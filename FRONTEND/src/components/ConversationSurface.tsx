import { createSignal, For, Show } from "solid-js";
import type { WebSocketEvent } from "../api/types";

interface ConversationSurfaceProps {
  messages: Array<{ role: string; content: string; timestamp?: string }>;
  isStreaming: boolean;
}

export default function ConversationSurface(props: ConversationSurfaceProps) {
  return (
    <div style={{ flex: 1, overflow: "auto", padding: "16px" }}>
      <Show when={props.messages.length > 0} fallback={
        <div style={{ color: "#9ca3af", "text-align": "center", "padding-top": "40px", "font-size": "14px" }}>
          Send a message to start planning
        </div>
      }>
        <For each={props.messages}>
          {(msg) => (
            <div style={{
              "margin-bottom": "12px",
              "text-align": msg.role === "user" ? "right" : "left",
            }}>
              <div style={{
                display: "inline-block",
                padding: "8px 12px",
                "border-radius": "8px",
                background: msg.role === "user" ? "#3b82f6" : "#f3f4f6",
                color: msg.role === "user" ? "white" : "#374151",
                "max-width": "80%",
                "font-size": "14px",
                "text-align": "left",
                "word-wrap": "break-word",
              }}>
                {msg.content}
              </div>
              <Show when={msg.timestamp}>
                <div style={{ "font-size": "11px", color: "#9ca3af", "margin-top": "2px" }}>
                  {new Date(msg.timestamp!).toLocaleTimeString()}
                </div>
              </Show>
            </div>
          )}
        </For>
      </Show>
      <Show when={props.isStreaming}>
        <div style={{ "text-align": "left", padding: "8px 0" }}>
          <span style={{ color: "#9ca3af", "font-size": "13px" }}>Thinking...</span>
        </div>
      </Show>
    </div>
  );
}
