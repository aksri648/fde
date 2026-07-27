from typing import Literal
from pydantic import BaseModel


class DeploymentConfig(BaseModel):
    strategy: Literal[
        "runpod_serverless",
        "modal_serverless",
        "vllm_azure_vm",
        "vllm_azure_aks",
        "vllm_azure_aca",
        "nim_azure_aks",
        "nim_azure_aca",
        "nim_azure_vm",
    ]
    cloud_provider: str = "azure"
    model_name: str
    gpu_type: str
    gpu_count: int
    region: str
    scaling_config: dict
    optimization_flags: dict
