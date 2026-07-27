# Implementation Prompt: audit, integrate, and add an OpenCode-based desktop UI

You are a senior full-stack engineer. Work carefully and complete this task in the current working directory. The project has three Python/FastAPI services:

- `BACKEND/`: the public FDE orchestration API and the only API that the desktop UI may call.
- `APPDEVELOPER/`: an application-generation microservice.
- `LLMDEPLOYER/`: an LLM deployment-orchestration microservice.

Your deliverable is a working, tested system plus a new `FRONTEND/` folder. Do not only write an analysis. First understand the code, then make the smallest safe changes needed to fix verified defects, connect the services with REST, and adapt the OpenCode desktop UI to this product.

## Non-negotiable rules

1. Read this entire prompt before editing.
2. Preserve all user-authored changes. Do not run destructive Git commands or delete an existing folder merely because it is unfamiliar.
3. Never commit API keys, tokens, `.env` files, generated databases, workspaces, or vendor `node_modules`.
4. Treat `BACKEND` as the browser-facing backend-for-frontend (BFF). `FRONTEND` must never directly call `APPDEVELOPER` or `LLMDEPLOYER`, and must never call cloud-provider APIs.
5. Use REST/JSON for service-to-service commands and queries. WebSockets may be used only for live progress after REST creates or identifies a resource. Do not replace REST APIs with WebSockets.
6. Do not invent UI actions or API endpoints. If an OpenCode control has no safe matching backend capability, remove it or render it as non-interactive information—not a broken button.
7. Use the actual OpenAPI schemas exposed by each running FastAPI service (`/openapi.json` or `/docs`) as the source of truth. The tables below are a starting point, not a reason to ignore runtime schemas.
8. Before reporting success, run the listed tests and at least one end-to-end handoff test using fake/mocked external AI/provider calls. Clearly report any external prerequisite that prevents a real-provider test.

## Phase 0 — inventory and baseline

1. List the files, existing test suites, Docker Compose files, environment examples, ports, auth schemes, CORS settings, startup hooks, database choices, and WebSocket event formats in all three folders.
2. Read all API routers, domain models/schemas, security/authentication code, downstream clients, outbox code, service layer, and tests before changing API contracts.
3. Run formatting, linting, type-checking, and tests that are already defined by each project. Record the exact command, exit code, and failure cause.
4. Start services only with safe development configuration and inspect `/openapi.json`; do not expose a dev server to the public internet.
5. Create `AUDIT_REPORT.md` at the repository root. It must contain: date, scope, architecture diagram, endpoint/auth matrix, findings ranked Critical/High/Medium/Low, proof for every finding, remediation, test evidence, and unresolved external dependencies.

Do not label something a bug based only on a README. Confirm it with code, schemas, or a reproducible test. Fix all Critical and High findings within scope; fix Medium findings where low risk; list justified Low/unresolved findings.

## Phase 1 — required integration architecture

Implement this architecture. Requests from the desktop UI go to `BACKEND`; `BACKEND` uses private REST calls to a downstream service after an approved plan is queued; the outbox worker retries transient failure safely.

```text
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

Use distinct local development ports (the current defaults suggest `BACKEND=8000`, `APPDEVELOPER=8001`, `LLMDEPLOYER=8002`). Resolve any Docker Compose port collision. Add/update root-level development documentation explaining startup order and all required environment variables without revealing values.

### Public BFF contract to retain or implement

Use a versioned `/v1` REST API, JSON request and response bodies, descriptive errors, and consistent status codes. Keep backward compatibility where possible; version a breaking change instead of silently changing a shape.

| User flow | BFF REST operation | Existing behavior to validate |
|---|---|---|
| Start planning | `POST /v1/sessions` with `{ "initial_message": string, "client_request_id"?: UUID }` | Returns `201` session snapshot. |
| Continue planning | `POST /v1/sessions/{id}/turns` and `POST /v1/sessions/{id}/answers` | Use `{ "message": string }` and `{ "answers": object }`. |
| Read planning state | `GET /v1/sessions/{id}`, `/questions`, and `/proposal` | Proposal response includes the selected plan version and citations. |
| Human approval | `POST /v1/sessions/{id}/approval` | Requires `{ "action": "approve" | "request_changes" | "cancel", "plan_version": integer, "feedback"?: string }`. |
| Handoff result | `GET /v1/sessions/{id}/handoff`; retry with `POST /v1/sessions/{id}/handoff/retry` | Do not claim success before downstream acceptance is persisted. |
| Cancel | `POST /v1/sessions/{id}/cancel` | Enforce the state machine. |

Expose authenticated live session events through the existing `GET`-equivalent WebSocket path `/v1/sessions/{id}/events` only if it is functional. The UI must also poll/refetch REST state after reconnect or an unknown event, because event delivery is not its source of truth. Define and document event envelopes such as `{ "type": string, "payload": object, "sequence"?: number }`; avoid relying on undocumented ad-hoc payloads.

### Private downstream REST contracts

Do not have the browser forward the planning package. `BACKEND` must own the package transformation, state transitions, correlation IDs, error handling, and audit records.

| Target | Command path | Required body / response behavior |
|---|---|---|
| APPDEVELOPER | `POST /v1/jobs` | Send a validated rendering of the approved planning package as `{ "prompt": string }`; accept `201` `JobResponse` and persist its `job_id` and state in the handoff receipt. |
| LLMDEPLOYER | `POST /api/sessions`, then `POST /api/sessions/{id}/answers` | Create a deployment session, translate the approved package into the exact `UserRequirements` answers shape, require a successful response for both calls, then persist downstream session ID and status. |
| Downstream tracking | existing downstream read endpoints, reached only by `BACKEND` | Add BFF read-only aggregation/proxy endpoints only if the desktop UI needs job artifacts, job progress, or deployment messages. Apply tenant/owner authorization before every proxy call and do not expose provider credentials. |

### Correctness requirements for the handoff

1. Fix the approval endpoint so it uses the existing `ProposalService.handle_approval()` or one single equivalent code path. Approval must atomically create exactly one outbox record for the approved `(session_id, plan_version)`, transition `AWAITING_APPROVAL -> HANDOFF_QUEUED`, and publish `handoff_queued`. It must not merely return `{ "status": "approved" }`.
2. Enforce a unique `(session_id, plan_version)` outbox record and reuse its stored idempotency key on every retry. Do not generate a new idempotency key per attempt.
3. Make the `BACKEND -> APPDEVELOPER` authentication compatible: the receiving service currently checks `X-API-Key`, while the existing caller appears to send a Bearer header. Choose and document one private-service authentication contract and implement it consistently. Prefer `X-API-Key` for this existing service unless you deliberately upgrade both sides. Test unauthorized, wrong-key, and valid-key requests.
4. Add authentication and authorization to LLMDEPLOYER private REST and WebSocket routes before exposing them outside a trusted local network. Its current permissive CORS and lack of dependency checks must be audited. Backend-to-LLMDeployer credentials must be configured separately from user credentials.
5. Call `raise_for_status()` (or equivalent explicit success handling) for every downstream REST operation, including LLMDEPLOYER answer submission. On failure preserve the useful sanitized error, increment retry count, set `HANDOFF_FAILED` only when retry policy is exhausted, and do not create a successful receipt.
6. Persist and return the real downstream ID and downstream state in the handoff receipt. Never replace these with empty strings or an unverified `accepted` state.
7. Propagate a stable `X-Correlation-ID`, FDE session ID, plan version, and idempotency key. Log only redacted/safe metadata.
8. Bound HTTP connect/read/write/pool timeouts, retry only retryable network/5xx errors, and avoid retrying a request after a non-idempotent ambiguous failure unless the downstream accepts the idempotency key.
9. Use a database transaction around state, outbox, and audit changes. Add concurrency tests for double-click approval and worker retry.
10. Validate and sanitize all user-controlled values. Keep path traversal protection and secret redaction intact. Never return internal exception strings, tokens, or planning package secrets to the renderer.

### Required integration tests

Implement tests using `httpx` transport/mocks (not live cloud APIs) proving all of the following:

- valid AppDeveloper route: approve -> one queued outbox item -> authenticated `POST /v1/jobs` -> receipt contains returned `job_id` -> session becomes `HANDED_OFF`;
- valid LLMDeployer route: both REST calls succeed -> receipt contains downstream session ID -> session becomes `HANDED_OFF`;
- downstream 401/403, validation 4xx, 5xx, timeout, and malformed JSON do not mark a handoff complete;
- repeated approval/retry cannot duplicate a downstream job/session;
- unauthorized tenant cannot read, cancel, approve, retry, or proxy another tenant's session;
- state transition and stale `plan_version` checks reject invalid requests;
- CORS preflight allows only configured desktop development/production origins; no `*` plus credentials;
- WebSocket authentication, unknown session, reconnect/refetch, and event envelope parsing work;
- all existing tests still pass or have a documented, justified update.

## Phase 2 — OpenCode desktop UI adaptation

OpenCode is a third-party upstream project. Its official contribution documentation identifies `packages/app` as the shared SolidJS web UI and `packages/desktop` as the native desktop wrapper. Use a pinned commit/tag and record the exact upstream URL, commit SHA, date, license, copied directories, and local modifications in `FRONTEND/UPSTREAM.md`.

1. Inspect the upstream repository before copying. Do not copy its server, TUI, agent runtime, provider integrations, plugins, or source-control implementation. Bring over only the desktop renderer/UI components, design tokens, icon assets, and the minimum desktop wrapper/build configuration needed to run them.
2. Create `FRONTEND/` as a standalone, reproducible project. Its README must state the runtime/package-manager version, install command, dev command, production build command, test command, environment variables, and how it connects to `BACKEND`.
3. Retain the desktop-only visual language: desktop window shell/title bar, compact navigation rail, session list, conversation surface, input composer, streaming/progress presentation, keyboard navigation, responsive panes, light/dark theme, accessibility focus states, and empty/error/loading states. Do not ship a mobile-first experience.
4. Replace upstream data stores, generated SDK calls, hooks, and domain types with a small typed FDE API client. Keep API-base URL configuration in `FRONTEND/.env.example` (for example `VITE_FDE_API_BASE_URL` and `VITE_FDE_WS_BASE_URL`). Do not hard-code `localhost` in production code.
5. Keep the API key/user token out of source control and out of renderer logs. In a desktop wrapper, obtain it through a narrow, validated IPC/settings boundary or a user-entered local setting; do not expose filesystem, shell, arbitrary IPC, or cloud credentials to UI components.
6. Use REST for every mutation and initial/refreshed query. Use WebSocket only for progress notifications. Implement exponential reconnect with jitter, cleanup on component unmount, a visible connection state, and a REST refetch after reconnect. Limit rendered event history to prevent unbounded memory use.
7. Treat HTTP errors as errors: `fetch()` resolving does not mean success. Parse the documented error shape defensively, present a safe human-readable message, and retain enough correlation ID information for support.

### UI capability map — implement only these

| UI area | Backed by FDE capability | Required behavior |
|---|---|---|
| New planning session | `POST /v1/sessions` | Create session from prompt and select it. |
| Planning conversation | session turns, questions, answers, proposal | Render assistant updates, typed question controls (text/single/multi/number/boolean), and route all responses through BFF REST. |
| Proposal review | proposal GET and approval POST | Render architecture, risks, assumptions, alternatives, delivery phases, and official documentation citations as external links. Require explicit approve/request-changes/cancel action and current plan version. |
| Session timeline/status | session GET, handoff GET, session events | Show state machine status, retryable failures, downstream receipt ID/status, live updates, and an accessible reconnect indicator. |
| App-development handoff | BFF handoff and any authenticated BFF aggregation endpoint actually implemented | Show only job information/files/progress exposed safely by the BFF. |
| LLM-deployment handoff | BFF handoff and any authenticated BFF aggregation endpoint actually implemented | Show only deployment state/messages returned by the BFF. |
| Cancellation/retry | session cancel/handoff retry | Show confirmation, disable during request, and refresh REST state afterward. |

### Remove or disable upstream functionality that this backend does not support

Remove—not merely hide with a dead click handler—OpenCode-specific project/worktree selection, local filesystem browsing/editing, terminal/shell execution, patch/diff editing, Git/VCS operations, git commits/PRs, provider/model/account management, OpenCode agent switching, MCP/plugin/command management, IDE integrations, sharing/sync/cloud workspaces, OpenCode server configuration, updater/telemetry settings unrelated to this application, and any direct OpenCode API calls.

Do not pretend that APPDEVELOPER's optional GitHub push endpoint is a generic desktop Git client. If a BFF-mediated, explicit consent flow is not implemented and tested, omit it entirely from the UI.

### Desktop security and usability

- Use least-privilege native IPC; validate every message and expose no generic `invoke`, process, shell, or filesystem bridge.
- Restrict the renderer Content Security Policy to required local assets and configured API/WebSocket origins. Do not use `unsafe-eval`; avoid `unsafe-inline` where the upstream build permits.
- Allow CORS origins explicitly. In production use the desktop wrapper origin/custom protocol that is actually used; in development use the known local dev origin. Do not configure `allow_origins=["*"]` together with credentials.
- Provide keyboard navigation, visible focus, semantic controls/labels, color contrast, screen-reader announcements for handoff/progress/error state, and no color-only status signal.
- Test desktop rendering at common laptop widths and high-DPI scaling. No blank screen when BACKEND is down: show a recoverable connection panel.

## Phase 3 — audit checklist

Audit and fix issues found in the following categories, documenting evidence in `AUDIT_REPORT.md`:

- API/contract drift among README, router, Pydantic model, client, tests, and Docker environment;
- authentication, tenant isolation, CORS, CSRF/cookie assumptions, WebSocket auth, rate limits, request size limits, security headers, secret redaction, and unsafe error exposure;
- state-machine integrity, transactions, idempotency, outbox locks/recovery, background task cancellation, retry/backoff, timeout behavior, and duplicate delivery;
- Pydantic mutable defaults, async resource lifecycle, database migrations, SQLite/Postgres compatibility, unbounded in-memory sessions/connections/messages, race conditions, and shutdown cleanup;
- frontend type safety, build reproducibility, dependency audit, license compliance, CSP/IPC safety, API error behavior, UI accessibility, and removal of unsupported features.

For every fix: add or adjust a focused regression test. Do not lower test coverage thresholds to make the build pass. Prefer small, explicit changes over rewrites.

## Completion checklist and final response

Only finish after all applicable items are true:

- `FRONTEND/` builds and tests successfully from a clean install.
- All three services have verified, documented REST contracts and compatible private authentication.
- Approved plans create a durable outbox entry and hand off exactly once under retry/concurrency tests.
- The new desktop UI talks only to `BACKEND`, presents only supported FDE functionality, and has functioning REST refresh plus WebSocket progress.
- CORS/WebSocket/security issues have been corrected and tested.
- `AUDIT_REPORT.md`, `FRONTEND/README.md`, `FRONTEND/UPSTREAM.md`, `.env.example` updates, and developer startup instructions exist.
- Final response lists changed files, tests run and results, fixed findings, anything intentionally not implemented, exact upstream OpenCode commit, and manual commands to run the stack.

## Required reference links

Use these official sources while implementing; cite them in `AUDIT_REPORT.md`/`FRONTEND/UPSTREAM.md` where relevant:

- [OpenCode source repository](https://github.com/anomalyco/opencode)
- [OpenCode contribution guide: package layout and desktop development](https://github.com/anomalyco/opencode/blob/dev/CONTRIBUTING.md)
- [OpenCode server/API documentation](https://dev.opencode.ai/docs/server/)
- [FastAPI CORS documentation](https://fastapi.tiangolo.com/tutorial/cors/)
- [FastAPI WebSocket reference](https://fastapi.tiangolo.com/reference/websockets/)
- [MDN Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)
- [MDN WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [OWASP REST Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html)
