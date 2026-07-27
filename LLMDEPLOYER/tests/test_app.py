import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app
from app.services.session_manager import SessionManager
from app.services.question_flow import get_questions, compile_requirements
from app.services.connection_manager import ConnectionManager
from app.adapters.vllm_deployer import VLLMDeployer
from app.adapters.nim_deployer import NIMDeployer


client = TestClient(app)


class TestSessionManager:
    def setup_method(self):
        self.manager = SessionManager()

    def test_create_session(self):
        session = self.manager.create_session()
        assert session.session_id
        assert session.status == "created"

    def test_get_session(self):
        session = self.manager.create_session()
        retrieved = self.manager.get_session(session.session_id)
        assert retrieved.session_id == session.session_id

    def test_get_session_not_found(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            self.manager.get_session("nonexistent")
        assert exc.value.status_code == 404

    def test_update_status(self):
        session = self.manager.create_session()
        self.manager.update_status(session.session_id, "deploying")
        retrieved = self.manager.get_session(session.session_id)
        assert retrieved.status == "deploying"


class TestQuestionFlow:
    def test_get_questions(self):
        questions = get_questions()
        assert len(questions) == 8
        assert questions[0].id == "purpose"

    def test_compile_requirements_valid(self):
        answers = {
            "purpose": "General Usage",
            "concurrent_users": 50,
            "peak_capacity": 100,
            "business_context": "Test deployment",
            "compliance": ["SOC 2"],
            "model_preference": "Llama 3.1 70B",
            "latency_requirements": "Moderate (<2s TTFT)",
            "budget_constraints": "$2,000 - $10,000/month",
        }
        req = compile_requirements(answers)
        assert req.purpose == "General Usage"
        assert req.concurrent_users == 50

    def test_compile_requirements_missing_field(self):
        from fastapi import HTTPException
        answers = {"purpose": "General Usage"}
        with pytest.raises(HTTPException) as exc:
            compile_requirements(answers)
        assert exc.value.status_code == 422

    def test_compile_requirements_invalid_number(self):
        from fastapi import HTTPException
        answers = {
            "purpose": "General Usage",
            "concurrent_users": -5,
            "peak_capacity": 100,
            "business_context": "Test",
            "compliance": [],
            "model_preference": "Llama 3.1 70B",
            "latency_requirements": "Moderate",
            "budget_constraints": "$500",
        }
        with pytest.raises(HTTPException) as exc:
            compile_requirements(answers)
        assert exc.value.status_code == 422


class TestVLLMDeployer:
    def setup_method(self):
        self.deployer = VLLMDeployer()

    def test_generate_docker_run_command_basic(self):
        cmd = self.deployer.generate_docker_run_command("meta-llama/Llama-3.1-70B", {})
        assert "--runtime nvidia" in cmd
        assert "--gpus all" in cmd
        assert "--ipc=host" in cmd
        assert "--model meta-llama/Llama-3.1-70B" in cmd

    def test_generate_docker_run_command_with_flags(self):
        flags = {"tensor_parallel_size": 4, "quantization": "fp8"}
        cmd = self.deployer.generate_docker_run_command("meta-llama/Llama-3.1-70B", flags)
        assert "--tensor-parallel-size 4" in cmd
        assert "--quantization fp8" in cmd

    def test_get_recommended_optimization_flags(self):
        flags = self.deployer.get_recommended_optimization_flags(
            "Llama-3.1-70B", "A100_80GB", 2, "Low (<500ms TTFT)"
        )
        assert flags["tensor_parallel_size"] == 2
        assert flags.get("enable_prefix_caching") == True

    def test_generate_k8s_manifest(self):
        manifest = self.deployer.generate_k8s_deployment_manifest(
            "Llama-3.1-70B", {"tensor_parallel_size": 2}, 2, 2
        )
        assert "deployment" in manifest
        assert "service" in manifest


class TestNIMDeployer:
    def setup_method(self):
        self.deployer = NIMDeployer()

    def test_get_nim_image_path_known_model(self):
        path = self.deployer.get_nim_image_path("llama-3.1-8b-instruct")
        assert path == "nvcr.io/nim/meta/llama-3.1-8b-instruct:latest"

    def test_get_nim_image_path_unknown_model(self):
        path = self.deployer.get_nim_image_path("custom-model")
        assert path == "nvcr.io/nim/custom-model:latest"

    def test_get_nim_image_path_full_path(self):
        path = self.deployer.get_nim_image_path("nvcr.io/nim/meta/llama-3.1-8b-instruct:latest")
        assert path == "nvcr.io/nim/meta/llama-3.1-8b-instruct:latest"

    def test_get_gpu_requirements(self):
        reqs = self.deployer.get_gpu_requirements("Llama-3.1-70B")
        assert reqs["min_gpus"] == 2
        assert reqs["min_vram_per_gpu_gb"] == 80

    def test_generate_docker_run_command(self):
        cmd = self.deployer.generate_docker_run_command("nvcr.io/nim/meta/llama-3.1-8b-instruct:latest")
        assert "--gpus all" in cmd
        assert "NGC_API_KEY" in cmd
        assert "nvcr.io/nim/meta/llama-3.1-8b-instruct:latest" in cmd


class TestRESTEndpoints:
    def test_health_check(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "providers" in data

    def test_get_questions(self):
        response = client.get("/api/questions")
        assert response.status_code == 200
        data = response.json()
        assert "questions" in data
        assert len(data["questions"]) == 8

    def test_create_session(self):
        response = client.post("/api/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "created"

    def test_get_session(self):
        create_resp = client.post("/api/sessions")
        session_id = create_resp.json()["session_id"]
        response = client.get(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["session_id"] == session_id

    def test_get_session_not_found(self):
        response = client.get("/api/sessions/nonexistent")
        assert response.status_code == 404

    def test_submit_answers(self):
        create_resp = client.post("/api/sessions")
        session_id = create_resp.json()["session_id"]
        answers = {
            "answers": {
                "purpose": "General Usage",
                "concurrent_users": 10,
                "peak_capacity": 20,
                "business_context": "Testing",
                "compliance": [],
                "model_preference": "Llama 3.1 8B",
                "latency_requirements": "Moderate (<2s TTFT)",
                "budget_constraints": "< $500/month",
            }
        }
        response = client.post(f"/api/sessions/{session_id}/answers", json=answers)
        assert response.status_code == 200
        assert response.json()["status"] == "analyzing"

    def test_get_messages(self):
        create_resp = client.post("/api/sessions")
        session_id = create_resp.json()["session_id"]
        response = client.get(f"/api/sessions/{session_id}/messages")
        assert response.status_code == 200
        assert "messages" in response.json()

    def test_get_status(self):
        create_resp = client.post("/api/sessions")
        session_id = create_resp.json()["session_id"]
        response = client.get(f"/api/sessions/{session_id}/status")
        assert response.status_code == 200
        assert response.json()["status"] == "created"

    def test_send_message(self):
        create_resp = client.post("/api/sessions")
        session_id = create_resp.json()["session_id"]
        response = client.post(
            f"/api/sessions/{session_id}/message",
            json={"text": "Switch to cheaper GPU"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "received"
