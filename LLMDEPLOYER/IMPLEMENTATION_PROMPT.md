# LLMDeployer — Complete Implementation Prompt

> **Purpose**: This document is a fully self-contained implementation guide for building the "LLMDeployer" microservice. It is written so that any code-generation model — including smaller/weaker models — can follow the steps verbatim to produce a working system. There are no code snippets in this document; only guided, detailed, step-by-step instructions with cited official documentation links.

> **IMPORTANT**: This microservice is **backend-only**. It does NOT include a frontend. It exposes REST APIs and a WebSocket endpoint that are consumed by a shared frontend (or any other client). The frontend is a separate project maintained independently.

---

## Table of Contents

1. [Project Overview and Architecture](#1-project-overview-and-architecture)
2. [Technology Stack Summary](#2-technology-stack-summary)
3. [Official Documentation Reference Links](#3-official-documentation-reference-links)
4. [Phase 1 — Project Structure and Scaffolding](#4-phase-1--project-structure-and-scaffolding)
5. [Phase 2 — FastAPI Server and REST API Surface](#5-phase-2--fastapi-server-and-rest-api-surface)
6. [Phase 3 — OpenAI-to-Claude Translation Layer (LiteLLM)](#6-phase-3--openai-to-claude-translation-layer-litellm)
7. [Phase 4 — Claude Agent SDK Integration](#7-phase-4--claude-agent-sdk-integration)
8. [Phase 5 — Deployment Decision Engine (System Prompt Placeholder)](#8-phase-5--deployment-decision-engine-system-prompt-placeholder)
9. [Phase 6 — Azure Infrastructure Adapter](#9-phase-6--azure-infrastructure-adapter)
10. [Phase 7 — RunPod Serverless Adapter](#10-phase-7--runpod-serverless-adapter)
11. [Phase 8 — Modal Serverless Adapter](#11-phase-8--modal-serverless-adapter)
12. [Phase 9 — vLLM Self-Hosted Deployment Adapter](#12-phase-9--vllm-self-hosted-deployment-adapter)
13. [Phase 10 — NVIDIA NIM Container Deployment Adapter](#13-phase-10--nvidia-nim-container-deployment-adapter)
14. [Phase 11 — End-to-End Integration and Wiring](#14-phase-11--end-to-end-integration-and-wiring)
15. [Phase 12 — Environment Configuration and Secrets](#15-phase-12--environment-configuration-and-secrets)
16. [Phase 13 — Testing and Validation](#16-phase-13--testing-and-validation)
17. [Appendix A — Key API Format Differences (OpenAI vs Anthropic)](#appendix-a--key-api-format-differences-openai-vs-anthropic)
18. [Appendix B — Azure GPU VM Series Reference](#appendix-b--azure-gpu-vm-series-reference)
19. [Appendix C — vLLM Optimization Flags Reference](#appendix-c--vllm-optimization-flags-reference)
20. [Appendix D — Existing OpenAI-to-Claude Translation Repos](#appendix-d--existing-openai-to-claude-translation-repos)

---

## 1. Project Overview and Architecture

### What LLMDeployer Does

LLMDeployer is a **headless backend microservice** that:

1. Exposes **REST APIs** for external consumers (a shared frontend, CLI tools, or other microservices) to initiate and manage LLM deployment workflows.
2. Accepts structured user requirements via API (purpose, scale, compliance, model preferences, budget, etc.).
3. Sends the collected requirements to a **Claude Agent SDK** powered agent.
4. The Claude agent, guided by a **system prompt** (written separately by the owner), decides which deployment strategy to use:
   - **Serverless deployment** via RunPod or Modal
   - **vLLM-based self-hosted** deployment on Azure cloud infrastructure with optimization flags
   - **NVIDIA NIM-based** container deployment on Azure cloud infrastructure
5. The Claude agent then **executes the deployment plan** by calling the appropriate API adapters (RunPod / Modal / Azure) as tools.
6. An **OpenAI-to-Claude translation layer** — powered by an existing open-source project (recommended: **LiteLLM**) — allows any OpenAI-compatible endpoint to be used by the Claude Agent SDK, so the agent can also call OpenAI-compatible models (like vLLM endpoints, Azure OpenAI, etc.) through a unified interface.
7. Streams real-time progress and agent responses back to the caller via **WebSocket** or polling endpoints.

### High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│              EXTERNAL CONSUMERS                               │
│  (Shared Frontend, CLI, Other Microservices, Postman, etc.)   │
│                                                               │
│   REST API calls:          WebSocket:                         │
│   POST /api/sessions       WS /api/ws/{session_id}           │
│   POST /api/sessions/:id/answers                              │
│   GET  /api/sessions/:id/status                               │
│   GET  /api/sessions/:id/messages                             │
│   GET  /api/questions                                         │
│   GET  /api/health                                            │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / WebSocket
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              LLMDeployer MICROSERVICE (FastAPI / Python)       │
│                                                               │
│  ┌───────────────────┐   ┌─────────────────────────────┐     │
│  │   REST API Router │   │   Session / State Manager    │     │
│  │   (sessions,      │   │   (stores user answers,      │     │
│  │    questions,      │   │    chat history, status)     │     │
│  │    health, ws)     │   │                              │     │
│  └────────┬──────────┘   └──────────────┬──────────────┘     │
│           │                             │                      │
│           ▼                             ▼                      │
│  ┌──────────────────────────────────────────────────────┐     │
│  │        Claude Agent SDK Orchestrator                  │     │
│  │  - Receives collected requirements                    │     │
│  │  - Runs agent loop with system prompt                 │     │
│  │  - Calls deployment tools based on decision           │     │
│  └──────────────────────┬───────────────────────────────┘     │
│                         │                                      │
│          ┌──────────────┼──────────────┐                       │
│          ▼              ▼              ▼                       │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐              │
│  │  RunPod  │   │  Modal   │   │    Azure     │              │
│  │ Adapter  │   │ Adapter  │   │   Adapter    │              │
│  └──────────┘   └──────────┘   └──────┬───────┘              │
│                                       │                        │
│                          ┌────────────┼────────────┐           │
│                          ▼            ▼            ▼           │
│                     ┌────────┐  ┌────────┐  ┌─────────┐      │
│                     │  vLLM  │  │  NIM   │  │ AKS/VM  │      │
│                     │ Deploy │  │ Deploy │  │  Deploy  │      │
│                     └────────┘  └────────┘  └─────────┘      │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐     │
│  │   OpenAI ↔ Claude Translation (LiteLLM Sidecar)      │     │
│  │   Any OpenAI-compatible endpoint usable by agent      │     │
│  └──────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow (Step by Step)

1. External consumer calls `GET /api/questions` to retrieve the list of required questions.
2. Consumer presents questions to the user (via its own UI or CLI).
3. Consumer collects answers and calls `POST /api/sessions` to create a new session, then `POST /api/sessions/{id}/answers` to submit the full answers payload.
4. The microservice validates and stores the answers, then triggers the Claude agent orchestrator asynchronously.
5. Consumer connects via WebSocket at `WS /api/ws/{session_id}` to receive real-time agent messages and deployment status updates (alternatively, polls `GET /api/sessions/{id}/messages` and `GET /api/sessions/{id}/status`).
6. The Claude agent (guided by the system prompt) decides the deployment strategy.
7. The Claude agent calls the appropriate adapter tool(s) to provision infrastructure.
8. The adapter executes Azure SDK / RunPod API / Modal SDK calls.
9. Results and status updates stream back through the WebSocket (or are stored for polling).
10. Consumer receives the final deployment result (endpoint URL, resource IDs, etc.).

### REST API Contract Summary

| Method | Endpoint | Description |
|--------|---------|-------------|
| `GET` | `/api/health` | Health check — returns service status and version |
| `GET` | `/api/questions` | Returns the ordered list of questions the user must answer |
| `POST` | `/api/sessions` | Creates a new deployment session — returns `{session_id}` |
| `GET` | `/api/sessions/{id}` | Returns the full session object (status, requirements, messages, result) |
| `POST` | `/api/sessions/{id}/answers` | Submits all user answers — triggers the agent orchestrator |
| `GET` | `/api/sessions/{id}/status` | Returns current deployment status and result |
| `GET` | `/api/sessions/{id}/messages` | Returns all chat messages for the session (agent reasoning, status updates) |
| `POST` | `/api/sessions/{id}/message` | Sends an additional user message to the agent mid-run (optional) |
| `WS` | `/api/ws/{session_id}` | WebSocket for real-time streaming of agent messages and status |

---

## 2. Technology Stack Summary

| Layer | Technology | Version / Notes |
|-------|-----------|-----------------|
| **Backend Framework** | Python + FastAPI | Python 3.10+, FastAPI latest |
| **Agent Orchestration** | Claude Agent SDK | `pip install claude-agent-sdk` (Python 3.10+) |
| **Translation Layer** | LiteLLM (open-source) | `pip install litellm` — unified OpenAI-compatible gateway for 100+ LLMs |
| **Azure SDK** | `azure-identity`, `azure-mgmt-compute`, `azure-mgmt-containerservice`, `azure-mgmt-appcontainers`, `azure-mgmt-containerregistry`, `azure-mgmt-resource`, `azure-mgmt-network` | Latest from PyPI |
| **RunPod** | `runpod` Python SDK + REST API | `pip install runpod` |
| **Modal** | `modal` Python SDK | `pip install modal` |
| **WebSocket** | FastAPI WebSocket | For streaming agent responses to consumers |
| **Async HTTP** | `httpx` | For outbound API calls in adapters |

---

## 3. Official Documentation Reference Links

### Claude Agent SDK
- **GitHub Repository**: https://github.com/anthropics/claude-agent-sdk-python
- **Official Documentation**: https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk
- **Anthropic Messages API**: https://docs.anthropic.com/en/api/messages
- **Tool Use Guide**: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
- **Streaming Events**: https://docs.anthropic.com/en/api/messages-streaming

### OpenAI-to-Claude Translation (Open-Source Projects)
- **LiteLLM (RECOMMENDED)** — Unified LLM Gateway, production-grade, supports 100+ providers:
  - Documentation: https://docs.litellm.ai
  - GitHub: https://github.com/BerriAI/litellm
  - Proxy Server Guide: https://docs.litellm.ai/docs/simple_proxy
  - Python SDK Usage: https://docs.litellm.ai/docs/
- **UniClaudeProxy** — Dedicated proxy for Claude Code ↔ OpenAI-compatible backends:
  - GitHub: https://github.com/vibheksoni/UniClaudeProxy
- **OpenAI-to-Claude-API-Converter-Proxy** — Simple local conversion proxy:
  - GitHub: https://github.com/Skillter/OpenAI-to-Claude-API-Converter-Proxy
- **CCProxy** — High-performance Go-based Claude ↔ OpenAI proxy:
  - GitHub: https://github.com/orchestre/CCProxy

### OpenAI API Format (reference for understanding the translation)
- **Chat Completions API Reference**: https://platform.openai.com/docs/api-reference/chat/create
- **Models Endpoint**: https://platform.openai.com/docs/api-reference/models
- **Function/Tool Calling Guide**: https://platform.openai.com/docs/guides/function-calling

### Azure Infrastructure
- **Azure SDK for Python Developer Center**: https://learn.microsoft.com/en-us/python/api/
- **Azure Identity (`azure-identity`)**: https://learn.microsoft.com/en-us/python/api/overview/azure/identity-README
- **Azure Container Apps (Serverless GPU)**: https://learn.microsoft.com/en-us/azure/container-apps/gpu-workloads
- **AKS GPU Node Pools**: https://learn.microsoft.com/en-us/azure/aks/gpu-cluster
- **KAITO (Kubernetes AI Toolchain Operator) on AKS**: https://learn.microsoft.com/en-us/azure/aks/ai-toolchain-operator
- **Azure GPU VM Sizes**: https://learn.microsoft.com/en-us/azure/virtual-machines/sizes-gpu
- **Azure Container Instances**: https://learn.microsoft.com/en-us/azure/container-instances/
- **Azure Container Registry**: https://learn.microsoft.com/en-us/azure/container-registry/
- **Azure SDK GitHub Monorepo**: https://github.com/Azure/azure-sdk-for-python

### RunPod
- **Serverless Introduction**: https://docs.runpod.io/serverless/introduction
- **Sending Endpoint Requests**: https://docs.runpod.io/serverless/endpoints/send-requests
- **OpenAI API Compatibility**: https://docs.runpod.io/serverless/references/openai-api-compatibility
- **Python SDK**: https://docs.runpod.io/sdk/python
- **GraphQL API Reference**: https://docs.runpod.io/serverless/endpoints/graphql
- **API Keys & Credentials**: https://docs.runpod.io/references/api-keys
- **GPU Types**: https://docs.runpod.io/references/gpu-types
- **Pricing**: https://www.runpod.io/pricing

### Modal
- **vLLM Inference Example**: https://modal.com/docs/guide/ex/vllm_inference
- **Web Endpoints**: https://modal.com/docs/guide/webhooks
- **GPU Guide**: https://modal.com/docs/guide/gpu
- **GPU Reference API**: https://modal.com/docs/reference/modal.gpu
- **CLI Guide**: https://modal.com/docs/guide/cli
- **Secrets & Credentials**: https://modal.com/docs/guide/secrets
- **Scaling Out Guide**: https://modal.com/docs/guide/scale
- **Pricing**: https://modal.com/pricing

### vLLM
- **Official Documentation**: https://docs.vllm.ai
- **Installation Guide**: https://docs.vllm.ai/en/latest/getting_started/installation.html
- **Quickstart**: https://docs.vllm.ai/en/latest/getting_started/quickstart.html
- **Docker Deployment**: https://docs.vllm.ai/en/latest/serving/deploying_with_docker.html
- **OpenAI Compatible Server**: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html
- **Engine Arguments**: https://docs.vllm.ai/en/latest/configuration/engine_args.html
- **Server Arguments**: https://docs.vllm.ai/en/latest/configuration/serve_args.html
- **FP8 Quantization**: https://docs.vllm.ai/en/latest/quantization/fp8.html
- **GitHub Repository**: https://github.com/vllm-project/vllm

### NVIDIA NIM
- **NIM Overview Documentation**: https://docs.nvidia.com/nim/
- **NIM LLM Getting Started**: https://docs.nvidia.com/nim/llm/latest/getting-started.html
- **NIM Deployment Guide**: https://docs.nvidia.com/nim/llm/latest/deployment-guide.html
- **NIM API Reference**: https://docs.nvidia.com/nim/llm/latest/api-reference.html
- **NIM Support Matrix (GPU Requirements)**: https://docs.nvidia.com/nim/llm/latest/support-matrix.html
- **NIM Helm & Kubernetes Guide**: https://docs.nvidia.com/nim/llm/latest/helm-kubernetes.html
- **NVIDIA Build Catalog (Hosted APIs)**: https://build.nvidia.com
- **NVIDIA NGC Catalog**: https://catalog.ngc.nvidia.com

### FastAPI
- **Official Documentation**: https://fastapi.tiangolo.com
- **WebSocket Guide**: https://fastapi.tiangolo.com/advanced/websockets/

---

## 4. Phase 1 — Project Structure and Scaffolding

### Step 1.1: Create the Top-Level Project Directory

Create a directory called `LLMDEPLOYER` at your chosen location. All project files will live inside this directory.

### Step 1.2: Define the Overall Directory Structure

Create the following directory tree inside `LLMDEPLOYER`. Each folder and file is explained in later phases:

```
LLMDEPLOYER/
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI application entry point
│   ├── config.py                      # Environment variables and configuration
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── sessions.py                # Session management REST endpoints
│   │   ├── questions.py               # Questions list endpoint
│   │   ├── websocket.py               # WebSocket handler for streaming
│   │   └── health.py                  # Health check endpoint
│   ├── models/
│   │   ├── __init__.py
│   │   ├── session.py                 # Session data model (user answers, status)
│   │   ├── chat.py                    # Chat message models
│   │   ├── questions.py               # Question definition models
│   │   └── deployment.py              # Deployment configuration models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── session_manager.py         # Manages user sessions and answer collection
│   │   ├── question_flow.py           # Defines the question sequence and validation
│   │   ├── connection_manager.py      # Manages WebSocket connections per session
│   │   └── agent_orchestrator.py      # Interfaces with Claude Agent SDK
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base_adapter.py            # Abstract base class for all adapters
│   │   ├── azure_adapter.py           # Azure SDK operations (VM, AKS, ACA, ACR)
│   │   ├── runpod_adapter.py          # RunPod API operations
│   │   ├── modal_adapter.py           # Modal SDK operations
│   │   ├── vllm_deployer.py           # vLLM specific deployment logic
│   │   └── nim_deployer.py            # NVIDIA NIM specific deployment logic
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── tools.py                   # Tool definitions for Claude Agent SDK
│   │   ├── system_prompt.py           # Placeholder: loads system prompt from file
│   │   └── agent_runner.py            # Claude Agent SDK runner and event handler
│   └── utils/
│       ├── __init__.py
│       └── logger.py                  # Structured logging utility
├── system_prompt.txt                  # PLACEHOLDER FILE for the owner's system prompt
├── requirements.txt                   # Python dependencies
├── .env.example                       # Example environment variables file
├── Dockerfile                         # Backend Docker containerization
├── docker-compose.yml                 # Service + LiteLLM sidecar orchestration
├── litellm_config.yaml                # LiteLLM proxy configuration
├── .gitignore
└── README.md
```

Note: There is **no frontend directory**. This is a pure backend microservice that exposes REST APIs and WebSocket endpoints.

### Step 1.3: Initialize the Python Project

1. Navigate into the `LLMDEPLOYER` directory.
2. Create a Python virtual environment: `python3 -m venv venv` and activate it.
3. Create the `requirements.txt` file with these dependencies (one per line):
   - `fastapi` — Web framework (docs: https://fastapi.tiangolo.com)
   - `uvicorn[standard]` — ASGI server for FastAPI
   - `websockets` — WebSocket support for FastAPI
   - `claude-agent-sdk` — Claude Agent SDK (docs: https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk)
   - `anthropic` — Low-level Anthropic API client
   - `litellm` — Unified LLM gateway, OpenAI ↔ Anthropic translation (docs: https://docs.litellm.ai)
   - `httpx` — Async HTTP client for adapter API calls
   - `pydantic` — Data validation (bundled with FastAPI)
   - `pydantic-settings` — Settings management from environment variables
   - `python-dotenv` — Environment variable loading
   - `runpod` — RunPod SDK (docs: https://docs.runpod.io/sdk/python)
   - `modal` — Modal SDK (docs: https://modal.com/docs/reference/modal.App)
   - `azure-identity` — Azure authentication
   - `azure-mgmt-resource` — Azure resource group management
   - `azure-mgmt-compute` — Azure VM provisioning
   - `azure-mgmt-network` — Azure networking
   - `azure-mgmt-containerservice` — Azure AKS management
   - `azure-mgmt-appcontainers` — Azure Container Apps management
   - `azure-mgmt-containerregistry` — Azure Container Registry management
   - `azure-mgmt-containerinstance` — Azure Container Instances (legacy, CPU only)
   - `pyyaml` — YAML parsing for LiteLLM config
4. Install dependencies: `pip install -r requirements.txt`

---

## 5. Phase 2 — FastAPI Server and REST API Surface

### Step 2.1: Application Entry Point (main.py)

1. Create `app/main.py`.
2. Initialize a FastAPI application instance with:
   - `title="LLMDeployer API"`
   - `description="Headless microservice for intelligent LLM deployment orchestration"`
   - `version="1.0.0"`
3. Add CORS middleware to allow requests from any origin (since this is a microservice consumed by various clients). Allow all methods, all headers, and credentials.
4. Include the routers: `sessions.router` (prefix "/api"), `questions.router` (prefix "/api"), `websocket.router` (prefix "/api"), and `health.router` (prefix "/api").
5. Add a startup event handler that:
   - Initializes the session manager.
   - Validates that the `ANTHROPIC_API_KEY` environment variable is set.
   - Logs the configured deployment adapters (which providers have credentials set).
   - Optionally starts the LiteLLM proxy as a background subprocess (or documents that it runs as a sidecar via Docker Compose — see Phase 3).
6. Add a shutdown event handler that cleans up any active WebSocket connections and running agent tasks.
7. Reference: https://fastapi.tiangolo.com

### Step 2.2: Configuration Module (config.py)

1. Create `app/config.py`.
2. Use `pydantic-settings` (`from pydantic_settings import BaseSettings`) to define a `Settings` class that loads environment variables:
   - `ANTHROPIC_API_KEY: str` — Required
   - `LITELLM_PROXY_URL: str = "http://localhost:4000"` — URL of the LiteLLM proxy sidecar
   - `AZURE_TENANT_ID: str = ""` — Optional (for Azure deployments)
   - `AZURE_CLIENT_ID: str = ""` — Optional
   - `AZURE_CLIENT_SECRET: str = ""` — Optional
   - `AZURE_SUBSCRIPTION_ID: str = ""` — Optional
   - `RUNPOD_API_KEY: str = ""` — Optional (for RunPod deployments)
   - `MODAL_TOKEN_ID: str = ""` — Optional (for Modal deployments)
   - `MODAL_TOKEN_SECRET: str = ""` — Optional (for Modal deployments)
   - `NGC_API_KEY: str = ""` — Optional (for NVIDIA NIM deployments)
   - `HUGGING_FACE_HUB_TOKEN: str = ""` — Optional (for gated models)
   - `SYSTEM_PROMPT_PATH: str = "system_prompt.txt"` — Path to the system prompt file
   - `CLAUDE_MODEL: str = "claude-sonnet-4-20250514"` — Model to use for the agent
3. Use `python-dotenv` to load from a `.env` file by setting `model_config = SettingsConfigDict(env_file=".env")` in the Settings class.
4. Create a singleton function `get_settings()` that returns a cached `Settings` instance. Use `@lru_cache` for caching.

### Step 2.3: Data Models (models/)

#### models/questions.py
1. Define a Pydantic model `Question` with fields:
   - `id: str` — Unique identifier (e.g., "purpose", "concurrent_users")
   - `question: str` — The full question text
   - `type: str` — One of: "text", "select", "multi_select", "number"
   - `options: Optional[list[str]]` — Options for select/multi_select types
   - `placeholder: Optional[str]` — Placeholder text for text/number inputs
   - `validation: Optional[str]` — Validation rule description
   - `required: bool = True`

#### models/session.py
1. Define a Pydantic model `UserRequirements` with fields matching the collected answers:
   - `purpose: str`
   - `concurrent_users: int`
   - `peak_capacity: int`
   - `business_context: str`
   - `compliance: list[str]`
   - `model_preference: str`
   - `latency_requirements: str`
   - `budget_constraints: str`
2. Define a `Session` model with:
   - `session_id: str` (UUID4 string)
   - `created_at: datetime`
   - `status: str` (enum: "created", "collecting", "analyzing", "deploying", "completed", "failed")
   - `requirements: Optional[UserRequirements]`
   - `deployment_result: Optional[dict]`
   - `messages: list[dict]` (chat history — all agent messages and status updates)

#### models/chat.py
1. Define `ChatMessage` model with: `id: str`, `text: str`, `sender: str` (enum: "user", "assistant", "system"), `timestamp: datetime`, `message_type: str` (enum: "agent_message", "status_update", "error", "deployment_complete").
2. Define `WebSocketMessage` model with: `type: str`, `payload: dict`.

#### models/deployment.py
1. Define `DeploymentConfig` model with:
   - `strategy: str` (enum: "runpod_serverless", "modal_serverless", "vllm_azure_vm", "vllm_azure_aks", "vllm_azure_aca", "nim_azure_aks", "nim_azure_aca", "nim_azure_vm")
   - `cloud_provider: str` (fixed to "azure" for MVP)
   - `model_name: str`
   - `gpu_type: str`
   - `gpu_count: int`
   - `region: str`
   - `scaling_config: dict` (min/max replicas, autoscaling rules)
   - `optimization_flags: dict` (vLLM specific flags like tensor_parallel_size, quantization, etc.)

### Step 2.4: Session Manager (services/session_manager.py)

1. Create an in-memory session store (a Python dictionary mapping session_id to Session objects). For the MVP, this is sufficient; note that production would use Redis or a database.
2. Implement methods:
   - `create_session() -> Session` — Generates a UUID4 session_id, creates and stores a new Session with status "created", returns it.
   - `get_session(session_id: str) -> Session` — Retrieves a session by ID or raises HTTPException 404.
   - `update_requirements(session_id: str, requirements: UserRequirements)` — Stores the collected answers in the session.
   - `update_status(session_id: str, status: str)` — Updates the session status.
   - `add_message(session_id: str, message: ChatMessage)` — Appends a message to the session's messages list.
   - `get_messages(session_id: str) -> list[ChatMessage]` — Returns all messages for a session.
   - `list_sessions() -> list[Session]` — Returns all sessions (for admin/debug purposes).

### Step 2.5: Question Flow Service (services/question_flow.py)

1. Define the list of questions as a Python list of `Question` model instances. This is the single source of truth for what the microservice asks the user. The external consumer retrieves this list via the `GET /api/questions` endpoint and presents them however it wants.
2. The predefined questions MUST include at minimum:
   - **"What is the purpose of this LLM deployment?"** — id: `purpose`, type: `select`, options: ["Agentic Coding", "General Usage", "Customer Support / Chatbot", "Internal Knowledge Base", "Content Generation", "Code Review & Analysis", "Other (please describe)"]
   - **"How many people will be using it simultaneously?"** — id: `concurrent_users`, type: `number`, validation: "Positive integer"
   - **"What is the expected peak capacity of clients?"** — id: `peak_capacity`, type: `number`, validation: "Positive integer, must be >= simultaneous users"
   - **"Describe the business context for this deployment."** — id: `business_context`, type: `text`, placeholder: "e.g., We are a fintech startup needing to process customer queries..."
   - **"Are there any compliance requirements that need to be guaranteed?"** — id: `compliance`, type: `multi_select`, options: ["HIPAA", "SOC 2", "GDPR", "PCI DSS", "FedRAMP", "Data Residency (specify region)", "No specific compliance requirements", "Other (please describe)"]
   - **"Which LLM model do you prefer to deploy?"** — id: `model_preference`, type: `text`, placeholder: "e.g., Llama 3.1 70B, Qwen 2.5 72B, Mistral Large, etc."
   - **"What are your latency requirements?"** — id: `latency_requirements`, type: `select`, options: ["Ultra-low (<100ms TTFT)", "Low (<500ms TTFT)", "Moderate (<2s TTFT)", "Flexible / Batch processing"]
   - **"What is your monthly budget range for this deployment?"** — id: `budget_constraints`, type: `select`, options: ["< $500/month", "$500 - $2,000/month", "$2,000 - $10,000/month", "> $10,000/month", "Flexible / No hard limit"]
3. Implement `get_questions() -> list[Question]` that returns the full question list.
4. Implement `compile_requirements(answers: dict) -> UserRequirements` that takes a raw answers dict (keyed by question ID), validates all required fields are present, validates types (e.g., concurrent_users is a positive integer), and transforms it into a `UserRequirements` Pydantic model. Raise `HTTPException 422` with descriptive errors if validation fails.

### Step 2.6: Connection Manager (services/connection_manager.py)

1. Create a `ConnectionManager` class that manages WebSocket connections per session:
   - `active_connections: dict[str, list[WebSocket]]` — Maps session_id to a list of connected WebSockets.
   - `async connect(session_id: str, websocket: WebSocket)` — Accepts the WebSocket and registers it under the session_id.
   - `disconnect(session_id: str, websocket: WebSocket)` — Removes a WebSocket from the session's list.
   - `async send_to_session(session_id: str, message: dict)` — Serializes the message as JSON and sends it to ALL WebSocket connections registered for the given session_id. Also calls `session_manager.add_message()` to persist the message for the polling endpoint.
   - `async broadcast(message: dict)` — Sends a message to all connected WebSockets across all sessions (for system-wide announcements).
2. Create a singleton instance of `ConnectionManager` that is imported by both the WebSocket router and the agent orchestrator.

### Step 2.7: Sessions Router (routers/sessions.py)

1. Define a FastAPI `APIRouter`.
2. Implement these REST endpoints:

   **`POST /sessions`**
   - Creates a new session via `session_manager.create_session()`.
   - Returns `{"session_id": "...", "status": "created"}`.

   **`GET /sessions/{session_id}`**
   - Returns the full session object (session_id, status, requirements, messages, deployment_result, created_at).

   **`POST /sessions/{session_id}/answers`**
   - Accepts a JSON body: `{"answers": {"purpose": "...", "concurrent_users": 50, ...}}`.
   - Calls `question_flow.compile_requirements(answers)` to validate and transform into `UserRequirements`.
   - Stores in session via `session_manager.update_requirements()`.
   - Updates status to "analyzing".
   - Triggers the agent orchestrator asynchronously: `asyncio.create_task(orchestrate_deployment(session_id))`.
   - Returns `{"status": "analyzing", "message": "Requirements received. Deployment analysis started. Connect via WebSocket at /api/ws/{session_id} for real-time updates, or poll GET /api/sessions/{session_id}/messages."}`.

   **`GET /sessions/{session_id}/status`**
   - Returns `{"session_id": "...", "status": "...", "deployment_result": {...} or null}`.

   **`GET /sessions/{session_id}/messages`**
   - Returns `{"messages": [...]}` — the full list of ChatMessage objects for the session.
   - Supports an optional query parameter `after_index` (integer) so the consumer can poll for only new messages since the last fetch. If `after_index` is provided, return only messages with index > after_index.

   **`POST /sessions/{session_id}/message`**
   - Accepts `{"text": "..."}` — an additional user message sent mid-deployment (e.g., "Please use a cheaper GPU" or "Switch to us-east-1 region").
   - Stores the message in the session and forwards it to the running agent (if supported by the agent SDK's session resumption feature).
   - Returns `{"status": "received"}`.

### Step 2.8: Questions Router (routers/questions.py)

1. Define a `GET /questions` endpoint that returns the full list of questions from `question_flow.get_questions()`.
2. The response format: `{"questions": [{"id": "purpose", "question": "What is the purpose...", "type": "select", "options": [...], ...}, ...]}`.
3. This allows any frontend or consumer to dynamically render the question flow without hardcoding.

### Step 2.9: WebSocket Router (routers/websocket.py)

1. Define a WebSocket endpoint: `@router.websocket("/ws/{session_id}")`.
2. On connection:
   - Verify the session_id exists via `session_manager.get_session()`. If not found, close the WebSocket with code 4004 and reason "Session not found".
   - Call `connection_manager.connect(session_id, websocket)`.
   - Send an initial message: `{"type": "connected", "payload": {"session_id": "...", "status": "<current_session_status>"}}`.
3. In the receive loop:
   - Listen for incoming messages from the client.
   - If the client sends a text message, parse it as JSON. If it has `type: "user_message"`, forward the text to the agent (via `session_manager.add_message()` and potentially the agent's session).
   - Handle `WebSocketDisconnect` exception: call `connection_manager.disconnect(session_id, websocket)`.
4. The connection_manager's `send_to_session()` method (called by the agent orchestrator) pushes messages to all connected WebSockets for a session. Message types sent to the client:
   - `{"type": "agent_message", "payload": {"text": "...", "timestamp": "..."}}` — Agent reasoning/response text.
   - `{"type": "status_update", "payload": {"status": "deploying", "detail": "Provisioning Azure GPU VM..."}}` — Deployment progress.
   - `{"type": "error", "payload": {"message": "...", "detail": "..."}}` — Error messages.
   - `{"type": "deployment_complete", "payload": {"endpoint_url": "...", "resource_ids": [...], "strategy": "..."}}` — Final result.

### Step 2.10: Health Router (routers/health.py)

1. Define a `GET /health` endpoint that returns:
   - `status`: "healthy"
   - `version`: "1.0.0"
   - `providers`: An object showing which deployment providers are configured (have credentials set). Example: `{"azure": true, "runpod": false, "modal": true, "nim": false}`. Check this by testing if the corresponding environment variables are non-empty.
   - `litellm_proxy`: Whether the LiteLLM proxy is reachable (make a quick HTTP GET to `{LITELLM_PROXY_URL}/health`).
2. This gives consumers a quick way to verify the service is up and which providers are available.

---

## 6. Phase 3 — OpenAI-to-Claude Translation Layer (LiteLLM)

### Purpose

Instead of building a custom translation layer from scratch, use **LiteLLM** — an established, production-grade open-source project that provides a unified OpenAI-compatible API gateway for 100+ LLM providers, including Anthropic Claude. LiteLLM handles all the bidirectional format translation (OpenAI ↔ Anthropic), streaming SSE conversion, tool/function calling translation, and error mapping automatically.

### Why LiteLLM (and alternatives)

There are several open-source projects that provide this translation capability (see Appendix D for a full list). **LiteLLM is recommended** because:
- It is the most mature and actively maintained project (15k+ GitHub stars).
- It supports both **Python SDK usage** (import and call directly in code) and a **standalone proxy server** mode.
- It handles the full translation surface: messages, tools, streaming, error codes, token counting.
- It supports 100+ providers, so if you add AWS Bedrock, Google Vertex, or Ollama in the future, no code changes are needed.
- It has built-in features useful for production: cost tracking, rate limiting, fallback routing, load balancing, virtual API keys.

**However**, if you prefer a lighter-weight alternative, you may use any of the repos listed in Appendix D. The architecture is the same — the translation layer sits between the Claude Agent SDK and any OpenAI-compatible endpoint.

### Step 3.1: LiteLLM as a Python SDK (Embedded Mode)

The simplest integration is to use LiteLLM directly as a Python library within the microservice. This requires no separate process.

1. LiteLLM is already in `requirements.txt` (`pip install litellm`).
2. To call any OpenAI-compatible endpoint through LiteLLM (translating to Claude format or vice versa), you use the `litellm.completion()` function. LiteLLM auto-detects the provider from the model name prefix:
   - Model names prefixed with `anthropic/` route to the Anthropic API (e.g., `anthropic/claude-sonnet-4-20250514`).
   - Model names prefixed with `openai/` route to the OpenAI API.
   - Model names prefixed with `azure/` route to Azure OpenAI.
   - Model names prefixed with `ollama/` or `vllm/` can route to local/self-hosted endpoints.
   - Custom base URLs can be set via the `api_base` parameter for vLLM/NIM endpoints.
3. In the agent tools (Phase 4), when the Claude agent wants to test or validate a deployed endpoint, use `litellm.completion(model="openai/<model_name>", api_base="<deployed_endpoint_url>", messages=[...])` to call the deployed vLLM/NIM endpoint through the unified interface.
4. Reference: https://docs.litellm.ai/docs/

### Step 3.2: LiteLLM as a Proxy Sidecar (Production Mode)

For production, run LiteLLM as a separate proxy server (sidecar) alongside the microservice. This approach is preferred because:
- It decouples the translation layer from the microservice process.
- It provides a single OpenAI-compatible URL (`http://litellm:4000/v1/chat/completions`) that any component can call.
- It enables centralized cost tracking, rate limiting, and API key management.
- It can serve as the bridge for the Claude Agent SDK to call any OpenAI-compatible endpoint.

1. Create `litellm_config.yaml` at the project root. This YAML file configures which models LiteLLM can route to. Define at minimum:
   - An Anthropic Claude model entry pointing to the Anthropic API.
   - A "custom" entry template for dynamically deployed vLLM/NIM endpoints (the agent will configure these at runtime).
   - The config file structure follows the LiteLLM proxy configuration spec documented at https://docs.litellm.ai/docs/simple_proxy.
   - The YAML should define a `model_list` array where each entry has a `model_name` (the alias clients use), `litellm_params.model` (the provider-prefixed model name), and optionally `litellm_params.api_base` for custom endpoints.
2. In `docker-compose.yml`, add a `litellm` service:
   - Image: `ghcr.io/berriai/litellm:main-latest` (official LiteLLM Docker image).
   - Mount `litellm_config.yaml` to `/app/config.yaml` inside the container.
   - Command: `--config /app/config.yaml --port 4000`.
   - Pass `ANTHROPIC_API_KEY` as an environment variable.
   - Expose port 4000 internally (no need to expose externally unless debugging).
   - Reference: https://docs.litellm.ai/docs/simple_proxy
3. In `app/config.py`, the `LITELLM_PROXY_URL` setting (default `http://localhost:4000`) points to this sidecar. When running via Docker Compose, set it to `http://litellm:4000`.
4. The microservice can now make calls to `{LITELLM_PROXY_URL}/v1/chat/completions` using the standard OpenAI SDK format, and LiteLLM will handle routing to the correct provider with full format translation.

### Step 3.3: How the Claude Agent SDK Uses the Translation Layer

1. When the Claude agent needs to **call an OpenAI-compatible endpoint** (e.g., to test a deployed vLLM server, to verify a NIM endpoint is healthy, or to use an Azure OpenAI model for a sub-task), it invokes a custom tool (defined in Phase 4) that internally calls `litellm.completion()` with the appropriate model name and `api_base`.
2. LiteLLM handles all format conversion:
   - If calling a vLLM endpoint: LiteLLM sends the request in OpenAI format directly (vLLM is natively OpenAI-compatible).
   - If calling through the proxy: LiteLLM resolves the model name to the configured provider and translates accordingly.
3. This means the Claude Agent SDK does NOT need to know about OpenAI vs Anthropic format differences at all — LiteLLM abstracts it away.

---

## 7. Phase 4 — Claude Agent SDK Integration

### Step 4.1: Install and Configure the SDK

1. The package `claude-agent-sdk` should already be in `requirements.txt` (from Phase 1). Verify it is installed.
2. Ensure the `ANTHROPIC_API_KEY` environment variable is set. The SDK automatically detects it.
3. The SDK requires Python 3.10+. It bundles and manages the Claude Code agent runtime binary internally — no separate CLI installation is needed.
4. Reference: https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk and https://github.com/anthropics/claude-agent-sdk-python

### Step 4.2: Define Agent Tools (agent/tools.py)

1. Create tool definitions that the Claude agent can invoke during its planning and execution loop. Each tool is a Python async function decorated with `@tool` from the Claude Agent SDK.
2. Define the following tools:

   **Tool: `analyze_requirements`**
   - Description: "Analyze the user's LLM deployment requirements and determine the optimal deployment strategy."
   - Input schema: `requirements` (a JSON object containing all collected user answers).
   - This tool does not perform external actions; it structures the requirements for the agent's reasoning. The agent uses this tool's output alongside the system prompt to decide the deployment path.
   - Return: A structured summary of the requirements analysis.

   **Tool: `deploy_runpod_serverless`**
   - Description: "Deploy an LLM model as a serverless endpoint on RunPod. Creates a vLLM-powered serverless endpoint with auto-scaling."
   - Input schema: `model_name` (string), `gpu_type` (string), `max_workers` (integer), `idle_timeout` (integer).
   - Implementation: Calls the RunPod adapter (Phase 7).
   - Return: Endpoint ID, endpoint URL, and status.

   **Tool: `deploy_modal_serverless`**
   - Description: "Deploy an LLM model as a serverless GPU function on Modal. Creates a vLLM-backed inference endpoint with auto-scaling."
   - Input schema: `model_name` (string), `gpu_type` (string), `max_containers` (integer), `container_idle_timeout` (integer).
   - Implementation: Calls the Modal adapter (Phase 8).
   - Return: Deployed app URL and status.

   **Tool: `deploy_vllm_on_azure`**
   - Description: "Deploy a vLLM inference server on Azure infrastructure. Supports deployment via Azure VMs with GPU, Azure Kubernetes Service (AKS) with GPU node pools, or Azure Container Apps with serverless GPU."
   - Input schema: `model_name` (string), `deployment_target` (string: "vm", "aks", or "aca"), `gpu_vm_size` (string), `gpu_count` (integer), `region` (string), `optimization_flags` (JSON object with vLLM flags like tensor_parallel_size, quantization, enable_prefix_caching, etc.).
   - Implementation: Calls the Azure adapter (Phase 6) combined with the vLLM deployer (Phase 9).
   - Return: Deployment endpoint URL, resource IDs, and status.

   **Tool: `deploy_nim_on_azure`**
   - Description: "Deploy an NVIDIA NIM container for LLM inference on Azure infrastructure. Supports deployment via AKS with GPU node pools, Azure Container Apps, or Azure VMs."
   - Input schema: `model_name` (string), `nim_image` (string: the nvcr.io image path), `deployment_target` (string: "aks", "aca", or "vm"), `gpu_vm_size` (string), `gpu_count` (integer), `region` (string).
   - Implementation: Calls the Azure adapter (Phase 6) combined with the NIM deployer (Phase 10).
   - Return: Deployment endpoint URL, resource IDs, and status.

   **Tool: `check_deployment_status`**
   - Description: "Check the current status of an active deployment. Returns health check results, endpoint readiness, and resource utilization."
   - Input schema: `deployment_id` (string), `provider` (string: "azure", "runpod", "modal").
   - Implementation: Calls the appropriate adapter's status check method.
   - Return: Status string, health check results, and any error details.

   **Tool: `estimate_cost`**
   - Description: "Estimate the monthly cost of a proposed deployment configuration. Returns approximate pricing breakdown."
   - Input schema: `strategy` (string), `gpu_type` (string), `gpu_count` (integer), `hours_per_day` (number), `provider` (string).
   - Implementation: Uses hardcoded pricing tables (from RunPod/Modal/Azure pricing pages) to calculate estimates.
   - Return: Estimated monthly cost, pricing breakdown, and comparison with alternative strategies.

   **Tool: `test_deployed_endpoint`**
   - Description: "Send a test inference request to a deployed LLM endpoint to verify it is working correctly. Uses LiteLLM to call the endpoint in OpenAI-compatible format."
   - Input schema: `endpoint_url` (string), `model_name` (string), `test_prompt` (string), `api_key` (optional string).
   - Implementation: Uses `litellm.completion(model="openai/{model_name}", api_base=endpoint_url, messages=[{"role": "user", "content": test_prompt}])` to send a test request through the translation layer. This works for both vLLM and NIM endpoints since they both expose OpenAI-compatible APIs.
   - Return: Success/failure status, response text, latency metrics.

3. Register all tools with the Claude Agent SDK via the `allowed_tools` list or `@tool` decorators as documented at https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk.

### Step 4.3: System Prompt Loader (agent/system_prompt.py)

1. Create a module that reads the system prompt from the file specified by `Settings.SYSTEM_PROMPT_PATH` (default: `system_prompt.txt`).
2. The function `load_system_prompt() -> str` should:
   - Read the file content.
   - If the file does not exist, return a minimal default prompt: "You are LLMDeployer, an expert at analyzing LLM deployment requirements and selecting the optimal deployment strategy. Analyze the user's requirements and execute the deployment using the available tools."
   - The actual system prompt will be written by the owner separately. The code should just load whatever is in the file.
3. Create the `system_prompt.txt` placeholder file in the project root with a comment: "PLACEHOLDER: Replace this content with your custom system prompt that guides the deployment decision logic."

### Step 4.4: Agent Runner (agent/agent_runner.py)

1. Create an async function `run_deployment_agent(session_id: str, requirements: UserRequirements, on_message: Callable, on_status: Callable)`:
   - `on_message` is an async callback that sends text messages to the session (stored + pushed via WebSocket).
   - `on_status` is an async callback that sends status updates to the session.
2. Inside this function:
   - Load the system prompt using `load_system_prompt()`.
   - Create `ClaudeAgentOptions` with:
     - `system_prompt`: The loaded system prompt, with the user requirements appended as a structured JSON block at the end (e.g., "The user has provided the following deployment requirements: {json.dumps(requirements.dict())}").
     - `model`: The model from `Settings.CLAUDE_MODEL` (default: "claude-sonnet-4-20250514").
     - `allowed_tools`: The list of custom tool names defined in `tools.py`.
   - Create a `ClaudeSDKClient` with the options.
   - Call `client.run(prompt)` where the prompt is a concise instruction like "Analyze the deployment requirements provided in the system prompt and execute the optimal deployment strategy using the available tools. Explain your reasoning at each step."
   - Iterate over the streamed event messages:
     - `TextMessage`: Call `await on_message(text_content)` to relay the agent's reasoning/response to the session.
     - `ToolUseMessage`: Call `await on_status(f"Executing: {tool_name}")` to notify which action the agent is taking.
     - `ToolResultMessage`: Call `await on_status(f"Completed: {tool_name}")` and optionally relay the result summary.
     - `ResultMessage`: Call `await on_message(final_text)` and `await on_status("deployment_complete")`.
   - Handle errors gracefully: if the agent loop fails, call `await on_status("failed")` and `await on_message("Deployment failed: {error_details}")`.
3. Reference: Claude Agent SDK event types and streaming patterns at https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk

### Step 4.5: Agent Orchestrator (services/agent_orchestrator.py)

1. Create the high-level orchestration function `async orchestrate_deployment(session_id: str)`:
   - Retrieves the session from `session_manager`.
   - Gets the `UserRequirements` from the session.
   - Updates session status to "deploying".
   - Defines the `on_message` async callback: creates a `ChatMessage` with sender="assistant" and message_type="agent_message", then calls `await connection_manager.send_to_session(session_id, {"type": "agent_message", "payload": {"text": message, "timestamp": "..."}})` and `session_manager.add_message(session_id, chat_message)`.
   - Defines the `on_status` async callback: creates a `ChatMessage` with sender="system" and message_type="status_update", then calls `await connection_manager.send_to_session(session_id, {"type": "status_update", "payload": {"status": status}})` and `session_manager.update_status(session_id, status)`.
   - Calls `await run_deployment_agent(session_id, requirements, on_message, on_status)`.
   - On completion, updates session status to "completed" and stores the deployment result in the session.
   - On failure, updates session status to "failed" with error details.
2. This function is called as an `asyncio.create_task` from the sessions router when answers are submitted (Step 2.7).

### Step 4.6: Human-in-the-Loop Security Gate

1. Implement a `can_use_tool` async callback function that intercepts tool invocations before they execute:
   - Allow `analyze_requirements`, `estimate_cost`, and `test_deployed_endpoint` without restriction (read-only / non-destructive operations).
   - For all deployment tools (`deploy_runpod_serverless`, `deploy_modal_serverless`, `deploy_vllm_on_azure`, `deploy_nim_on_azure`), log the tool invocation details and allow execution. In a production system, this would be where you add approval workflows.
   - Deny any tool invocations that contain obviously dangerous shell commands (if the agent somehow tries to run arbitrary bash).
2. Pass this callback to `ClaudeAgentOptions(can_use_tool=security_gate)`.
3. Reference: Claude Agent SDK permission gating at https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk

---

## 8. Phase 5 — Deployment Decision Engine (System Prompt Placeholder)

### Step 5.1: System Prompt File

1. Create `system_prompt.txt` at the project root with a clear placeholder header.
2. The file content should be a placeholder comment explaining that the owner will write the actual system prompt. Include a brief description of what the system prompt should cover:
   - The prompt should instruct the Claude agent on how to analyze user requirements.
   - The prompt should define the decision tree/logic for choosing between deployment strategies.
   - The prompt should specify when to choose RunPod serverless (e.g., low-scale, cost-sensitive, flexible latency).
   - The prompt should specify when to choose Modal serverless (e.g., rapid iteration, Python-native workflows, moderate scale).
   - The prompt should specify when to choose vLLM on Azure (e.g., high throughput, custom optimization, data sovereignty/compliance, self-hosted control).
   - The prompt should specify when to choose NVIDIA NIM on Azure (e.g., enterprise-grade, optimized TensorRT performance, specific GPU architectures like Hopper/Blackwell).
   - The prompt should guide the agent on which Azure deployment target to select (VM vs AKS vs ACA) based on scale and management preferences.
   - The prompt should instruct the agent on which vLLM optimization flags to apply based on model size, GPU type, and latency requirements (see Appendix C for the flag reference).
3. The code in `system_prompt.py` simply reads this file. No decision logic is hardcoded in the application code.

---

## 9. Phase 6 — Azure Infrastructure Adapter

### Step 6.1: Base Adapter (adapters/base_adapter.py)

1. Define an abstract base class `BaseAdapter` with:
   - Abstract method `async deploy(config: DeploymentConfig) -> dict` — Executes the deployment.
   - Abstract method `async check_status(deployment_id: str) -> dict` — Checks deployment status.
   - Abstract method `async teardown(deployment_id: str) -> dict` — Tears down the deployment.
   - Concrete method `validate_config(config: DeploymentConfig) -> bool` — Validates the deployment config has all required fields.

### Step 6.2: Azure Adapter (adapters/azure_adapter.py)

1. Create the `AzureAdapter` class extending `BaseAdapter`.
2. In the constructor, initialize the Azure SDK clients using `DefaultAzureCredential`:
   - Import `DefaultAzureCredential` from `azure.identity`.
   - Create a credential instance. The SDK will automatically detect credentials from environment variables (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`) or Azure CLI login or managed identity.
   - Initialize the following management clients using the credential and `AZURE_SUBSCRIPTION_ID`:
     - `ResourceManagementClient` from `azure.mgmt.resource`
     - `ComputeManagementClient` from `azure.mgmt.compute`
     - `NetworkManagementClient` from `azure.mgmt.network`
     - `ContainerServiceClient` from `azure.mgmt.containerservice`
     - `ContainerAppsAPIClient` from `azure.mgmt.appcontainers`
     - `ContainerRegistryManagementClient` from `azure.mgmt.containerregistry`
   - Reference: https://learn.microsoft.com/en-us/python/api/overview/azure/identity-README

3. Implement the following methods:

   **Method: `create_resource_group(name: str, location: str, tags: dict) -> dict`**
   - Use `resource_client.resource_groups.create_or_update(name, {"location": location, "tags": tags})`.
   - Return the resource group properties.

   **Method: `create_virtual_network(resource_group: str, vnet_name: str, location: str, address_prefix: str, subnet_name: str, subnet_prefix: str) -> dict`**
   - Create a VirtualNetwork object with the address space.
   - Call `network_client.virtual_networks.begin_create_or_update(...)`.
   - Then create a Subnet using `network_client.subnets.begin_create_or_update(...)`.
   - Wait for both operations to complete using `.result()`.
   - Return the VNet and subnet IDs.

   **Method: `create_container_registry(resource_group: str, registry_name: str, location: str, sku: str = "Premium") -> dict`**
   - Use `acr_client.registries.begin_create(resource_group, registry_name, Registry(location=location, sku=Sku(name=sku), admin_user_enabled=False))`.
   - Wait for completion with `.result()`.
   - Return the registry login server URL.
   - Reference: https://learn.microsoft.com/en-us/azure/container-registry/

   **Method: `provision_gpu_vm(resource_group: str, vm_name: str, location: str, vm_size: str, image_reference: dict, nic_id: str) -> dict`**
   - Create a VirtualMachine config with `HardwareProfile(vm_size=vm_size)` (use GPU VM sizes like "Standard_NC6s_v3", "Standard_NC24ads_A100_v4", "Standard_NCads_H100_v5").
   - Set the StorageProfile with the specified image reference (typically Ubuntu 24.04 LTS from Canonical).
   - Set the OSProfile with admin username and SSH key (or password for MVP).
   - Set the NetworkProfile with the provided NIC ID.
   - Call `compute_client.virtual_machines.begin_create_or_update(...)`.
   - After VM creation, install the NVIDIA GPU driver extension by calling `compute_client.virtual_machine_extensions.begin_create_or_update(...)` with publisher `"Microsoft.HpcCompute"`, type `"NvidiaGpuDriverLinux"`, version `"1.6"`.
   - Wait for both operations. Return the VM ID and public IP.
   - Reference: https://learn.microsoft.com/en-us/azure/virtual-machines/sizes-gpu

   **Method: `create_aks_cluster(resource_group: str, cluster_name: str, location: str, gpu_vm_size: str, gpu_node_count: int, min_count: int, max_count: int) -> dict`**
   - Create a system node pool (CPU, for cluster infrastructure) and a GPU node pool.
   - For the GPU node pool, use `AgentPool(count=gpu_node_count, vm_size=gpu_vm_size, os_type="Linux", mode="User", node_taints=["sku=gpu:NoSchedule"], node_labels={"accelerator": "nvidia-gpu"}, enable_auto_scaling=True, min_count=min_count, max_count=max_count)`.
   - Call `aks_client.managed_clusters.begin_create_or_update(...)` for the cluster, then `aks_client.agent_pools.begin_create_or_update(...)` for the GPU pool.
   - Return the cluster FQDN and kubeconfig access details.
   - Reference: https://learn.microsoft.com/en-us/azure/aks/gpu-cluster

   **Method: `deploy_container_app(resource_group: str, app_name: str, location: str, environment_id: str, container_image: str, container_args: list, target_port: int, min_replicas: int, max_replicas: int) -> dict`**
   - Create a ContainerApp definition with the specified container image, arguments, ingress configuration (external=True, target_port), and scaling rules.
   - Call `app_client.container_apps.begin_create_or_update(...)`.
   - Return the app FQDN endpoint URL.
   - IMPORTANT NOTE: Azure Container Apps supports serverless GPU workloads (NVIDIA A100 80GB and T4) within Consumption Workload Profiles. Verify GPU availability in the target region.
   - Reference: https://learn.microsoft.com/en-us/azure/container-apps/gpu-workloads

   **Method: `check_status(deployment_id: str) -> dict`**
   - Based on the deployment type (parsed from the deployment_id format), query the appropriate Azure resource's provisioning state.
   - For VMs: `compute_client.virtual_machines.get(...)` and check `provisioning_state`.
   - For AKS: `aks_client.managed_clusters.get(...)` and check `provisioning_state` and `power_state`.
   - For Container Apps: `app_client.container_apps.get(...)` and check `provisioning_state`.
   - Return a status dict with the state and any relevant details.

---

## 10. Phase 7 — RunPod Serverless Adapter

### Step 7.1: RunPod Adapter (adapters/runpod_adapter.py)

1. Create the `RunPodAdapter` class extending `BaseAdapter`.
2. In the constructor:
   - Import the `runpod` SDK.
   - Set `runpod.api_key` from `Settings.RUNPOD_API_KEY`.
   - Reference: https://docs.runpod.io/sdk/python

3. Implement the following methods:

   **Method: `deploy(config: DeploymentConfig) -> dict`**
   - Create a serverless endpoint using RunPod's GraphQL API.
   - Send a GraphQL mutation to `https://api.runpod.io/graphql` with the query parameter `api_key`. The mutation should be `saveEndpoint` with inputs:
     - `name`: A descriptive name derived from the model name (e.g., "llmdeployer-llama3-70b").
     - `templateId`: The ID of a pre-configured vLLM template on RunPod. For MVP, this can be a known vLLM template ID or a custom one. Document that the user needs to create a template first via the RunPod UI or provide the template ID.
     - `gpuIds`: Map the requested GPU type to RunPod GPU identifiers (e.g., "AMPERE_80" for A100 80GB, "ADA_24" for RTX 4090, "HOPPER_80" for H100). Reference: https://docs.runpod.io/references/gpu-types
     - `workersMin`: 0 (for true serverless, scale to zero).
     - `workersMax`: Derived from the scaling config (e.g., peak_capacity / estimated_requests_per_worker).
     - `idleTimeout`: 5 seconds (configurable).
     - `scalerType`: "QUEUE_DELAY".
     - `scalerValue`: 4 (seconds of queue delay before scaling up).
   - Use `httpx.AsyncClient` to send the GraphQL request.
   - Parse the response to extract the endpoint ID.
   - Construct the endpoint URL: `https://api.runpod.ai/v2/{endpoint_id}/openai/v1/chat/completions`.
   - Return `{"endpoint_id": "...", "endpoint_url": "...", "status": "created"}`.
   - Reference: https://docs.runpod.io/serverless/endpoints/graphql

   **Method: `check_status(deployment_id: str) -> dict`**
   - Send a GET request to `https://api.runpod.ai/v2/{deployment_id}/health` with the API key header.
   - Parse the health response which includes `workers` (idle, running, throttled counts) and `jobs` (completed, failed, in_progress, in_queue, retried).
   - Return a status summary.
   - Reference: https://docs.runpod.io/serverless/endpoints/send-requests

   **Method: `teardown(deployment_id: str) -> dict`**
   - Send a GraphQL mutation to delete the endpoint.
   - Return confirmation.

---

## 11. Phase 8 — Modal Serverless Adapter

### Step 8.1: Modal Adapter (adapters/modal_adapter.py)

1. Create the `ModalAdapter` class extending `BaseAdapter`.
2. Modal works differently from RunPod — it is a Python-code-first platform. You define your inference logic as Python code with Modal decorators, and then deploy it using `modal deploy`.
3. The adapter cannot directly "call an API to create endpoints" like RunPod. Instead, it must:
   - Dynamically generate a Modal deployment Python script based on the configuration.
   - Execute `modal deploy <script.py>` as a subprocess to deploy it.
   - Parse the deployment output to get the endpoint URL.

4. Implement the following methods:

   **Method: `deploy(config: DeploymentConfig) -> dict`**
   - Generate a Python file (a Modal app definition) in a temporary directory. The generated file should follow the pattern documented at https://modal.com/docs/guide/ex/vllm_inference:
     - Import `modal`.
     - Define a `modal.Image` using `modal.Image.debian_slim(python_version="3.12").pip_install("vllm", "torch")`.
     - Define a `modal.App` with a descriptive name.
     - Define a `modal.Volume` for model weight caching.
     - Define a class with `@app.cls(gpu=<gpu_type>, image=<image>, volumes={...}, container_idle_timeout=<timeout>)`.
     - In the class, use `@modal.enter()` to load the vLLM model on container startup.
     - Use `@modal.web_endpoint(method="POST")` or `@modal.asgi_app()` to expose a FastAPI-based inference endpoint that accepts OpenAI-format requests and returns responses.
     - Configure scaling via `concurrency_limit`, `min_containers` (0 for scale-to-zero, 1+ for pre-warmed), `max_containers`.
   - The GPU type should be mapped to Modal GPU classes: `"a10g"`, `"a100"` (with optional `size="80GB"`), `"h100"`, `"l4"`, `"t4"`. Reference: https://modal.com/docs/reference/modal.gpu
   - Write the generated script to a temp file.
   - Run `modal deploy <temp_file>` as a subprocess. Ensure that `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET` environment variables are set for headless authentication. Reference: https://modal.com/docs/guide/secrets
   - Parse stdout for the deployed endpoint URL (Modal prints the URL upon successful deployment).
   - Return `{"app_name": "...", "endpoint_url": "...", "status": "deployed"}`.

   **Method: `check_status(deployment_id: str) -> dict`**
   - Run `modal app list` as a subprocess and parse the output to find the app by name.
   - Alternatively, send a health check HTTP request to the deployed endpoint URL.
   - Return status.

   **Method: `teardown(deployment_id: str) -> dict`**
   - Run `modal app stop <app_name>` as a subprocess.
   - Return confirmation.

---

## 12. Phase 9 — vLLM Self-Hosted Deployment Adapter

### Step 9.1: vLLM Deployer (adapters/vllm_deployer.py)

1. Create a `VLLMDeployer` class that works in conjunction with the Azure Adapter. It does not deploy infrastructure directly; instead, it generates the vLLM configuration and deployment commands/scripts that the Azure Adapter uses.

2. Implement the following methods:

   **Method: `generate_docker_run_command(model_name: str, optimization_flags: dict, port: int = 8000) -> str`**
   - Construct a `docker run` command string for the vLLM OpenAI-compatible server.
   - Base image: `vllm/vllm-openai:latest` (or a specific version from Docker Hub). Reference: https://docs.vllm.ai/en/latest/serving/deploying_with_docker.html
   - Required flags:
     - `--runtime nvidia --gpus all` — Enable GPU passthrough.
     - `-v ~/.cache/huggingface:/root/.cache/huggingface` — Mount HuggingFace model cache.
     - `--env "HUGGING_FACE_HUB_TOKEN=<token>"` — Pass HuggingFace token for gated models.
     - `-p {port}:8000` — Port mapping.
     - `--ipc=host` — MANDATORY: Required for PyTorch shared memory communication in tensor parallelism. Without this, the container will crash with SIGBUS errors.
   - vLLM server arguments (appended after the image name):
     - `--model {model_name}` — The HuggingFace model ID or path.
     - `--host 0.0.0.0` — Bind to all interfaces.
     - `--port 8000` — Internal port.
   - Apply optimization flags from the `optimization_flags` dict (see Appendix C for full reference).
   - Return the complete docker run command string.

   **Method: `generate_k8s_deployment_manifest(model_name: str, optimization_flags: dict, replicas: int, gpu_count: int) -> dict`**
   - Generate a Kubernetes Deployment YAML (as a Python dict) for deploying vLLM on AKS.
   - The manifest should include:
     - A Deployment with the specified number of replicas.
     - Container spec using the `vllm/vllm-openai:latest` image.
     - Resource requests and limits with `nvidia.com/gpu: {gpu_count}`.
     - Node selector and tolerations for GPU nodes (`sku=gpu:NoSchedule`).
     - Container args matching the vLLM server arguments (same as the docker run command flags).
     - Environment variables for `HUGGING_FACE_HUB_TOKEN`.
     - `shm-size` volume mount or `hostIPC: true` in the pod spec.
   - Also generate a Kubernetes Service manifest (ClusterIP or LoadBalancer) exposing port 8000.
   - Return the manifest dicts.

   **Method: `generate_aca_container_config(model_name: str, optimization_flags: dict) -> dict`**
   - Generate the Azure Container Apps container configuration dict for the vLLM container.
   - Container image: `vllm/vllm-openai:latest`.
   - Container args: Same optimization flags as above.
   - Return the config dict suitable for passing to the Azure adapter's `deploy_container_app` method.

   **Method: `get_recommended_optimization_flags(model_name: str, gpu_type: str, gpu_count: int, latency_requirements: str) -> dict`**
   - Based on the model name (infer parameter count from common model naming conventions), GPU type, GPU count, and latency requirements, return a recommended set of optimization flags.
   - Logic guidelines (the system prompt will provide more detailed reasoning, but this provides sensible defaults):
     - If model has >40B parameters and GPU has <48GB VRAM: recommend quantization "awq" or "gptq".
     - If GPU supports FP8 (Ada Lovelace or newer): recommend quantization "fp8" and kv_cache_dtype "fp8".
     - If gpu_count > 1: set tensor_parallel_size = gpu_count.
     - If latency_requirements is "Ultra-low" or "Low": enable prefix_caching and chunked_prefill.
     - Always recommend gpu_memory_utilization = 0.90 unless running other processes on the same GPU.
   - Return the flags dict.

---

## 13. Phase 10 — NVIDIA NIM Container Deployment Adapter

### Step 10.1: NIM Deployer (adapters/nim_deployer.py)

1. Create a `NIMDeployer` class that works in conjunction with the Azure Adapter, similar to the vLLM deployer.

2. Key NVIDIA NIM Concepts:
   - NIM containers are pre-built, TensorRT/vLLM-optimized inference microservices pulled from `nvcr.io`.
   - Container path format: `nvcr.io/nim/<publisher>/<model-name>:<version-tag>` (e.g., `nvcr.io/nim/meta/llama-3.1-8b-instruct:latest`).
   - Authentication to `nvcr.io` uses username `$oauthtoken` and password = NGC API Key.
   - NIM containers expose an OpenAI-compatible API at port 8000.
   - Required environment variable: `NGC_API_KEY` — passed to the container.
   - Local model cache should be mounted at `/opt/nim/.cache`.
   - Reference: https://docs.nvidia.com/nim/llm/latest/getting-started.html

3. Implement the following methods:

   **Method: `get_nim_image_path(model_name: str) -> str`**
   - Map common model names to their NIM container image paths on nvcr.io.
   - Maintain a lookup dictionary with entries like:
     - "llama-3.1-8b-instruct" → "nvcr.io/nim/meta/llama-3.1-8b-instruct:latest"
     - "llama-3.1-70b-instruct" → "nvcr.io/nim/meta/llama-3.1-70b-instruct:latest"
     - "mistral-7b-instruct" → "nvcr.io/nim/mistralai/mistral-7b-instruct-v03:latest"
     - "mixtral-8x7b-instruct" → "nvcr.io/nim/mistralai/mixtral-8x7b-instruct-v01:latest"
   - If the model is not found in the lookup, return the model_name as-is (user may provide the full image path).
   - Reference for available models: https://build.nvidia.com and https://catalog.ngc.nvidia.com

   **Method: `generate_docker_run_command(nim_image: str, port: int = 8000) -> str`**
   - Construct the docker run command for NIM:
     - `--gpus all` — Enable GPU passthrough.
     - `-e NGC_API_KEY=$NGC_API_KEY` — Pass NGC credentials.
     - `-v $HOME/.cache/nim:/opt/nim/.cache` — Model cache volume.
     - `-p {port}:8000` — Port mapping.
     - The image path (e.g., `nvcr.io/nim/meta/llama-3.1-8b-instruct:latest`).
   - No additional arguments needed — NIM containers are pre-configured with optimal TensorRT profiles.
   - Return the command string.
   - Reference: https://docs.nvidia.com/nim/llm/latest/getting-started.html

   **Method: `generate_k8s_deployment_manifest(nim_image: str, replicas: int, gpu_count: int) -> dict`**
   - Generate Kubernetes manifests for NIM deployment on AKS.
   - Alternatively, use the official NVIDIA NIM Helm chart approach:
     - The Helm chart is at `nvidia/nim-llm` in the NVIDIA Helm repository (`https://helm.ngc.nvidia.com/nvidia`).
     - Generate a Helm values override dict with `ngc.apiKey`, `model.name`, `persistence.enabled`, and GPU resource limits.
     - The adapter can either:
       a. Generate raw Kubernetes manifests (Deployment + Service + Secret for NGC key), OR
       b. Generate a Helm install command (`helm install nim-llm nvidia/nim-llm --set ...`).
   - For MVP, option (a) with raw manifests is simpler to implement.
   - Include:
     - A Kubernetes Secret for the NGC API key.
     - A Kubernetes Secret for `nvcr.io` image pull credentials (dockerconfigjson format with username `$oauthtoken`).
     - A Deployment with `imagePullSecrets`, GPU resource limits, and the NIM container config.
     - Health check probes: readinessProbe on `GET /v1/health/ready:8000` and livenessProbe on `GET /v1/health/live:8000`.
     - A LoadBalancer Service exposing port 8000.
   - Reference: https://docs.nvidia.com/nim/llm/latest/helm-kubernetes.html

   **Method: `generate_aca_container_config(nim_image: str) -> dict`**
   - Generate Azure Container Apps config for NIM.
   - Set the container image, NGC_API_KEY environment variable, and port 8000.
   - Return the config dict.

   **Method: `get_gpu_requirements(model_name: str) -> dict`**
   - Return the minimum GPU requirements for a given model based on the NIM support matrix:
     - 8B models: 1x GPU with ≥ 16GB VRAM (L4, A10G, L40S, RTX 4090).
     - 70B models: 2x 80GB GPUs (A100 80GB, H100 80GB) or 4x L40S.
     - 405B models: 8x H100/H200 80GB GPUs.
   - Return `{"min_gpus": int, "recommended_gpu_type": str, "min_vram_per_gpu_gb": int}`.
   - Reference: https://docs.nvidia.com/nim/llm/latest/support-matrix.html

---

## 14. Phase 11 — End-to-End Integration and Wiring

### Step 11.1: Wire the Sessions Router to the Agent Orchestrator

1. In `routers/sessions.py`, the `POST /sessions/{session_id}/answers` endpoint should:
   - Validate the answers using `compile_requirements()`.
   - Store them in the session.
   - Start the orchestrator as a background task: `asyncio.create_task(orchestrate_deployment(session_id))`.
   - Return immediately with `{"status": "analyzing", "message": "Requirements received. Deployment analysis started."}`.

2. The WebSocket handler at `/api/ws/{session_id}` should:
   - Accept the connection and register it with the connection manager.
   - Keep the connection alive, forwarding any client messages to the agent (if the agent supports mid-run instructions).
   - The connection manager's `send_to_session` is called by the orchestrator's callbacks to push messages back to the client.

### Step 11.2: Wire the Agent Tools to the Adapters

1. In `agent/tools.py`, each tool function should:
   - Instantiate the appropriate adapter (or receive it via dependency injection).
   - Call the adapter's methods with the tool's input parameters.
   - Handle errors and return structured results.
   - Example flow for `deploy_vllm_on_azure`:
     a. Instantiate `AzureAdapter` and `VLLMDeployer`.
     b. Call `vllm_deployer.get_recommended_optimization_flags(...)` to get default flags (agent may override these).
     c. Call `azure_adapter.create_resource_group(...)` if needed.
     d. Based on `deployment_target`:
        - If "vm": Call `azure_adapter.provision_gpu_vm(...)`, then SSH into the VM and run `vllm_deployer.generate_docker_run_command(...)`.
        - If "aks": Call `azure_adapter.create_aks_cluster(...)`, then apply `vllm_deployer.generate_k8s_deployment_manifest(...)` via kubectl.
        - If "aca": Call `azure_adapter.deploy_container_app(...)` with `vllm_deployer.generate_aca_container_config(...)`.
     e. Return the deployment details.

### Step 11.3: Wire the LiteLLM Translation Layer

1. The `test_deployed_endpoint` tool (defined in Phase 4) uses `litellm.completion()` directly to call any deployed endpoint in OpenAI format.
2. If using the LiteLLM proxy sidecar, the microservice can also route requests through `{LITELLM_PROXY_URL}/v1/chat/completions` for centralized logging and cost tracking.
3. Ensure the `litellm_config.yaml` is properly configured with at least the Anthropic Claude model entry.
4. In `docker-compose.yml`, ensure the `litellm` service starts before or alongside the main microservice, and the microservice's `LITELLM_PROXY_URL` environment variable points to the sidecar.

### Step 11.4: Integration Verification Checklist

1. Verify REST API endpoints respond correctly:
   - `GET /api/health` returns healthy status with provider availability.
   - `GET /api/questions` returns the full question list.
   - `POST /api/sessions` creates a session and returns a session_id.
   - `POST /api/sessions/{id}/answers` accepts answers and triggers the orchestrator.
   - `GET /api/sessions/{id}/status` reflects the current deployment state.
   - `GET /api/sessions/{id}/messages` returns the growing message history.
2. Verify WebSocket streaming works:
   - Connect to `WS /api/ws/{session_id}` after submitting answers.
   - Receive `agent_message`, `status_update`, and `deployment_complete` messages in real time.
3. Test the full flow:
   a. Call `POST /api/sessions` → get session_id.
   b. Call `POST /api/sessions/{id}/answers` with all answers.
   c. Connect to WebSocket or poll messages endpoint.
   d. Claude agent analyzes requirements and executes deployment.
   e. Receive final deployment result with endpoint URL and resource IDs.

---

## 15. Phase 12 — Environment Configuration and Secrets

### Step 12.1: Create .env.example

Create `.env.example` at the project root with all required and optional environment variables:

```
# === REQUIRED ===
# Anthropic API key for Claude Agent SDK
# Obtain from: https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=sk-ant-...

# === LITELLM PROXY (if using sidecar mode) ===
LITELLM_PROXY_URL=http://localhost:4000

# === CLAUDE MODEL SELECTION ===
CLAUDE_MODEL=claude-sonnet-4-20250514

# === AZURE (Required for Azure deployments) ===
# Azure Service Principal credentials
# Create via: az ad sp create-for-rbac --name LLMDeployer --role Contributor
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_SUBSCRIPTION_ID=

# === RUNPOD (Required for RunPod deployments) ===
# RunPod API key
# Obtain from: RunPod Console > User Settings > API Keys
RUNPOD_API_KEY=

# === MODAL (Required for Modal deployments) ===
# Modal token credentials
# Generate via: modal token new
MODAL_TOKEN_ID=
MODAL_TOKEN_SECRET=

# === NVIDIA NIM (Required for NIM deployments) ===
# NGC API key for pulling NIM containers
# Obtain from: https://build.nvidia.com or https://ngc.nvidia.com
NGC_API_KEY=

# === OPTIONAL ===
# HuggingFace token for gated model access (Llama, Mistral, etc.)
HUGGING_FACE_HUB_TOKEN=

# Path to the system prompt file
SYSTEM_PROMPT_PATH=system_prompt.txt
```

### Step 12.2: Docker Compose (docker-compose.yml)

1. Create a `docker-compose.yml` at the project root with two services:
   - **llmdeployer**: The main microservice.
     - Build from `./Dockerfile`.
     - Expose port 8000.
     - Mount the `.env` file and pass environment variables.
     - Depends on `litellm` service.
   - **litellm**: The LiteLLM proxy sidecar.
     - Image: `ghcr.io/berriai/litellm:main-latest`.
     - Mount `litellm_config.yaml` to `/app/config.yaml`.
     - Command: `--config /app/config.yaml --port 4000`.
     - Pass `ANTHROPIC_API_KEY` environment variable.
     - Expose port 4000 (internal only, unless debugging).
   - Reference: https://docs.litellm.ai/docs/simple_proxy

### Step 12.3: Dockerfile

Create `Dockerfile` at the project root:
- Base image: `python:3.12-slim`
- Install system dependencies for Azure SDK and cryptography (`build-essential`, `libffi-dev`).
- Copy `requirements.txt` and install Python dependencies.
- Copy the entire `app/` directory and other project files (`system_prompt.txt`, etc.).
- Expose port 8000.
- Set the `CMD` to `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

### Step 12.4: LiteLLM Config (litellm_config.yaml)

Create `litellm_config.yaml` at the project root. This configures the LiteLLM proxy with available models:
- Define a `model_list` array with at least one entry for Claude:
  - `model_name`: "claude-sonnet" (the alias consumers use)
  - `litellm_params.model`: "anthropic/claude-sonnet-4-20250514"
  - `litellm_params.api_key`: "os.environ/ANTHROPIC_API_KEY" (LiteLLM supports environment variable references)
- Optionally define entries for testing OpenAI-compatible endpoints (vLLM, NIM) with custom `api_base` URLs.
- Reference: https://docs.litellm.ai/docs/simple_proxy

---

## 16. Phase 13 — Testing and Validation

### Step 13.1: Backend Unit Tests

1. Create a `tests/` directory at the project root.
2. Write tests for:
   - **Session manager**: Test session creation, retrieval, updates, and edge cases (non-existent session IDs raise 404).
   - **Question flow**: Test `compile_requirements()` with valid and invalid answer sets. Test that missing required fields raise validation errors.
   - **REST API endpoints**: Use FastAPI's `TestClient` to test all endpoints end-to-end (session creation, answer submission, status retrieval, questions list).
   - **vLLM deployer**: Test `generate_docker_run_command()` with various optimization flag combinations. Verify the command string includes `--ipc=host` and proper GPU flags.
   - **NIM deployer**: Test `get_nim_image_path()` with known model names. Test `get_gpu_requirements()` returns correct minimums.
   - **Connection manager**: Test WebSocket connection registration and message broadcasting.
   - **LiteLLM integration**: Test that `litellm.completion()` calls work with mocked responses (do not call real APIs in unit tests).
3. Use `pytest` and `pytest-asyncio` for async test support.

### Step 13.2: Integration Test Scenario

1. Start the microservice (and LiteLLM sidecar if using Docker Compose).
2. Call `GET /api/health` — verify all fields are present.
3. Call `GET /api/questions` — verify the full question list is returned.
4. Call `POST /api/sessions` — create a session.
5. Call `POST /api/sessions/{id}/answers` with a complete answer set.
6. Poll `GET /api/sessions/{id}/messages` — verify agent messages start appearing.
7. Call `GET /api/sessions/{id}/status` — verify status transitions (analyzing → deploying → completed or failed).
8. If Azure credentials are configured, verify infrastructure provisioning begins (use a low-cost VM size like Standard_NCas_T4_v3 for testing).

---

## Appendix A — Key API Format Differences (OpenAI vs Anthropic)

This appendix is retained as reference for understanding what LiteLLM handles internally, and for debugging translation issues.

| Feature | OpenAI API | Anthropic (Claude) Messages API |
|---------|-----------|-------------------------------|
| **Endpoint** | `POST /v1/chat/completions` | `POST /v1/messages` |
| **Authentication** | Header: `Authorization: Bearer <KEY>` | Header: `x-api-key: <KEY>` + `anthropic-version: 2023-06-01` |
| **System Prompt** | Message in `messages[]` with `role: "system"` or `"developer"` | Top-level `"system"` field. `messages[]` contains ONLY `"user"` and `"assistant"`. |
| **Required Fields** | `model`, `messages` | `model`, `messages`, **`max_tokens`** (REQUIRED) |
| **Tool Definition** | `tools: [{"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}]` | `tools: [{"name": "...", "description": "...", "input_schema": {...}}]` |
| **Tool Call (Assistant)** | `message.tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "...", "arguments": "{\"x\":1}"}}]` (arguments is JSON **string**) | `content = [{"type": "tool_use", "id": "toolu_1", "name": "...", "input": {"x": 1}}]` (input is parsed JSON **object**) |
| **Tool Result** | Separate message: `{"role": "tool", "tool_call_id": "call_1", "content": "..."}` | Inside user message: `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "..."}]}` |
| **Streaming** | Generic SSE: `data: {"choices": [{"delta": {"content": "..."}}]}` ending with `data: [DONE]` | Typed SSE events: `event: message_start`, `event: content_block_delta`, `event: message_stop` |
| **Stop Reasons** | `"stop"`, `"tool_calls"`, `"length"` | `"end_turn"`, `"tool_use"`, `"max_tokens"` |

**References:**
- OpenAI Chat Completions: https://platform.openai.com/docs/api-reference/chat/create
- Anthropic Messages API: https://docs.anthropic.com/en/api/messages
- Anthropic Tool Use: https://docs.anthropic.com/en/docs/build-with-claude/tool-use
- Anthropic Streaming: https://docs.anthropic.com/en/api/messages-streaming

---

## Appendix B — Azure GPU VM Series Reference

| VM Series | GPU Hardware | VRAM | Recommended For |
|-----------|-------------|------|-----------------|
| **Standard_NCas_T4_v3** | NVIDIA T4 | 16GB | Small models (1B-7B quantized), cost-effective testing |
| **Standard_NC6s_v3** | NVIDIA V100 | 16GB | Mid-tier inference, legacy workloads |
| **Standard_NC_A100_v4** | NVIDIA A100 | 40GB or 80GB | Mid-to-large model serving (7B-70B) |
| **Standard_NCads_H100_v5** | NVIDIA H100 | 80GB | Best performance/value for 70B+ models |
| **Standard_NC_RTXPRO6000BSE_v6** | NVIDIA RTX Pro 6000 | 48GB | Enterprise RAG, models <70B |
| **Standard_ND_A100_v4** | 8× NVIDIA A100 | 8×80GB | Distributed serving (70B-405B), multi-GPU |
| **Standard_ND_H100_v5** | 8× NVIDIA H100 | 8×80GB | Largest models (405B+), ultra-high throughput |

**Reference:** https://learn.microsoft.com/en-us/azure/virtual-machines/sizes-gpu

---

## Appendix C — vLLM Optimization Flags Reference

| Flag | CLI Argument | Type | Default | When to Use |
|------|-------------|------|---------|-------------|
| **Tensor Parallelism** | `--tensor-parallel-size` / `-tp` | int | 1 | Multi-GPU setups. Set to number of GPUs. |
| **Pipeline Parallelism** | `--pipeline-parallel-size` / `-pp` | int | 1 | Multi-node or when TP alone is insufficient. |
| **Quantization** | `--quantization` / `-q` | str | none | `awq`, `gptq` (INT4), `fp8` (FP8 on Ada/Hopper), `bitsandbytes`, `compressed-tensors`, `gguf` |
| **KV Cache Quantization** | `--kv-cache-dtype` | str | auto | `fp8` or `fp8_e4m3` — doubles context length capacity. Requires Ada/Hopper GPU. |
| **Max Model Length** | `--max-model-len` | int | auto | Reduce to save VRAM if full context not needed. |
| **GPU Memory Utilization** | `--gpu-memory-utilization` | float | 0.90 | Fraction of GPU VRAM allocated. Lower if co-locating. |
| **Prefix Caching** | `--enable-prefix-caching` | flag | off | Caches KV for repeated prompt prefixes (e.g., system prompts). |
| **Chunked Prefill** | `--enable-chunked-prefill` | flag | off | Prevents long-prompt latency spikes by interleaving prefill and generation. |
| **Max Concurrent Seqs** | `--max-num-seqs` | int | 256 | Max parallel requests in one iteration. |
| **Speculative Decoding** | `--speculative-model` | str | none | Use a smaller draft model for speculative multi-token generation. |
| **Served Model Name** | `--served-model-name` | str | model ID | Override the model name returned by the API. |
| **API Key** | `--api-key` | str | none | Require an API key for endpoint access. |
| **Swap Space** | `--swap-space` | int (GB) | 4 | CPU RAM for KV cache offloading during preemption. |
| **CPU Offload** | `--cpu-offload-gb` | int | 0 | Offload model weights to CPU (reduces GPU VRAM usage). |

**References:**
- Engine Arguments: https://docs.vllm.ai/en/latest/configuration/engine_args.html
- Server Arguments: https://docs.vllm.ai/en/latest/configuration/serve_args.html
- Quantization: https://docs.vllm.ai/en/latest/quantization/fp8.html
- Docker Deployment: https://docs.vllm.ai/en/latest/serving/deploying_with_docker.html
- OpenAI Compatible Server: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html

---

## Appendix D — Existing OpenAI-to-Claude Translation Repos

Instead of building a custom translation layer, use one of these established open-source projects. **LiteLLM is recommended** for production use and is the default in this implementation.

| Project | GitHub | Best For | Stars |
|---------|--------|----------|-------|
| **LiteLLM** (RECOMMENDED) | https://github.com/BerriAI/litellm | Production-grade unified gateway, 100+ providers, cost tracking, load balancing, virtual keys | 15k+ |
| **UniClaudeProxy** | https://github.com/vibheksoni/UniClaudeProxy | Claude Code CLI ↔ any OpenAI-compatible backend, SSE streaming, ReAct XML tool fallback | — |
| **OpenAI-to-Claude-API-Converter-Proxy** | https://github.com/Skillter/OpenAI-to-Claude-API-Converter-Proxy | Simple, lightweight local-only proxy for OpenAI → Claude conversion | — |
| **CCProxy** | https://github.com/orchestre/CCProxy | High-performance Go-based proxy, low memory, fast translation | — |

### When to choose which:

- **LiteLLM**: Default choice. Use when you need production reliability, multi-provider support, Docker sidecar deployment, cost tracking, and future-proofing for adding more LLM providers.
- **UniClaudeProxy**: Use if you specifically want to connect Claude Code CLI or Anthropic-format tools to non-Anthropic backends with ReAct XML fallback for models that lack native tool calling.
- **OpenAI-to-Claude-API-Converter-Proxy**: Use for the simplest possible setup — a lightweight local proxy with minimal configuration. Good for local development and testing.
- **CCProxy**: Use if you need maximum performance and minimal resource footprint. Written in Go, so it compiles to a single binary with very low overhead.

### How to swap LiteLLM for an alternative:

If you prefer a different translation project instead of LiteLLM:
1. Remove `litellm` from `requirements.txt`.
2. Remove the LiteLLM sidecar from `docker-compose.yml`.
3. Remove `litellm_config.yaml`.
4. Run the chosen proxy as a separate process or sidecar (follow the project's own Docker/deployment instructions).
5. Point the `LITELLM_PROXY_URL` (rename to a generic `TRANSLATION_PROXY_URL` if desired) at the alternative proxy's URL.
6. In the `test_deployed_endpoint` tool, replace `litellm.completion()` calls with direct HTTP calls to the proxy's OpenAI-compatible endpoint using `httpx`.

---

## Final Notes

1. **The system prompt** (`system_prompt.txt`) is intentionally left as a placeholder. The owner will write the decision-making logic that guides the Claude agent to choose the right deployment strategy based on user requirements. The code infrastructure is fully ready to consume whatever prompt is provided.

2. **No Frontend**: This microservice is headless. The shared frontend (or any consumer — CLI, Postman, another microservice) interacts with LLMDeployer purely through the REST API and WebSocket endpoints documented in Phase 2. The `GET /api/questions` endpoint provides the question list so consumers can dynamically render them.

3. **MVP Scope**: This implementation is Azure-only for the cloud infrastructure provider. RunPod and Modal are serverless platforms and are provider-agnostic. The Azure adapter handles all direct infrastructure provisioning (VMs, AKS, ACA).

4. **Translation Layer**: Instead of building a custom OpenAI ↔ Anthropic translation layer, this implementation uses **LiteLLM** (or any open-source alternative from Appendix D). LiteLLM runs as a Python library (embedded) or as a Docker sidecar (production) and handles all format conversion automatically.

5. **Security**: The `can_use_tool` security gate in the Claude Agent SDK integration provides a hook for future approval workflows. For MVP, it logs and allows all deployment operations.

6. **Scalability**: The in-memory session store is adequate for MVP/development. For production, replace with Redis or PostgreSQL.

---

*This implementation prompt was generated with cited documentation fetched on 2026-07-27. Always verify links against the latest official documentation before implementation.*
