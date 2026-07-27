import { Show, For, createSignal } from "solid-js";
import type { SessionSnapshot } from "../api/types";

interface SessionListProps {
  sessions: SessionSnapshot[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

function stateColor(state: string): string {
  switch (state) {
    case "HANDED_OFF": return "#22c55e";
    case "HANDOFF_QUEUED": return "#f59e0b";
    case "AWAITING_APPROVAL": return "#3b82f6";
    case "AWAITING_ANSWERS": return "#8b5cf6";
    case "DISCOVERING": return "#6b7280";
    case "FAILED":
    case "HANDOFF_FAILED": return "#ef4444";
    case "CANCELLED": return "#9ca3af";
    default: return "#6b7280";
  }
}

export default function SessionList(props: SessionListProps) {
  return (
    <div class="session-list" style={{ "min-width": "240px", "max-width": "300px", "border-right": "1px solid #e5e7eb", height: "100vh", display: "flex", "flex-direction": "column" }}>
      <div style={{ padding: "12px", "border-bottom": "1px solid #e5e7eb", display: "flex", "justify-content": "space-between", "align-items": "center" }}>
        <h2 style={{ margin: 0, "font-size": "14px", "font-weight": 600 }}>Sessions</h2>
        <button
          onClick={props.onNew}
          style={{ "font-size": "12px", padding: "4px 8px", "border-radius": "4px", border: "1px solid #d1d5db", background: "white", cursor: "pointer" }}
        >
          + New
        </button>
      </div>
      <div style={{ flex: 1, overflow: "auto" }}>
        <Show
          when={props.sessions.length > 0}
          fallback={
            <div style={{ padding: "16px", color: "#9ca3af", "text-align": "center", "font-size": "13px" }}>
              No sessions yet
            </div>
          }
        >
          <For each={props.sessions}>
            {(session) => (
              <div
                onClick={() => props.onSelect(session.id)}
                style={{
                  padding: "10px 12px",
                  cursor: "pointer",
                  "border-bottom": "1px solid #f3f4f6",
                  background: props.selectedId === session.id ? "#f0f9ff" : "white",
                  "font-size": "13px",
                }}
              >
                <div style={{ display: "flex", "align-items": "center", gap: "6px" }}>
                  <span style={{ width: "8px", height: "8px", "border-radius": "50%", background: stateColor(session.state), display: "inline-block" }} />
                  <span style={{ "font-family": "monospace", "font-size": "12px" }}>
                    {session.id.slice(0, 8)}...
                  </span>
                </div>
                <div style={{ "font-size": "11px", color: "#6b7280", "margin-top": "2px" }}>
                  {session.state}
                  <Show when={session.route}>
                    <span style={{ "margin-left": "4px", padding: "1px 4px", background: "#f3f4f6", "border-radius": "3px", "font-size": "10px" }}>
                      {session.route}
                    </span>
                  </Show>
                </div>
              </div>
            )}
          </For>
        </Show>
      </div>
    </div>
  );
}
