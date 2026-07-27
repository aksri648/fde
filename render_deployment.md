# Render Deployment Guide

Deploy the FDE platform as 5 separate services on Render from a single Git repo (monorepo). Each service has its own subdirectory and Dockerfile/build config.

---

## Service 1: FRONTEND (Static Site)

| Setting | Value |
|---------|-------|
| **Name** | `fde-frontend` |
| **Type** | Static Site |
| **Root Directory** | `FRONTEND` |
| **Build Command** | `npm install && npm run build` |
| **Publish Directory** | `FRONTEND/dist` |
| **Redirect/Rewrite Rules** | `/* → /index.html` (SPA fallback) |

**Environment Variables:**
```
VITE_CLERK_PUBLISHABLE_KEY=pk_live_xxxxxxxxxxxx
VITE_FDE_API_BASE_URL=https://fde-backend.onrender.com
VITE_FDE_WS_BASE_URL=wss://fde-backend.onrender.com
```

---

## Service 2: BACKEND (Web Service)

| Setting | Value |
|---------|-------|
| **Name** | `fde-backend` |
| **Type** | Web Service |
| **Runtime** | Docker |
| **Root Directory** | `BACKEND` |
| **Dockerfile Path** | `./Dockerfile` |
| **Port** | `8000` |
| **Health Check Path** | `/healthz` |

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
APPDEVELOPER_BASE_URL=https://fde-appdeveloper.onrender.com
APPDEVELOPER_API_KEY=<shared-appdev-key>
LLMDEPLOYER_BASE_URL=https://fde-llmdeployer.onrender.com
LLMDEPLOYER_API_KEY=<shared-deploy-key>
OUTBOX_POLL_SECONDS=2
```

---

## Service 3: APPDEVELOPER (Web Service)

| Setting | Value |
|---------|-------|
| **Name** | `fde-appdeveloper` |
| **Type** | Web Service |
| **Runtime** | Docker |
| **Root Directory** | `APPDEVELOPER` |
| **Dockerfile Path** | `./Dockerfile` |
| **Port** | `8001` |
| **Health Check Path** | `/healthz` |

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

## Service 4: LLMDEPLOYER (Web Service)

| Setting | Value |
|---------|-------|
| **Name** | `fde-llmdeployer` |
| **Type** | Web Service |
| **Runtime** | Docker |
| **Root Directory** | `LLMDEPLOYER` |
| **Dockerfile Path** | `./Dockerfile` |
| **Port** | `8002` |
| **Health Check Path** | `/api/health` |

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
| **Type** | Background Worker (or Web Service with no port) |
| **Runtime** | Docker |
| **Root Directory** | `BACKEND` |
| **Dockerfile Path** | `./Dockerfile` |
| **Start Command Override** | `python -m app.workers.main` |

**Environment Variables:** Same as Service 2 (BACKEND). Copy all env vars.

---

## Post-Deploy Checklist

1. **CORS:** Update BACKEND's `cors_origins` in config (or add env var) to include your Render frontend URL: `https://fde-frontend.onrender.com`
2. **Clerk:** Add `https://fde-frontend.onrender.com` to Clerk's allowed origins in the Dashboard
3. **API key consistency:** Ensure `APPDEVELOPER_API_KEY` matches between BACKEND and APPDEVELOPER services; same for `LLMDEPLOYER_API_KEY`
4. **Health checks:** Verify `/healthz` (BACKEND, APPDEVELOPER) and `/api/health` (LLMDEPLOYER) respond 200
5. **WebSocket:** Render supports WSS natively on Web Services — the `wss://` URL works with the same service URL
6. **Database:** BACKEND auto-creates tables on first startup (no migration step needed)

---

## Render Blueprint (`render.yaml`)

Place this at the repo root for infrastructure-as-code deployment:

```yaml
services:
  - type: web
    name: fde-backend
    runtime: docker
    rootDir: BACKEND
    dockerfilePath: ./Dockerfile
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
        sync: false
      - key: APPDEVELOPER_API_KEY
        sync: false
      - key: LLMDEPLOYER_BASE_URL
        sync: false
      - key: LLMDEPLOYER_API_KEY
        sync: false
      - key: OUTBOX_POLL_SECONDS
        value: "2"

  - type: worker
    name: fde-backend-worker
    runtime: docker
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
      - fromService:
          type: web
          name: fde-backend
          envVarKey: APPDEVELOPER_BASE_URL
      - fromService:
          type: web
          name: fde-backend
          envVarKey: APPDEVELOPER_API_KEY
      - fromService:
          type: web
          name: fde-backend
          envVarKey: LLMDEPLOYER_BASE_URL
      - fromService:
          type: web
          name: fde-backend
          envVarKey: LLMDEPLOYER_API_KEY

  - type: web
    name: fde-appdeveloper
    runtime: docker
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

  - type: web
    name: fde-llmdeployer
    runtime: docker
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

  - type: web
    name: fde-frontend
    buildCommand: npm install && npm run build
    staticPublishPath: dist
    rootDir: FRONTEND
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
    envVars:
      - key: VITE_CLERK_PUBLISHABLE_KEY
        sync: false
      - key: VITE_FDE_API_BASE_URL
        sync: false
      - key: VITE_FDE_WS_BASE_URL
        sync: false
```

---

## Architecture Reminder

```
FRONTEND (Static)  →  BACKEND (API + WS)  →  APPDEVELOPER (code gen)
     :5173                :8000           ↗       :8001
                              ↘
                          LLMDEPLOYER (deployment)
                              :8002

BACKEND Worker (polls outbox, delivers handoffs to downstream services)
```

All inter-service calls use `X-API-Key` auth. User auth is Clerk JWT verified by BACKEND via JWKS.
