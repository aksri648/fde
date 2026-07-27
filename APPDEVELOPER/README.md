# APPDEVELOPER

Python 3.12 backend microservice for AI-powered app generation using Claude Agent SDK.

## Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env

# Edit .env with your ANTHROPIC_API_KEY and APPDEVELOPER_API_KEY
```

## Running

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## REST API

| Method | Path | Description |
|--------|------|-------------|
| POST | /v1/jobs | Create a job from prompt |
| GET | /v1/jobs/{job_id} | Get job state and details |
| POST | /v1/jobs/{job_id}/answers | Submit answers to questions |
| POST | /v1/jobs/{job_id}/generate | Start code generation |
| GET | /v1/jobs/{job_id}/artifacts | List generated files |
| GET | /v1/jobs/{job_id}/artifacts/{path} | Get file content |
| POST | /v1/jobs/{job_id}/push-decision | Approve/reject push to GitHub |
| POST | /v1/jobs/{job_id}/github/push | Push to GitHub repository |
| POST | /v1/jobs/{job_id}/cancel | Cancel job |
| GET | /healthz | Liveness check |
| GET | /readyz | Readiness check |

### Create Job

```bash
curl -X POST http://localhost:8000/v1/jobs \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"prompt": "Build a REST API for todo items"}'
```

### Get Job

```bash
curl http://localhost:8000/v1/jobs/{job_id} \
  -H "X-API-Key: your-api-key"
```

## WebSocket

Connect to `ws://localhost:8000/v1/jobs/{job_id}/events` for real-time events.

Events include: `state_changed`, `architecture_ready`, `questions_ready`, `agent_message`, `tool_activity`, `file_created`, `validation_started`, `validation_result`, `review_finding`, `github_status`, `completed`, `error`.

## OpenAPI

Interactive docs available at `http://localhost:8000/docs` when the server is running.

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| ANTHROPIC_API_KEY | Claude API key | required |
| APPDEVELOPER_API_KEY | Service auth key | required |
| DATABASE_URL | Database connection string | sqlite+aiosqlite:///./appdeveloper.db |
| APPDEVELOPER_WORKSPACE_ROOT | Workspace root directory | ./workspaces |
| APPDEVELOPER_REQUIRE_HTTPS | Require HTTPS | false |
| APPDEVELOPER_MAX_CONCURRENT_JOBS | Max concurrent generations | 5 |

## Job Lifecycle

```
CREATED -> ARCHITECTURE_PROPOSED -> AWAITING_ANSWERS <-> ARCHITECTURE_PROPOSED
-> READY_TO_GENERATE -> GENERATING -> REVIEWING -> DEBUGGING (0-3 cycles)
-> VERIFIED -> AWAITING_PUSH_DECISION -> AWAITING_GITHUB_TOKEN -> PUSHING -> PUSHED
```

Terminal states: CANCELLED, FAILED, REVIEW_FAILED, PUSH_FAILED

## Security

- Token material is never persisted, logged, or emitted in events
- Path traversal protection on all workspace operations
- Secret scanning on staged git content before push
- Rate limiting on job creation
- API key authentication required
- CORS disabled by default

## Docker

```bash
docker-compose up
```

## Testing

```bash
pytest -q --cov=app --cov-fail-under=60
ruff check .
ruff format --check .
mypy app
bandit -q -r app
```

## Limitations

- Local process isolation is not a hardened sandbox
- Deployment should use disposable containers with CPU/memory/filesystem controls
- The Claude Agent SDK integration uses a mock client when SDK is unavailable
- GitHub push requires explicit user confirmation and valid token
