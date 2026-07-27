import json

from anthropic import AsyncAnthropic

from app.agent.system_prompt import load_system_prompt
from app.agent.tools import (
    analyze_requirements,
    check_deployment_status,
    deploy_modal_serverless,
    deploy_nim_on_azure,
    deploy_runpod_serverless,
    deploy_vllm_on_azure,
    estimate_cost,
    search_pricing,
    test_deployed_endpoint,
)
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("agent_runner")

# Maximum number of model<->tool round-trips before we stop, to bound cost and
# prevent an unterminated agent loop.
MAX_ITERATIONS = 12

# Maps tool names (as exposed to the model) to their async implementations.
TOOL_MAP = {
    "analyze_requirements": analyze_requirements,
    "search_pricing": search_pricing,
    "deploy_runpod_serverless": deploy_runpod_serverless,
    "deploy_modal_serverless": deploy_modal_serverless,
    "deploy_vllm_on_azure": deploy_vllm_on_azure,
    "deploy_nim_on_azure": deploy_nim_on_azure,
    "check_deployment_status": check_deployment_status,
    "estimate_cost": estimate_cost,
    "test_deployed_endpoint": test_deployed_endpoint,
}

# Anthropic tool schemas (Client SDK tool-use). The model chooses which of these
# to call; we execute the corresponding function and feed the result back.
DEPLOYMENT_TOOLS = [
    {
        "name": "analyze_requirements",
        "description": "Analyze the structured deployment requirements and record an initial assessment before choosing a strategy.",
        "input_schema": {
            "type": "object",
            "properties": {
                "requirements": {
                    "type": "string",
                    "description": "JSON string of the deployment requirements.",
                }
            },
            "required": ["requirements"],
        },
    },
    {
        "name": "search_pricing",
        "description": "Search for real-time cloud GPU pricing information using Tavily web search. Use this to get current pricing for specific GPU types, cloud providers, and deployment options before making cost estimates or recommendations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The pricing query, e.g. 'A100 80GB hourly rate' or 'RunPod serverless GPU pricing 2024'.",
                },
                "provider": {
                    "type": "string",
                    "description": "Optional cloud provider to focus the search (e.g. 'RunPod', 'Azure', 'Modal', 'Lambda Labs').",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "estimate_cost",
        "description": "Estimate the monthly cost of a deployment strategy using static pricing tables. Use search_pricing first for current rates; fall back to this for quick estimates when live data is unavailable.",
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy": {"type": "string"},
                "gpu_type": {"type": "string"},
                "gpu_count": {"type": "integer"},
                "hours_per_day": {"type": "number"},
                "provider": {"type": "string"},
            },
            "required": ["strategy", "gpu_type", "gpu_count", "hours_per_day", "provider"],
        },
    },
    {
        "name": "deploy_runpod_serverless",
        "description": "Provision a RunPod serverless endpoint. Best for low-scale, cost-sensitive, flexible-latency workloads.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string"},
                "gpu_type": {"type": "string"},
                "max_workers": {"type": "integer"},
                "idle_timeout": {"type": "integer"},
            },
            "required": ["model_name", "gpu_type", "max_workers", "idle_timeout"],
        },
    },
    {
        "name": "deploy_modal_serverless",
        "description": "Provision a Modal serverless deployment. Best for rapid iteration, Python-native workflows, and moderate scale.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string"},
                "gpu_type": {"type": "string"},
                "max_containers": {"type": "integer"},
                "container_idle_timeout": {"type": "integer"},
            },
            "required": [
                "model_name",
                "gpu_type",
                "max_containers",
                "container_idle_timeout",
            ],
        },
    },
    {
        "name": "deploy_vllm_on_azure",
        "description": "Deploy vLLM on Azure (VM, AKS, or ACA). Best for high throughput, custom optimization, and data-sovereignty/self-hosted control.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string"},
                "deployment_target": {
                    "type": "string",
                    "enum": ["vm", "aks", "aca"],
                },
                "gpu_vm_size": {"type": "string"},
                "gpu_count": {"type": "integer"},
                "region": {"type": "string"},
                "optimization_flags": {"type": "object"},
            },
            "required": [
                "model_name",
                "deployment_target",
                "gpu_vm_size",
                "gpu_count",
                "region",
                "optimization_flags",
            ],
        },
    },
    {
        "name": "deploy_nim_on_azure",
        "description": "Deploy an NVIDIA NIM container on Azure (AKS or ACA). Best for enterprise-grade, TensorRT-optimized performance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string"},
                "nim_image": {
                    "type": "string",
                    "description": "NIM container image path; leave empty to auto-resolve from model_name.",
                },
                "deployment_target": {"type": "string", "enum": ["aks", "aca"]},
                "gpu_vm_size": {"type": "string"},
                "gpu_count": {"type": "integer"},
                "region": {"type": "string"},
            },
            "required": [
                "model_name",
                "nim_image",
                "deployment_target",
                "gpu_vm_size",
                "gpu_count",
                "region",
            ],
        },
    },
    {
        "name": "check_deployment_status",
        "description": "Check the status of a previously created deployment by id and provider (azure|runpod|modal).",
        "input_schema": {
            "type": "object",
            "properties": {
                "deployment_id": {"type": "string"},
                "provider": {"type": "string", "enum": ["azure", "runpod", "modal"]},
            },
            "required": ["deployment_id", "provider"],
        },
    },
    {
        "name": "test_deployed_endpoint",
        "description": "Send a test prompt to a deployed OpenAI-compatible endpoint to verify it responds.",
        "input_schema": {
            "type": "object",
            "properties": {
                "endpoint_url": {"type": "string"},
                "model_name": {"type": "string"},
                "test_prompt": {"type": "string"},
                "api_key": {"type": "string"},
            },
            "required": ["endpoint_url", "model_name", "test_prompt"],
        },
    },
]


async def _execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Execute a tool by name. Returns (result_json_string, is_error)."""
    func = TOOL_MAP.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"}), True
    try:
        result = await func(**tool_input)
        return result, False
    except Exception as e:  # noqa: BLE001 - surface tool failures back to the model
        logger.error(f"Tool {name} failed: {e}")
        return json.dumps({"error": str(e)}), True


async def run_deployment_agent(
    session_id: str,
    requirements: dict,
    on_message,
    on_status,
):
    """Run the deployment agent using the Anthropic Client SDK tool-use loop.

    The model is given the deployment tools and autonomously calls them to
    estimate cost, provision infrastructure, and verify the endpoint. Each tool
    call is executed against the real adapters and the result is fed back to the
    model until it produces a final answer.

    All traffic is routed through ``ANTHROPIC_BASE_URL`` when set (e.g. the
    LiteLLM proxy), so this runs against your OpenAI-compatible backend while
    using the Anthropic tool-use protocol.
    """
    settings = get_settings()
    system_prompt = load_system_prompt()

    client = AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        base_url=settings.ANTHROPIC_BASE_URL or None,
    )

    user_message = (
        "Analyze the deployment requirements below and execute the optimal "
        "deployment strategy using the available tools. First use search_pricing "
        "to look up current GPU pricing for the relevant providers, then "
        "compare options with estimate_cost as a cross-check, call the "
        "appropriate deploy_* tool to actually provision the deployment, and "
        "finally verify it with test_deployed_endpoint. Explain your reasoning "
        "at each step.\n\n"
        f"Deployment requirements:\n{json.dumps(requirements, indent=2)}"
    )
    messages: list[dict] = [{"role": "user", "content": user_message}]

    try:
        await on_status("analyzing")
        await on_message("Analyzing your deployment requirements...")

        for iteration in range(MAX_ITERATIONS):
            response = await client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=4096,
                system=system_prompt,
                tools=DEPLOYMENT_TOOLS,
                messages=messages,
            )

            assistant_content: list[dict] = []
            tool_uses: list[tuple[str, str, dict]] = []  # (id, name, input)

            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                    if block.text.strip():
                        await on_message(block.text)
                elif block.type == "tool_use":
                    assistant_content.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        }
                    )
                    tool_uses.append((block.id, block.name, block.input))

            messages.append({"role": "assistant", "content": assistant_content})

            # No tool calls -> the model has produced its final response.
            if response.stop_reason != "tool_use" or not tool_uses:
                break

            tool_results: list[dict] = []
            for tool_id, tool_name, tool_input in tool_uses:
                await on_status(f"executing:{tool_name}")
                await on_message(f"Running tool: {tool_name}")

                result_str, is_error = await _execute_tool(tool_name, tool_input)

                await on_message(f"Tool {tool_name} result: {result_str}")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_str,
                        "is_error": is_error,
                    }
                )

            messages.append({"role": "user", "content": tool_results})
        else:
            await on_message(
                "Reached the maximum number of tool iterations; stopping."
            )

        await on_status("completed")
        await on_message("Deployment analysis and execution completed.")

    except Exception as e:
        logger.error(f"Agent failed: {e}")
        await on_status("failed")
        await on_message(f"Deployment failed: {str(e)}")
