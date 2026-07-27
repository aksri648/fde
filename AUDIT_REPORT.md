# FDE System Audit Report

**Date**: 2026-07-27
**Scope**: BACKEND, APPDEVELOPER, LLMDEPLOYER, FRONTEND

## Architecture

```
OpenCode-derived desktop renderer
          | HTTPS REST + authenticated WebSocket events
          v
BACKEND (public BFF, owns sessions, proposals, routing, audit/outbox)
          | private REST with service authentication, correlation and idempotency IDs
     +----+-----------------------------+
     v                                  v
APPDEVELOPER                    LLMDEPLOYER
job generation                  deployment orchestration
```

| Service | Port | Auth | Database |
|---------|------|------|----------|
| BACKEND | 8000 | Bearer token / API key | PostgreSQL (async) |
| APPDEVELOPER | 8001 | X-API-Key header | SQLite (async) |
| LLMDEPLOYER | 8002 | X-API-Key header | In-memory |
| FRONTEND | 5173 | N/A (renderer) | N/A |

## Endpoint/Auth Matrix

### BACKEND (BFF)

| Endpoint | Method | Auth | State |
|----------|--------|------|-------|
| `/healthz` | GET | None | OK |
| `/readyz` | GET | None | OK |
| `/v1/sessions` | POST | Bearer | OK |
| `/v1/sessions/{id}` | GET | Bearer | OK |
| `/v1/sessions/{id}/turns` | POST | Bearer | OK |
| `/v1/sessions/{id}/answers` | POST | Bearer | OK |
| `/v1/sessions/{id}/questions` | GET | Bearer | OK |
| `/v1/sessions/{id}/proposal` | GET | Bearer | OK |
| `/v1/sessions/{id}/approval` | POST | Bearer | **FIXED** |
| `/v1/sessions/{id}/handoff` | GET | Bearer | OK |
| `/v1/sessions/{id}/handoff/retry` | POST | Bearer | OK |
| `/v1/sessions/{id}/cancel` | POST | Bearer | OK |
| `/v1/sessions/{id}/events` | WS | Token query | OK |

### APPDEVELOPER (Downstream)

| Endpoint | Method | Auth | Notes |
|----------|--------|------|-------|
| `/v1/jobs` | POST | X-API-Key | **FIXED** - BACKEND now sends X-API-Key |
| `/v1/jobs/{id}` | GET | X-API-Key | OK |
| `/healthz` | GET | None | OK |

### LLMDEPLOYER (Downstream)

| Endpoint | Method | Auth | Notes |
|----------|--------|------|-------|
| `/api/sessions` | POST | X-API-Key | **FIXED** - Auth required |
| `/api/sessions/{id}/answers` | POST | X-API-Key | **FIXED** - Auth required |
| `/api/sessions/{id}` | GET | X-API-Key | **FIXED** - Auth required |
| `/api/health` | GET | None | OK |

## Findings

### Critical (Fixed)

1. **Approval endpoint did not create outbox record** (planning.py:97-205)
   - **Evidence**: `submit_approval()` returned `{"status": "approved"}` without calling `ProposalService.handle_approval()`, no state transition, no outbox record, no event published.
   - **Fix**: Replaced endpoint to delegate to `ProposalService.handle_approval()` which atomically creates outbox record, transitions `AWAITING_APPROVAL -> HANDOFF_QUEUED`, and publishes `handoff_queued`.

2. **BACKEND->APPDEVELOPER auth mismatch** (appdeveloper_client.py:33)
   - **Evidence**: Client sent `Authorization: Bearer` header, but APPDEVELOPER's `verify_api_key()` checks `X-API-Key` header via `APIKeyHeader(name="X-API-Key")`.
   - **Fix**: Changed client to send `X-API-Key` header matching APPDEVELOPER's expected auth scheme.

3. **Outbox worker used placeholder downstream IDs** (outbox_worker.py:90-101)
   - **Evidence**: Receipt created with `downstream_id=""` and `downstream_status="accepted"` regardless of actual downstream response.
   - **Fix**: Worker now captures actual response from downstream client and stores real `downstream_id` and `downstream_status`.

4. **LLMDEPLOYER answer submission not checked** (llmdeployer_client.py:47-50)
   - **Evidence**: `POST /api/sessions/{id}/answers` response was not checked with `raise_for_status()`. A 5xx error would be silently ignored.
   - **Fix**: Added `answers_response.raise_for_status()` after the second REST call.

### High (Fixed)

5. **LLMDEPLOYER had no authentication** (LLMDEPLOYER/app/main.py:17-23)
   - **Evidence**: All REST and WebSocket endpoints were publicly accessible without any auth.
   - **Fix**: Created `app/security.py` with `X-API-Key` verification, added `Depends(verify_api_key)` to all session routes.

6. **LLMDEPLOYER CORS configured `allow_origins=["*"]` with credentials** (LLMDEPLOYER/app/main.py:17-23)
   - **Evidence**: Wildcard CORS with `allow_credentials=True` is a security vulnerability.
   - **Fix**: Restricted to `["http://localhost:3000", "http://localhost:5173"]`.

7. **Docker Compose port collisions** (all docker-compose.yml files)
   - **Evidence**: APPDEVELOPER and LLMDEPLOYER both mapped port 8000, same as BACKEND. Internal service URLs pointed to wrong ports.
   - **Fix**: APPDEVELOPER -> 8001, LLMDEPLOYER -> 8002. BACKEND compose updated to use correct internal URLs.

### Medium (Fixed)

8. **LLMDEPLOYER used deprecated `on_event` handlers** (LLMDEPLOYER/app/main.py:31-54)
   - **Evidence**: FastAPI deprecated `on_event("startup")` in favor of lifespan context manager.
   - **Status**: Documented, not changed to avoid scope creep. Functionally equivalent.

### Low (Documented)

9. **No FRONTEND existed**
   - **Fix**: Created complete SolidJS desktop frontend in `FRONTEND/`.

10. **No integration tests for handoff flows**
    - **Fix**: Added 13 integration tests in `tests/integration/test_handoff_flows.py`.

## Test Evidence

| Service | Tests | Before | After | Status |
|---------|-------|--------|-------|--------|
| BACKEND | Unit + Integration | 66 | 79 | All pass |
| APPDEVELOPER | Unit | 115 | 115 | All pass |
| LLMDEPLOYER | Unit | 26 | 26 | All pass |
| **Total** | | **207** | **220** | **All pass** |

## Unresolved External Dependencies

1. **PostgreSQL** - Required for BACKEND runtime. Not available in local test environment; tests use mocks.
2. **Redis** - Required for rate limiting. Not available in local test environment; rate limiter returns True on connection error.
3. **LiteLLM Proxy** - Required for real Claude planner. Tests use FakePlanner.
4. **Anthropic API Key** - Required for real planner mode. Not needed for fake planner.
5. **Cloud Provider Keys** - Azure, RunPod, Modal, NGC keys for LLMDeployer deployment adapters.

## Required Reference Links

- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [FastAPI WebSocket](https://fastapi.tiangolo.com/reference/websockets/)
- [OWASP REST Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html)
- [OpenCode Repository](https://github.com/anomalyco/opencode)
