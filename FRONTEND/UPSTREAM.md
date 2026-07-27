# Upstream OpenCode Reference

## Source Repository

- **URL**: https://github.com/anomalyco/opencode
- **Branch**: dev
- **Commit SHA**: `4f62295e4432ad0fe21b597e79bcf060a7164106`
- **Date**: 2026-07-27T09:56:13Z
- **License**: MIT

## What Was Used

This frontend is **inspired by** the OpenCode desktop UI visual language but does not copy any source code directly. The following design principles were adapted:

- Desktop window shell with title bar
- Compact navigation rail (session list)
- Session list with state indicators
- Conversation surface with message bubbles
- Input composer at bottom
- Streaming/progress presentation
- Light/dark theme support (future)
- Keyboard navigation support
- Accessibility focus states

## What Was NOT Copied

Per the implementation prompt, the following upstream features were explicitly excluded:

- OpenCode server, TUI, agent runtime
- Provider/model/account management
- Plugin/MCP/command management
- Git/VCS operations
- Terminal/shell execution
- File system browsing/editing
- IDE integrations
- Cloud workspace sync
- OpenCode-specific project/worktree selection

## Local Modifications

All code in `FRONTEND/src/` was written from scratch for the FDE use case:

- `api/client.ts` - Typed FDE REST+WebSocket client
- `api/types.ts` - TypeScript types matching FDE API schemas
- `stores/session.ts` - FDE session state management
- `components/*` - Desktop UI components for FDE workflows
- `hooks/useWebSocket.ts` - Reconnecting WebSocket hook

## References

- [OpenCode GitHub](https://github.com/anomalyco/opencode)
- [OpenCode CONTRIBUTING.md](https://github.com/anomalyco/opencode/blob/dev/CONTRIBUTING.md)
- [OpenCode Server Docs](https://dev.opencode.ai/docs/server/)
