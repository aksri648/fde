from app.utils.logger import get_logger

logger = get_logger("nim_deployer")


class NIMDeployer:
    NIM_IMAGE_MAP = {
        "llama-3.1-8b-instruct": "nvcr.io/nim/meta/llama-3.1-8b-instruct:latest",
        "llama-3.1-70b-instruct": "nvcr.io/nim/meta/llama-3.1-70b-instruct:latest",
        "llama-3.1-405b-instruct": "nvcr.io/nim/meta/llama-3.1-405b-instruct:latest",
        "llama-3.2-1b-instruct": "nvcr.io/nim/meta/llama-3.2-1b-instruct:latest",
        "llama-3.2-3b-instruct": "nvcr.io/nim/meta/llama-3.2-3b-instruct:latest",
        "mistral-7b-instruct": "nvcr.io/nim/mistralai/mistral-7b-instruct-v03:latest",
        "mixtral-8x7b-instruct": "nvcr.io/nim/mistralai/mixtral-8x7b-instruct-v01:latest",
        "mixtral-8x22b-instruct": "nvcr.io/nim/mistralai/mixtral-8x22b-instruct-v01:latest",
        "nemotron-4-340b-instruct": "nvcr.io/nim/nvidia/nemotron-4-340b-instruct:latest",
    }

    GPU_REQUIREMENTS = {
        "8b": {"min_gpus": 1, "recommended_gpu_type": "L4", "min_vram_per_gpu_gb": 16},
        "70b": {"min_gpus": 2, "recommended_gpu_type": "A100_80GB", "min_vram_per_gpu_gb": 80},
        "405b": {"min_gpus": 8, "recommended_gpu_type": "H100", "min_vram_per_gpu_gb": 80},
    }

    def get_nim_image_path(self, model_name: str) -> str:
        model_lower = model_name.lower().replace(" ", "-")
        if model_lower in self.NIM_IMAGE_MAP:
            return self.NIM_IMAGE_MAP[model_lower]
        if "nvcr.io/" in model_name:
            return model_name
        return f"nvcr.io/nim/{model_name}:latest"

    def generate_docker_run_command(self, nim_image: str, port: int = 8000) -> str:
        return (
            f"docker run --gpus all "
            f"-e NGC_API_KEY=$NGC_API_KEY "
            f"-v $HOME/.cache/nim:/opt/nim/.cache "
            f"-p {port}:8000 "
            f"{nim_image}"
        )

    def generate_k8s_deployment_manifest(
        self, nim_image: str, replicas: int, gpu_count: int
    ) -> dict:
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": f"nim-{nim_image.split('/')[-2]}"},
            "spec": {
                "replicas": replicas,
                "selector": {
                    "matchLabels": {"app": f"nim-{nim_image.split('/')[-2]}"}
                },
                "template": {
                    "metadata": {
                        "labels": {"app": f"nim-{nim_image.split('/')[-2]}"}
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "nim",
                                "image": nim_image,
                                "ports": [{"containerPort": 8000}],
                                "env": [
                                    {"name": "NGC_API_KEY", "valueFrom": {"secretKeyRef": {"name": "ngc-secret", "key": "api-key"}}}
                                ],
                                "resources": {
                                    "requests": {"nvidia.com/gpu": str(gpu_count)},
                                    "limits": {"nvidia.com/gpu": str(gpu_count)},
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/v1/health/ready", "port": 8000},
                                    "initialDelaySeconds": 60,
                                    "periodSeconds": 10,
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": "/v1/health/live", "port": 8000},
                                    "initialDelaySeconds": 120,
                                    "periodSeconds": 30,
                                },
                            }
                        ],
                        "imagePullSecrets": [{"name": "ngc-secret"}],
                        "nodeSelector": {"accelerator": "nvidia-gpu"},
                        "tolerations": [
                            {"key": "sku", "operator": "Equal", "value": "gpu", "effect": "NoSchedule"}
                        ],
                    },
                },
            },
        }

        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": f"nim-{nim_image.split('/')[-2]}"},
            "spec": {
                "selector": {"app": f"nim-{nim_image.split('/')[-2]}"},
                "ports": [{"port": 8000, "targetPort": 8000}],
                "type": "LoadBalancer",
            },
        }

        return {"deployment": deployment, "service": service}

    def generate_aca_container_config(self, nim_image: str) -> dict:
        return {
            "image": nim_image,
            "env": [{"name": "NGC_API_KEY", "value": ""}],
            "ports": [{"containerPort": 8000}],
            "resources": {"cpu": 2.0, "memory": "4Gi"},
        }

    def get_gpu_requirements(self, model_name: str) -> dict:
        model_lower = model_name.lower()
        if "405b" in model_lower or "400b" in model_lower:
            return self.GPU_REQUIREMENTS["405b"]
        elif "70b" in model_lower or "72b" in model_lower:
            return self.GPU_REQUIREMENTS["70b"]
        elif "8b" in model_lower or "7b" in model_lower or "3b" in model_lower or "1b" in model_lower:
            return self.GPU_REQUIREMENTS["8b"]
        return {"min_gpus": 1, "recommended_gpu_type": "A100_80GB", "min_vram_per_gpu_gb": 40}
