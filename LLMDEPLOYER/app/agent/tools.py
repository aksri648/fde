import json
import asyncio
import litellm

from app.adapters.runpod_adapter import RunPodAdapter
from app.adapters.modal_adapter import ModalAdapter
from app.adapters.azure_adapter import AzureAdapter
from app.adapters.vllm_deployer import VLLMDeployer
from app.adapters.nim_deployer import NIMDeployer
from app.utils.logger import get_logger

logger = get_logger("agent_tools")


async def analyze_requirements(requirements: str) -> str:
    req = json.loads(requirements) if isinstance(requirements, str) else requirements
    return json.dumps(
        {
            "analysis": "Requirements analyzed successfully",
            "requirements": req,
            "recommended_strategy": "To be determined by the agent based on requirements",
        }
    )


async def deploy_runpod_serverless(
    model_name: str, gpu_type: str, max_workers: int, idle_timeout: int
) -> str:
    adapter = RunPodAdapter()
    from app.models.deployment import DeploymentConfig

    config = DeploymentConfig(
        strategy="runpod_serverless",
        model_name=model_name,
        gpu_type=gpu_type,
        gpu_count=1,
        region="us",
        scaling_config={"max_workers": max_workers, "idle_timeout": idle_timeout},
        optimization_flags={},
    )
    result = await adapter.deploy(config)
    return json.dumps(result)


async def deploy_modal_serverless(
    model_name: str, gpu_type: str, max_containers: int, container_idle_timeout: int
) -> str:
    adapter = ModalAdapter()
    from app.models.deployment import DeploymentConfig

    config = DeploymentConfig(
        strategy="modal_serverless",
        model_name=model_name,
        gpu_type=gpu_type,
        gpu_count=1,
        region="us",
        scaling_config={
            "max_containers": max_containers,
            "container_idle_timeout": container_idle_timeout,
        },
        optimization_flags={},
    )
    result = await adapter.deploy(config)
    return json.dumps(result)


async def deploy_vllm_on_azure(
    model_name: str,
    deployment_target: str,
    gpu_vm_size: str,
    gpu_count: int,
    region: str,
    optimization_flags: dict,
) -> str:
    azure_adapter = AzureAdapter()
    vllm_deployer = VLLMDeployer()

    recommended = vllm_deployer.get_recommended_optimization_flags(
        model_name, gpu_vm_size, gpu_count, "Moderate"
    )
    flags = {**recommended, **optimization_flags}

    resource_group = f"llmdeployer-{model_name.replace('/', '-')}"
    await asyncio.to_thread(
        azure_adapter.create_resource_group, resource_group, region, {"purpose": "llm-deployment"}
    )

    if deployment_target == "vm":
        nic_id = ""
        vm_result = await asyncio.to_thread(
            azure_adapter.provision_gpu_vm,
            resource_group,
            f"vm-{model_name.replace('/', '-')}",
            region,
            gpu_vm_size,
            {"publisher": "Canonical", "offer": "0001-com-ubuntu-server-jammy", "sku": "22_04-lts", "version": "latest"},
            nic_id,
        )
        return json.dumps(
            {
                "endpoint_url": f"http://{vm_result.get('public_ip', '')}:8000",
                "resource_ids": [vm_result.get("vm_id", "")],
                "status": "deploying",
                "deployment_target": "vm",
            }
        )
    elif deployment_target == "aks":
        cluster_result = await asyncio.to_thread(
            azure_adapter.create_aks_cluster,
            resource_group,
            f"aks-{model_name.replace('/', '-')}",
            region,
            gpu_vm_size,
            gpu_count,
            1,
            4,
        )
        return json.dumps(
            {
                "endpoint_url": f"http://{cluster_result.get('fqdn', '')}:8000",
                "resource_ids": [cluster_result.get("cluster_id", "")],
                "status": "deploying",
                "deployment_target": "aks",
            }
        )
    elif deployment_target == "aca":
        app_result = await asyncio.to_thread(
            azure_adapter.deploy_container_app,
            resource_group,
            f"aca-{model_name.replace('/', '-')}",
            region,
            "",
            "vllm/vllm-openai:latest",
            ["--model", model_name],
            8000,
            0,
            4,
        )
        return json.dumps(
            {
                "endpoint_url": f"https://{app_result.get('fqdn', '')}",
                "resource_ids": [app_result.get("app_id", "")],
                "status": "deploying",
                "deployment_target": "aca",
            }
        )
    else:
        return json.dumps({"error": f"Unknown deployment target: {deployment_target}"})


async def deploy_nim_on_azure(
    model_name: str,
    nim_image: str,
    deployment_target: str,
    gpu_vm_size: str,
    gpu_count: int,
    region: str,
) -> str:
    azure_adapter = AzureAdapter()
    nim_deployer = NIMDeployer()

    if not nim_image:
        nim_image = nim_deployer.get_nim_image_path(model_name)

    resource_group = f"llmdeployer-nim-{model_name.replace('/', '-')}"
    await asyncio.to_thread(
        azure_adapter.create_resource_group, resource_group, region, {"purpose": "nim-deployment"}
    )

    if deployment_target == "aks":
        cluster_result = await asyncio.to_thread(
            azure_adapter.create_aks_cluster,
            resource_group,
            f"aks-nim-{model_name.replace('/', '-')}",
            region,
            gpu_vm_size,
            gpu_count,
            1,
            4,
        )
        return json.dumps(
            {
                "endpoint_url": f"http://{cluster_result.get('fqdn', '')}:8000",
                "resource_ids": [cluster_result.get("cluster_id", "")],
                "status": "deploying",
                "deployment_target": "aks",
            }
        )
    elif deployment_target == "aca":
        app_result = await asyncio.to_thread(
            azure_adapter.deploy_container_app,
            resource_group,
            f"aca-nim-{model_name.replace('/', '-')}",
            region,
            "",
            nim_image,
            [],
            8000,
            0,
            4,
        )
        return json.dumps(
            {
                "endpoint_url": f"https://{app_result.get('fqdn', '')}",
                "resource_ids": [app_result.get("app_id", "")],
                "status": "deploying",
                "deployment_target": "aca",
            }
        )
    else:
        return json.dumps({"error": f"Unknown deployment target: {deployment_target}"})


async def check_deployment_status(deployment_id: str, provider: str) -> str:
    if provider == "azure":
        return json.dumps({"status": "unknown", "detail": "Azure status check not implemented"})
    elif provider == "runpod":
        adapter = RunPodAdapter()
        result = await adapter.check_status(deployment_id)
        return json.dumps(result)
    elif provider == "modal":
        adapter = ModalAdapter()
        result = await adapter.check_status(deployment_id)
        return json.dumps(result)
    return json.dumps({"error": f"Unknown provider: {provider}"})


async def estimate_cost(
    strategy: str, gpu_type: str, gpu_count: int, hours_per_day: float, provider: str
) -> str:
    pricing = {
        "A100_80GB": 2.21,
        "H100": 3.70,
        "L4": 0.80,
        "T4": 0.50,
        "A10G": 0.80,
        "RTX_4090": 0.40,
    }
    hourly_rate = pricing.get(gpu_type, 1.0) * gpu_count
    monthly_cost = hourly_rate * hours_per_day * 30
    return json.dumps(
        {
            "estimated_monthly_cost": round(monthly_cost, 2),
            "hourly_rate": round(hourly_rate, 2),
            "gpu_type": gpu_type,
            "gpu_count": gpu_count,
            "hours_per_day": hours_per_day,
            "strategy": strategy,
        }
    )


async def test_deployed_endpoint(
    endpoint_url: str, model_name: str, test_prompt: str, api_key: str = ""
) -> str:
    try:
        kwargs = {"model": f"openai/{model_name}", "api_base": endpoint_url, "messages": [{"role": "user", "content": test_prompt}]}
        if api_key:
            kwargs["api_key"] = api_key
        response = await litellm.acompletion(**kwargs)
        return json.dumps(
            {
                "success": True,
                "response": response.choices[0].message.content,
                "model": model_name,
            }
        )
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
