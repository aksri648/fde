import httpx

from app.adapters.base_adapter import BaseAdapter
from app.config import get_settings
from app.models.deployment import DeploymentConfig
from app.utils.logger import get_logger

logger = get_logger("runpod_adapter")


class RunPodAdapter(BaseAdapter):
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.RUNPOD_API_KEY
        self.graphql_url = f"https://api.runpod.io/graphql?api_key={self.api_key}"

    async def deploy(self, config: DeploymentConfig) -> dict:
        gpu_map = {
            "A100_80GB": "AMPERE_80",
            "H100": "HOPPER_80",
            "RTX_4090": "ADA_24",
            "L4": "ADA_24",
            "T4": "TURING_16",
            "A10G": "AMPERE_24",
        }
        gpu_id = gpu_map.get(config.gpu_type, "AMPERE_80")
        max_workers = config.scaling_config.get("max_workers", 4)
        idle_timeout = config.scaling_config.get("idle_timeout", 5)

        mutation = """
        mutation saveEndpoint($input: SaveEndpointInput!) {
            saveEndpoint(input: $input) {
                id
                gpuIds
                workersMin
                workersMax
            }
        }
        """

        variables = {
            "input": {
                "name": f"llmdeployer-{config.model_name.replace('/', '-')}",
                "templateId": "vllm-template",
                "gpuIds": [gpu_id],
                "workersMin": 0,
                "workersMax": max_workers,
                "idleTimeout": idle_timeout,
                "scalerType": "QUEUE_DELAY",
                "scalerValue": 4,
            }
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.graphql_url,
                json={"query": mutation, "variables": variables},
                timeout=30.0,
            )
            data = resp.json()

        endpoint_id = data.get("data", {}).get("saveEndpoint", {}).get("id", "unknown")
        endpoint_url = f"https://api.runpod.ai/v2/{endpoint_id}/openai/v1/chat/completions"

        return {
            "endpoint_id": endpoint_id,
            "endpoint_url": endpoint_url,
            "status": "created",
        }

    async def check_status(self, deployment_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.runpod.ai/v2/{deployment_id}/health",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10.0,
            )
            return resp.json()

    async def teardown(self, deployment_id: str) -> dict:
        mutation = """
        mutation terminateEndpoint($input: TerminateEndpointInput!) {
            terminateEndpoint(input: $input) { id }
        }
        """
        async with httpx.AsyncClient() as client:
            await client.post(
                self.graphql_url,
                json={"query": mutation, "variables": {"input": {"id": deployment_id}}},
                timeout=30.0,
            )
        return {"status": "terminated", "deployment_id": deployment_id}
