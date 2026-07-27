from abc import ABC, abstractmethod

from app.models.deployment import DeploymentConfig


class BaseAdapter(ABC):
    @abstractmethod
    async def deploy(self, config: DeploymentConfig) -> dict:
        pass

    @abstractmethod
    async def check_status(self, deployment_id: str) -> dict:
        pass

    @abstractmethod
    async def teardown(self, deployment_id: str) -> dict:
        pass

    def validate_config(self, config: DeploymentConfig) -> bool:
        required = ["strategy", "model_name", "gpu_type", "gpu_count", "region"]
        return all(getattr(config, field) for field in required)
