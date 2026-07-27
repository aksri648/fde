from app.utils.logger import get_logger

logger = get_logger("vllm_deployer")


class VLLMDeployer:
    def generate_docker_run_command(
        self, model_name: str, optimization_flags: dict, port: int = 8000
    ) -> str:
        cmd = [
            "docker run",
            "--runtime nvidia",
            "--gpus all",
            "-v ~/.cache/huggingface:/root/.cache/huggingface",
            "--ipc=host",
            f"-p {port}:8000",
            "vllm/vllm-openai:latest",
            f"--model {model_name}",
            "--host 0.0.0.0",
            "--port 8000",
        ]

        if optimization_flags.get("tensor_parallel_size"):
            cmd.append(f"--tensor-parallel-size {optimization_flags['tensor_parallel_size']}")
        if optimization_flags.get("quantization"):
            cmd.append(f"--quantization {optimization_flags['quantization']}")
        if optimization_flags.get("kv_cache_dtype"):
            cmd.append(f"--kv-cache-dtype {optimization_flags['kv_cache_dtype']}")
        if optimization_flags.get("max_model_len"):
            cmd.append(f"--max-model-len {optimization_flags['max_model_len']}")
        if optimization_flags.get("gpu_memory_utilization"):
            cmd.append(f"--gpu-memory-utilization {optimization_flags['gpu_memory_utilization']}")
        if optimization_flags.get("enable_prefix_caching"):
            cmd.append("--enable-prefix-caching")
        if optimization_flags.get("enable_chunked_prefill"):
            cmd.append("--enable-chunked-prefill")
        if optimization_flags.get("max_num_seqs"):
            cmd.append(f"--max-num-seqs {optimization_flags['max_num_seqs']}")
        if optimization_flags.get("swap_space"):
            cmd.append(f"--swap-space {optimization_flags['swap_space']}")
        if optimization_flags.get("cpu_offload_gb"):
            cmd.append(f"--cpu-offload-gb {optimization_flags['cpu_offload_gb']}")

        return " ".join(cmd)

    def generate_k8s_deployment_manifest(
        self, model_name: str, optimization_flags: dict, replicas: int, gpu_count: int
    ) -> dict:
        args = ["--model", model_name, "--host", "0.0.0.0", "--port", "8000"]

        if optimization_flags.get("tensor_parallel_size"):
            args.extend(["--tensor-parallel-size", str(optimization_flags["tensor_parallel_size"])])
        if optimization_flags.get("quantization"):
            args.extend(["--quantization", optimization_flags["quantization"]])

        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": f"vllm-{model_name.replace('/', '-')}"},
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app": f"vllm-{model_name.replace('/', '-')}"}},
                "template": {
                    "metadata": {"labels": {"app": f"vllm-{model_name.replace('/', '-')}"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "vllm",
                                "image": "vllm/vllm-openai:latest",
                                "args": args,
                                "ports": [{"containerPort": 8000}],
                                "resources": {
                                    "requests": {"nvidia.com/gpu": str(gpu_count)},
                                    "limits": {"nvidia.com/gpu": str(gpu_count)},
                                },
                            }
                        ],
                        "nodeSelector": {"accelerator": "nvidia-gpu"},
                        "tolerations": [
                            {"key": "sku", "operator": "Equal", "value": "gpu", "effect": "NoSchedule"}
                        ],
                        "hostIPC": True,
                    },
                },
            },
        }

        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": f"vllm-{model_name.replace('/', '-')}"},
            "spec": {
                "selector": {"app": f"vllm-{model_name.replace('/', '-')}"},
                "ports": [{"port": 8000, "targetPort": 8000}],
                "type": "LoadBalancer",
            },
        }

        return {"deployment": deployment, "service": service}

    def generate_aca_container_config(
        self, model_name: str, optimization_flags: dict
    ) -> dict:
        args = ["--model", model_name, "--host", "0.0.0.0", "--port", "8000"]

        if optimization_flags.get("tensor_parallel_size"):
            args.extend(["--tensor-parallel-size", str(optimization_flags["tensor_parallel_size"])])
        if optimization_flags.get("quantization"):
            args.extend(["--quantization", optimization_flags["quantization"]])

        return {
            "image": "vllm/vllm-openai:latest",
            "args": args,
            "resources": {"cpu": 2.0, "memory": "4Gi"},
            "ports": [{"containerPort": 8000}],
        }

    def get_recommended_optimization_flags(
        self,
        model_name: str,
        gpu_type: str,
        gpu_count: int,
        latency_requirements: str,
    ) -> dict:
        flags = {"gpu_memory_utilization": 0.90}

        if gpu_count > 1:
            flags["tensor_parallel_size"] = gpu_count

        model_lower = model_name.lower()
        param_size = 0
        if "405b" in model_lower or "400b" in model_lower:
            param_size = 405
        elif "70b" in model_lower or "72b" in model_lower:
            param_size = 70
        elif "13b" in model_lower:
            param_size = 13
        elif "7b" in model_lower or "8b" in model_lower:
            param_size = 7

        gpu_vram = {
            "T4": 16, "L4": 24, "A10G": 24, "RTX_4090": 24,
            "A100_40GB": 40, "A100_80GB": 80, "H100": 80, "H200": 141,
        }
        vram = gpu_vram.get(gpu_type, 40)

        if param_size > 0 and param_size * 2 > vram * gpu_count:
            if vram >= 80:
                flags["quantization"] = "fp8"
                flags["kv_cache_dtype"] = "fp8"
            else:
                flags["quantization"] = "awq"

        if "Ultra-low" in latency_requirements or "Low" in latency_requirements:
            flags["enable_prefix_caching"] = True
            flags["enable_chunked_prefill"] = True

        return flags
