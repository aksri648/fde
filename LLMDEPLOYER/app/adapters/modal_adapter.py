import tempfile
import subprocess
import os

from app.adapters.base_adapter import BaseAdapter
from app.config import get_settings
from app.models.deployment import DeploymentConfig
from app.utils.logger import get_logger

logger = get_logger("modal_adapter")


class ModalAdapter(BaseAdapter):
    def __init__(self):
        settings = get_settings()
        os.environ["MODAL_TOKEN_ID"] = settings.MODAL_TOKEN_ID
        os.environ["MODAL_TOKEN_SECRET"] = settings.MODAL_TOKEN_SECRET

    def _generate_modal_script(self, config: DeploymentConfig) -> str:
        gpu_type = config.gpu_type.lower().replace("_", "").replace("gb", "")
        gpu_map = {
            "a100": "A100",
            "a10080gb": "A100-80GB",
            "h100": "H100",
            "l4": "L4",
            "t4": "T4",
            "a10g": "A10G",
        }
        gpu_class = gpu_map.get(gpu_type, "A100")

        return f'''
import modal

app = modal.App("llmdeployer-{config.model_name.replace("/", "-")}")

image = modal.Image.debian_slim(python_version="3.12").pip_install("vllm", "torch")

@app.cls(
    gpu=modal.gpu.{gpu_class}(),
    image=image,
    container_idle_timeout={config.scaling_config.get("container_idle_timeout", 120)},
    concurrency_limit={config.scaling_config.get("max_containers", 4)},
)
class Inference:
    @modal.enter()
    def load_model(self):
        from vllm import LLM
        self.llm = LLM(model="{config.model_name}")

    @modal.web_endpoint(method="POST")
    def generate(self, request: dict) -> dict:
        from vllm import SamplingParams
        prompt = request.get("prompt", "")
        params = SamplingParams(temperature=0.7, max_tokens=1024)
        outputs = self.llm.generate([prompt], params)
        return {{"response": outputs[0].outputs[0].text}}
'''

    async def deploy(self, config: DeploymentConfig) -> dict:
        script_content = self._generate_modal_script(config)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(script_content)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["modal", "deploy", temp_path],
                capture_output=True,
                text=True,
                timeout=300,
            )

            endpoint_url = ""
            for line in result.stdout.split("\n"):
                if "https://" in line:
                    endpoint_url = line.strip()
                    break

            return {
                "app_name": f"llmdeployer-{config.model_name.replace('/', '-')}",
                "endpoint_url": endpoint_url,
                "status": "deployed",
                "stdout": result.stdout,
            }
        finally:
            os.unlink(temp_path)

    async def check_status(self, deployment_id: str) -> dict:
        result = subprocess.run(
            ["modal", "app", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {"status": "unknown", "output": result.stdout}

    async def teardown(self, deployment_id: str) -> dict:
        subprocess.run(
            ["modal", "app", "stop", deployment_id],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {"status": "stopped", "deployment_id": deployment_id}
