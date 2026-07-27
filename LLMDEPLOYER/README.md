# LLMDeployer

A headless backend microservice for intelligent LLM deployment orchestration.

## Overview

LLMDeployer exposes REST APIs and a WebSocket endpoint that are consumed by a shared frontend (or any other client). It:

1. Accepts structured user requirements via API
2. Sends requirements to a Claude Agent SDK powered agent
3. The agent decides which deployment strategy to use (RunPod, Modal, Azure vLLM, Azure NIM)
4. Executes the deployment plan by calling appropriate adapters
5. Streams real-time progress via WebSocket

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (for production)

### Development Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the server
uvicorn app.main:app --reload --port 8000
```

### Docker Compose

```bash
docker compose up
```

This starts both the LLMDeployer microservice (port 8000) and the LiteLLM proxy sidecar (port 4000).

## API Endpoints

| Method | Endpoint | Description |
|--------|---------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/questions` | Get deployment questions |
| `POST` | `/api/sessions` | Create a new session |
| `GET` | `/api/sessions/{id}` | Get session details |
| `POST` | `/api/sessions/{id}/answers` | Submit answers and start deployment |
| `GET` | `/api/sessions/{id}/status` | Get deployment status |
| `GET` | `/api/sessions/{id}/messages` | Get agent messages |
| `POST` | `/api/sessions/{id}/message` | Send additional message to agent |
| `WS` | `/api/ws/{session_id}` | WebSocket for real-time streaming |

## Environment Variables

See `.env.example` for all configuration options.

### Required

- `ANTHROPIC_API_KEY` - Anthropic API key for Claude Agent SDK

### Optional (per provider)

- `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_SUBSCRIPTION_ID` - Azure credentials
- `RUNPOD_API_KEY` - RunPod API key
- `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` - Modal credentials
- `NGC_API_KEY` - NVIDIA NGC API key for NIM containers
- `HUGGING_FACE_HUB_TOKEN` - HuggingFace token for gated models

## Architecture

The system uses:
- **FastAPI** for REST API and WebSocket
- **Claude Agent SDK** for deployment decision orchestration
- **LiteLLM** for OpenAI ↔ Claude translation
- **Azure SDK** for cloud infrastructure provisioning
- **RunPod/Modal SDKs** for serverless deployments
- **vLLM/NVIDIA NIM** for self-hosted LLM inference

## Running Tests

```bash
pytest tests/
```
