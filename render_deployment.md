# Render Deployment Guide

Deploy the FDE platform as 5 separate services on Render from a single Git repo (monorepo). Each service has its own subdirectory and Dockerfile/build config.

## Render Service Types Used

| FDE Component | Render Service Type | Why |
|---------------|-------------------|-----|
| FRONTEND | **Static Site** (`type: web`, `runtime: static`) | Pure SPA (SolidJS + Vite). No server-side logic. Served via global CDN. Free tier eligible. |
| BACKEND API | **Web Service** (`type: web`, `runtime: docker`) | FastAPI server handling HTTP requests + WebSocket connections on a port. Needs public URL. |
| APPDEVELOPER | **Private Service** (`type: pserv`, `runtime: docker`) | Only BACKEND's outbox worker calls it (not public-facing). Receives traffic only over Render's private network. |
| LLMDEPLOYER | **Private Service** (`type: pserv`, `runtime: docker`) | Only BACKEND's outbox worker calls it (not public-facing). Receives traffic only over Render's private network. |
| BACKEND Worker | **Background Worker** (`type: worker`, `runtime: docker`) | Polls the outbox DB table continuously. Never receives incoming traffic. |

### Why Private Services for APPDEVELOPER and LLMDEPLOYER?

Per Render docs: "Private services are just like web services, with one exception: they aren't reachable via the public internet. They are reachable by your other Render services on the same private network."

APPDEVELOPER and LLMDEPLOYER are internal microservices — only BACKEND's outbox worker calls them. They don't need public URLs. Using Private Services:
- Saves cost (no public load balancer)
- Improves security (no public attack surface)
- Enables faster internal communication via Render's private network
- BACKEND references them via their internal hostname (e.g., `appdeveloper:8001` on the private network)

---

## Service 1: FRONTEND (Static Site)

| Setting | Value |
|---------|-------|
| **Name** | `fde-frontend` |
| **Type** | Static Site (`type: web`, `runtime: static`) |
| **Root Directory** | `FRONTEND` |
| **Build Command** | `npm ci && npm run build` |
| **Publish Directory** | `dist` |
| **Rewrite Rules** | `/* → /index.html` (SPA fallback — required for client-side routing) |

**Environment Variables (build-time only — baked into the JS bundle):**
```
VITE_CLERK_PUBLISHABLE_KEY=pk_live_xxxxxxxxxxxx
VITE_FDE_API_BASE_URL=https://fde-backend.onrender.com
VITE_FDE_WS_BASE_URL=wss://fde-backend.onrender.com
```

> **Note:** Static sites have no runtime env vars. Changing these requires a rebuild.

---

## Service 2: BACKEND (Web Service — public)

| Setting | Value |
|---------|-------|
| **Name** | `fde-backend` |
| **Type** | Web Service (`type: web`, `runtime: docker`) |
| **Root Directory** | `BACKEND` |
| **Dockerfile Path** | `./Dockerfile` |
| **Port** | `8000` (set via `PORT` env var or Docker EXPOSE) |
| **Health Check Path** | `/healthz` |

> This is the only public-facing backend. It handles user auth, WebSocket connections, and proxies work to private downstream services.

**Environment Variables:**
```
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://<neon-connection-string>?ssl=require
REDIS_URL=rediss://<upstash-connection-string>
CLERK_JWKS_URL=https://<your-clerk-frontend-api>.clerk.accounts.dev/.well-known/jwks.json
CLERK_PUBLISHABLE_KEY=pk_live_xxxxxxxxxxxx
FDE_API_KEY=<your-service-api-key>
ANTHROPIC_BASE_URL=<your-litellm-proxy-url>
ANTHROPIC_API_KEY=<your-proxy-api-key>
FDE_CLAUDE_MODEL=<your-model-alias>
PLANNER_MODE=real
APPDEVELOPER_BASE_URL=http://fde-appdeveloper:8001
APPDEVELOPER_API_KEY=<shared-appdev-key>
LLMDEPLOYER_BASE_URL=http://fde-llmdeployer:8002
LLMDEPLOYER_API_KEY=<shared-deploy-key>
OUTBOX_POLL_SECONDS=2
```

> **Important:** `APPDEVELOPER_BASE_URL` and `LLMDEPLOYER_BASE_URL` use **internal hostnames** (Render private network), not public URLs. Format: `http://<service-name>:<port>`.

---

## Service 3: APPDEVELOPER (Private Service)

| Setting | Value |
|---------|-------|
| **Name** | `fde-appdeveloper` |
| **Type** | Private Service (`type: pserv`, `runtime: docker`) |
| **Root Directory** | `APPDEVELOPER` |
| **Dockerfile Path** | `./Dockerfile` |
| **Port** | `8001` |

> Private Service = reachable only by other Render services on the same private network. Not publicly accessible.

**Environment Variables:**
```
APPDEVELOPER_API_KEY=<shared-appdev-key>
ANTHROPIC_BASE_URL=<your-litellm-proxy-url>
ANTHROPIC_API_KEY=<your-proxy-api-key>
ANTHROPIC_MODEL=<your-model-alias>
DAYTONA_API_KEY=<your-daytona-key>
DAYTONA_API_URL=https://app.daytona.io/api
DAYTONA_TARGET=us
DATABASE_URL=sqlite+aiosqlite:///./appdeveloper.db
APPDEVELOPER_WORKSPACE_ROOT=/workspaces
```

**Disk:** Attach a persistent disk at `/workspaces` if you want generated code to survive redeploys (optional — Daytona sandboxes handle isolation regardless).

---

## Service 4: LLMDEPLOYER (Private Service)

| Setting | Value |
|---------|-------|
| **Name** | `fde-llmdeployer` |
| **Type** | Private Service (`type: pserv`, `runtime: docker`) |
| **Root Directory** | `LLMDEPLOYER` |
| **Dockerfile Path** | `./Dockerfile` |
| **Port** | `8002` |

> Private Service = reachable only by other Render services on the same private network. Not publicly accessible.

**Environment Variables:**
```
LLMDEPLOYER_API_KEY=<shared-deploy-key>
ANTHROPIC_BASE_URL=<your-litellm-proxy-url>
ANTHROPIC_API_KEY=<your-proxy-api-key>
CLAUDE_MODEL=<your-model-alias>
TAVILY_API_KEY=<your-tavily-key>
DAYTONA_API_KEY=<your-daytona-key>
DAYTONA_API_URL=https://app.daytona.io/api
DAYTONA_TARGET=us
RUNPOD_API_KEY=<if-using-runpod>
MODAL_TOKEN_ID=<if-using-modal>
MODAL_TOKEN_SECRET=<if-using-modal>
AZURE_TENANT_ID=<if-using-azure>
AZURE_CLIENT_ID=<if-using-azure>
AZURE_CLIENT_SECRET=<if-using-azure>
AZURE_SUBSCRIPTION_ID=<if-using-azure>
NGC_API_KEY=<if-using-nim>
```

---

## Service 5: BACKEND Worker (Background Worker)

| Setting | Value |
|---------|-------|
| **Name** | `fde-backend-worker` |
| **Type** | Background Worker (`type: worker`, `runtime: docker`) |
| **Root Directory** | `BACKEND` |
| **Dockerfile Path** | `./Dockerfile` |
| **Docker Command Override** | `python -m app.workers.main` |

> Background Workers run continuously but **never receive incoming traffic** (no port, no health check). Perfect for the outbox poller which only initiates outbound requests to private services.

**Environment Variables:** Same as Service 2 (BACKEND). Copy all env vars.

---

## Post-Deploy Checklist

1. **Region:** Deploy ALL services in the **same Render region** (required for private network communication)
2. **CORS:** Update BACKEND's `cors_origins` to include your Render frontend URL: `https://fde-frontend.onrender.com`
3. **Clerk:** Add `https://fde-frontend.onrender.com` to Clerk's allowed origins in the Dashboard
4. **API key consistency:** Ensure `APPDEVELOPER_API_KEY` matches between BACKEND and APPDEVELOPER; same for `LLMDEPLOYER_API_KEY`
5. **Private network URLs:** BACKEND and Worker must reference downstream services by their **internal hostnames** (`http://fde-appdeveloper:8001`, `http://fde-llmdeployer:8002`) — NOT public `.onrender.com` URLs
6. **Health checks:** BACKEND has `/healthz`. Private services don't need health check paths (Render monitors the process).
7. **WebSocket:** Render supports WSS natively on Web Services — the `wss://fde-backend.onrender.com` URL works out of the box
8. **Database:** BACKEND auto-creates tables on first startup (no migration step needed)
9. **Persistent disk:** Optional for APPDEVELOPER at `/workspaces` (only if you want local artifacts to survive redeploys)

---

## Render Blueprint (`render.yaml`)

Place this at the repo root for infrastructure-as-code deployment:

```yaml
services:
  # --- FRONTEND: Static Site (global CDN, free tier) ---
  - type: web
    runtime: static
    name: fde-frontend
    rootDir: FRONTEND
    buildCommand: npm ci && npm run build
    staticPublishPath: dist
    pullRequestPreviewsEnabled: true
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
    headers:
      - path: /assets/*
        name: Cache-Control
        value: "public, max-age=31536000, immutable"
    envVars:
      - key: VITE_CLERK_PUBLISHABLE_KEY
        sync: false
      - key: VITE_FDE_API_BASE_URL
        sync: false
      - key: VITE_FDE_WS_BASE_URL
        sync: false

  # --- BACKEND API: Web Service (public, receives user traffic) ---
  - type: web
    runtime: docker
    name: fde-backend
    rootDir: BACKEND
    dockerfilePath: ./Dockerfile
    healthCheckPath: /healthz
    envVars:
      - key: APP_ENV
        value: production
      - key: DATABASE_URL
        sync: false
      - key: REDIS_URL
        sync: false
      - key: CLERK_JWKS_URL
        sync: false
      - key: CLERK_PUBLISHABLE_KEY
        sync: false
      - key: FDE_API_KEY
        sync: false
      - key: ANTHROPIC_BASE_URL
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: FDE_CLAUDE_MODEL
        sync: false
      - key: PLANNER_MODE
        value: real
      - key: APPDEVELOPER_BASE_URL
        value: http://fde-appdeveloper:8001
      - key: APPDEVELOPER_API_KEY
        sync: false
      - key: LLMDEPLOYER_BASE_URL
        value: http://fde-llmdeployer:8002
      - key: LLMDEPLOYER_API_KEY
        sync: false
      - key: OUTBOX_POLL_SECONDS
        value: "2"

  # --- BACKEND WORKER: Background Worker (polls outbox, no incoming traffic) ---
  - type: worker
    runtime: docker
    name: fde-backend-worker
    rootDir: BACKEND
    dockerfilePath: ./Dockerfile
    dockerCommand: python -m app.workers.main
    envVars:
      - fromService:
          type: web
          name: fde-backend
          envVarKey: DATABASE_URL
      - fromService:
          type: web
          name: fde-backend
          envVarKey: REDIS_URL
      - key: APPDEVELOPER_BASE_URL
        value: http://fde-appdeveloper:8001
      - fromService:
          type: web
          name: fde-backend
          envVarKey: APPDEVELOPER_API_KEY
      - key: LLMDEPLOYER_BASE_URL
        value: http://fde-llmdeployer:8002
      - fromService:
          type: web
          name: fde-backend
          envVarKey: LLMDEPLOYER_API_KEY

  # --- APPDEVELOPER: Private Service (internal only, not public) ---
  - type: pserv
    runtime: docker
    name: fde-appdeveloper
    rootDir: APPDEVELOPER
    dockerfilePath: ./Dockerfile
    envVars:
      - key: APPDEVELOPER_API_KEY
        sync: false
      - key: ANTHROPIC_BASE_URL
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: ANTHROPIC_MODEL
        sync: false
      - key: DAYTONA_API_KEY
        sync: false
      - key: DAYTONA_API_URL
        value: https://app.daytona.io/api
      - key: DAYTONA_TARGET
        value: us

  # --- LLMDEPLOYER: Private Service (internal only, not public) ---
  - type: pserv
    runtime: docker
    name: fde-llmdeployer
    rootDir: LLMDEPLOYER
    dockerfilePath: ./Dockerfile
    envVars:
      - key: LLMDEPLOYER_API_KEY
        sync: false
      - key: ANTHROPIC_BASE_URL
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: CLAUDE_MODEL
        sync: false
      - key: TAVILY_API_KEY
        sync: false
      - key: DAYTONA_API_KEY
        sync: false
      - key: DAYTONA_API_URL
        value: https://app.daytona.io/api
      - key: DAYTONA_TARGET
        value: us
```

---

## Architecture on Render

```
                    PUBLIC INTERNET
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               │
  ┌─────────────┐  ┌──────────────┐     │
  │  FRONTEND   │  │   BACKEND    │     │
  │ Static Site │  │ Web Service  │     │
  │  (CDN)      │  │  :8000       │     │
  │  :5173      │──│  (public)    │     │
  └─────────────┘  └──────┬───────┘     │
                           │             │
              ─────────────┼─────────────┼───── RENDER PRIVATE NETWORK ─────
                           │             │
         ┌─────────────────┼─────────────┘
         │                 │
         ▼                 ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
  │ APPDEVELOPER │  │ LLMDEPLOYER  │  │ BACKEND WORKER   │
  │ Private Svc  │  │ Private Svc  │  │ Background Worker│
  │ :8001        │  │ :8002        │  │ (no port)        │
  │ (internal)   │  │ (internal)   │  │ polls outbox     │
  └──────────────┘  └──────────────┘  └──────────────────┘
```

- Only BACKEND has a public URL (user-facing API + WebSocket)
- FRONTEND is a static CDN (no server process)
- APPDEVELOPER + LLMDEPLOYER are private (internal network only)
- BACKEND Worker is a background process (initiates requests, receives none)
- All inter-service calls stay on Render's private network (faster, no public egress)
- User auth is Clerk JWT verified by BACKEND via JWKS
