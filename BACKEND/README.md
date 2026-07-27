# FDE Backend

Forward Deployed Engineer planning and routing backend. Handles planning conversations, architecture proposals, human-in-the-loop approval, and downstream handoff to AppDeveloper/LLMDeployer services.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Clients                              │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP / WebSocket
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     FDE API (FastAPI)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Sessions │ │ Planning │ │ Handoffs │ │   WebSocket  │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘   │
│       └─────────────┴────────────┴──────────────┘           │
│                          │                                  │
│  ┌───────────────────────┴────────────────────────────┐     │
│  │              Service Layer                         │     │
│  │  PlanningService · ProposalService · EventService  │     │
│  │  ClaudePlanner (real/fake) · RedactionService      │     │
│  └───────────────────────┬────────────────────────────┘     │
└──────────────────────────┼──────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│  PostgreSQL  │  │    Redis     │  │   LiteLLM Proxy  │
│   (async)    │  │  (rate limit │  │  (OpenAI compat) │
│              │  │   + events)  │  │  → Anthropic API  │
└──────────────┘  └──────────────┘  └──────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────┐
│              Outbox Worker (async)                    │
│  Polls handoff_outbox → delivers to downstream APIs   │
└───────┬──────────────────────────┬────────────────────┘
        ▼                          ▼
┌──────────────┐          ┌──────────────┐
│ AppDeveloper │          │ LLMDeployer  │
│   (downstream)│          │  (downstream)│
└──────────────┘          └──────────────┘
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Python | 3.12+ | Runtime |
| FastAPI | ≥0.115.0,<1.0 | Web framework |
| Uvicorn | ≥0.30.0,<1.0 | ASGI server |
| Pydantic | ≥2.9.0,<3.0 | Data validation |
| Pydantic Settings | ≥2.5.0,<3.0 | Configuration |
| SQLAlchemy | ≥2.0.35,<3.0 | ORM (async) |
| asyncpg | ≥0.30.0,<1.0 | PostgreSQL driver |
| Alembic | ≥1.14.0,<2.0 | Database migrations |
| httpx | ≥0.27.0,<1.0 | HTTP client |
| Redis | ≥5.2.0,<6.0 | Rate limiting, events |
| PyJWT | ≥2.9.0,<3.0 | Token authentication |
| structlog | ≥24.4.0,<25.0 | Structured logging |
| prometheus-client | ≥0.21.0,<1.0 | Metrics |

### Dev dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| ruff | ≥0.8.0,<1.0 | Linter + formatter |
| mypy | ≥1.12.0,<2.0 | Static type checking |
| pytest | ≥8.3.0,<9.0 | Test framework |
| pytest-asyncio | ≥0.24.0,<1.0 | Async test support |
| pytest-cov | ≥6.0.0,<7.0 | Coverage |
| bandit | ≥1.8.0,<2.0 | Security linting |

### Infrastructure

| Service | Image | Purpose |
|---------|-------|---------|
| PostgreSQL | postgres:16-alpine | Persistent storage |
| Redis | redis:7-alpine | Rate limiting + event pub/sub |
| LiteLLM | ghcr.io/berriai/litellm:main-latest | OpenAI-compatible gateway to Anthropic |

## Local Development

### Prerequisites

- Docker + Docker Compose
- Python 3.12+

### Quick start

```bash
# Clone and enter the directory
cd BACKEND

# Copy environment variables
cp .env.example .env

# Edit .env and set your ANTHROPIC_API_KEY (required for real planner)
# For fake planner mode (no API key needed), set PLANNER_MODE=fake

# Start all services
docker compose up --build

# The API is available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Without Docker

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Start PostgreSQL and Redis locally, then:
export DATABASE_URL="postgresql+asyncpg://fde_user:change_me@localhost:5432/fde_backend"
export REDIS_URL="redis://localhost:6379/0"

# Run migrations
alembic upgrade head

# Start the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start the worker (in a separate terminal)
python -m app.workers.main
```

## Database Migrations

```bash
# Apply migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "description"

# Check current revision
alembic current
```

## Running the Worker

The worker polls the outbox table and delivers handoffs to downstream services.

```bash
# Docker (included in compose)
docker compose up worker

# Local
python -m app.workers.main
```

## API Examples

### Create a session

```bash
curl -X POST http://localhost:8000/v1/sessions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"user_message": "I need a chatbot for customer support"}'
```

### Send an answer

```bash
curl -X POST http://localhost:8000/v1/sessions/{session_id}/answers \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"question_id": "q1", "answer_text": "We use PostgreSQL"}'
```

### Approve a proposal

```bash
curl -X POST http://localhost:8000/v1/sessions/{session_id}/approval \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "plan_version": 1}'
```

### Check handoff status

```bash
curl http://localhost:8000/v1/sessions/{session_id}/handoff \
  -H "Authorization: Bearer your-api-key"
```

### WebSocket events

```javascript
const ws = new WebSocket("ws://localhost:8000/v1/sessions/{session_id}/events?token=your-api-key");
ws.onmessage = (event) => console.log(JSON.parse(event.data));
```

## State Machine

```
DISCOVERING ──────┬──→ AWAITING_ANSWERS ──→ DISCOVERING (loop)
                  │
                  ├──→ AWAITING_APPROVAL ──→ DISCOVERING (request changes)
                  │         │
                  │         ├──→ HANDOFF_QUEUED ──→ HANDED_OFF (terminal)
                  │         │         │
                  │         │         └──→ HANDOFF_FAILED ──→ HANDOFF_QUEUED (retry)
                  │         │
                  │         └──→ CANCELLED (terminal)
                  │
                  ├──→ FAILED ──→ DISCOVERING (recover) or CANCELLED
                  │
                  └──→ CANCELLED (terminal)
```

### Valid transitions

| From | To |
|------|-----|
| DISCOVERING | AWAITING_ANSWERS, AWAITING_APPROVAL, FAILED, CANCELLED |
| AWAITING_ANSWERS | DISCOVERING, CANCELLED |
| AWAITING_APPROVAL | DISCOVERING, HANDOFF_QUEUED, CANCELLED |
| HANDOFF_QUEUED | HANDED_OFF, HANDOFF_FAILED, CANCELLED |
| HANDOFF_FAILED | HANDOFF_QUEUED, CANCELLED |
| FAILED | DISCOVERING, CANCELLED |

## Security Model

- **Authentication**: API key or JWT bearer token via `Authorization` header
- **Authorization**: Tenant isolation — users can only access their own sessions
- **Rate limiting**: Per-tenant limits enforced via Redis
- **Request limits**: Configurable max request body size (default 64KB)
- **Redaction**: PII, API keys, tokens, and secrets redacted from logs and events
- **Planner isolation**: Claude planner has no access to downstream services or host files

## Observability

- **Health**: `GET /healthz` — liveness probe (always 200 if process is running)
- **Readiness**: `GET /readyz` — checks PostgreSQL, Redis, and LiteLLM connectivity
- **Logging**: Structured JSON via structlog
- **Metrics**: Prometheus metrics at `/metrics`
- **Correlation**: All requests tagged with correlation IDs

## Official Documentation

- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://docs.pydantic.dev/latest/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic](https://alembic.sqlalchemy.org/en/latest/)
- [LiteLLM Proxy](https://docs.litellm.ai/docs/proxy/quick_start)
- [LiteLLM Anthropic Provider](https://docs.litellm.ai/docs/providers/anthropic)
- [Anthropic API](https://docs.anthropic.com/en/api/messages)
- [OWASP LLM Top 10](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [OWASP API Security Top 10](https://owasp.org/API-Security/)

## Known Limitations

1. **No frontend** — this is a backend-only service
2. **Single worker** — outbox worker runs as a single process; for production, run multiple instances with PostgreSQL row-level locking
3. **No persistent WebSocket storage** — event snapshots are held in memory; process restart loses unsent events
4. **Fake planner is for development only** — never use `PLANNER_MODE=fake` in production
5. **No multi-region support** — designed for single-region deployment
6. **LiteLLM sidecar** — runs the latest image; pin a specific version for production
7. **No webhook retries for downstream** — relies on outbox polling; WebSocket delivery to downstream is not implemented
8. **Alembic migrations must run before API starts** — compose handles this, but manual deploys must ensure migration order
