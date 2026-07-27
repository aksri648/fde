# FDE Desktop Frontend

SolidJS desktop application for the FDE planning and routing system.

## Runtime Requirements

- **Node.js**: >= 20.0.0
- **Package Manager**: npm >= 10.0.0 (or bun/pnpm)

## Setup

```bash
cd FRONTEND
cp .env.example .env
# Edit .env with your API key if needed
npm install
```

## Development

```bash
npm run dev
# Opens at http://localhost:5173
```

The dev server proxies API requests to `http://localhost:8000` (BACKEND).

## Production Build

```bash
npm run build
npm run preview
```

## Testing

```bash
npm run test
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_FDE_API_BASE_URL` | Backend API base URL | `http://localhost:8000` |
| `VITE_FDE_WS_BASE_URL` | Backend WebSocket base URL | `ws://localhost:8000` |
| `VITE_FDE_API_KEY` | API key for authentication | (empty) |

## Architecture

```
FRONTEND/
├── src/
│   ├── api/
│   │   ├── client.ts          # Typed FDE API client (REST + WebSocket)
│   │   └── types.ts           # TypeScript types for API schemas
│   ├── components/
│   │   ├── SessionList.tsx     # Left sidebar session list
│   │   ├── ConversationSurface.tsx  # Chat message display
│   │   ├── InputComposer.tsx   # Message input with send
│   │   ├── QuestionPanel.tsx   # Follow-up question forms
│   │   ├── ProposalReview.tsx  # Architecture proposal review
│   │   ├── SessionStatus.tsx   # Session state and handoff info
│   │   ├── ConnectionIndicator.tsx  # WebSocket connection status
│   │   ├── EmptyState.tsx      # Welcome screen
│   │   └── NewSessionDialog.tsx # New session modal
│   ├── hooks/
│   │   └── useWebSocket.ts     # Reconnecting WebSocket hook
│   ├── stores/
│   │   └── session.ts          # Session state management
│   ├── styles/
│   │   └── globals.css         # Base styles
│   ├── App.tsx                 # Root application component
│   └── index.tsx               # Entry point
├── index.html                  # HTML entry
├── package.json                # Dependencies and scripts
├── tsconfig.json               # TypeScript configuration
├── vite.config.ts              # Vite build configuration
├── .env.example                # Environment variable template
├── .gitignore                  # Git ignore rules
├── UPSTREAM.md                 # Upstream reference documentation
└── README.md                   # This file
```

## UI Capability Map

| UI Area | FDE Capability | Behavior |
|---------|---------------|----------|
| New planning session | `POST /v1/sessions` | Create session from prompt |
| Planning conversation | turns, questions, answers | Render assistant updates, typed question controls |
| Proposal review | proposal GET, approval POST | Render architecture, risks, alternatives, citations |
| Session timeline/status | session GET, handoff GET | Show state machine, retryable failures |
| App-development handoff | BFF handoff | Show job info from BFF |
| LLM-deployment handoff | BFF handoff | Show deployment state from BFF |
| Cancellation/retry | cancel/handoff retry | Confirmation, disable during request |

## Connected Backend Services

- **BACKEND**: `http://localhost:8000` (public BFF)
- **WebSocket**: `ws://localhost:8000/v1/sessions/{id}/events`

## Security

- API key stored in `.env` (not committed)
- No filesystem/shell/IPC access from renderer
- CORS restricted to configured origins
- All API calls authenticated via Bearer token
- CSP headers should be configured in production

## Keyboard Shortcuts

- `Enter` - Send message
- `Shift+Enter` - New line in input
- `Tab` - Navigate between sessions (future)
