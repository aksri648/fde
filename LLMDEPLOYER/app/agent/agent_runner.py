import json

from anthropic import Anthropic

from app.agent.system_prompt import load_system_prompt
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("agent_runner")


async def run_deployment_agent(
    session_id: str,
    requirements: dict,
    on_message,
    on_status,
):
    settings = get_settings()
    system_prompt = load_system_prompt()
    full_prompt = f"{system_prompt}\n\nThe user has provided the following deployment requirements:\n{json.dumps(requirements, indent=2)}"

    # Point ANTHROPIC_BASE_URL at the LiteLLM proxy to route the Anthropic
    # client to an OpenAI-compatible backend. Empty -> real Anthropic endpoint.
    client = Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        base_url=settings.ANTHROPIC_BASE_URL or None,
    )

    try:
        await on_status("analyzing")
        await on_message("Analyzing your deployment requirements...")

        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=4096,
            system=full_prompt,
            messages=[{"role": "user", "content": "Analyze the deployment requirements provided in the system prompt and execute the optimal deployment strategy using the available tools. Explain your reasoning at each step."}],
        )

        for block in response.content:
            if block.type == "text":
                await on_message(block.text)
            elif block.type == "tool_use":
                await on_status(f"Executing: {block.name}")
                logger.info(f"Tool use: {block.name} with input: {block.input}")

                from app.agent.tools import (
                    analyze_requirements,
                    deploy_runpod_serverless,
                    deploy_modal_serverless,
                    deploy_vllm_on_azure,
                    deploy_nim_on_azure,
                    check_deployment_status,
                    estimate_cost,
                    test_deployed_endpoint,
                )

                tool_map = {
                    "analyze_requirements": analyze_requirements,
                    "deploy_runpod_serverless": deploy_runpod_serverless,
                    "deploy_modal_serverless": deploy_modal_serverless,
                    "deploy_vllm_on_azure": deploy_vllm_on_azure,
                    "deploy_nim_on_azure": deploy_nim_on_azure,
                    "check_deployment_status": check_deployment_status,
                    "estimate_cost": estimate_cost,
                    "test_deployed_endpoint": test_deployed_endpoint,
                }

                tool_func = tool_map.get(block.name)
                if tool_func:
                    result = await tool_func(**block.input)
                    await on_status(f"Completed: {block.name}")
                    await on_message(f"Tool {block.name} result: {result}")
                else:
                    await on_message(f"Unknown tool: {block.name}")

        await on_status("completed")
        await on_message("Deployment analysis and execution completed.")

    except Exception as e:
        logger.error(f"Agent failed: {e}")
        await on_status("failed")
        await on_message(f"Deployment failed: {str(e)}")
