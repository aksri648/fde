import { Show } from "solid-js";

interface ConnectionIndicatorProps {
  connected: boolean;
}

export default function ConnectionIndicator(props: ConnectionIndicatorProps) {
  return (
    <div style={{ display: "flex", "align-items": "center", gap: "6px", "font-size": "12px", color: "#6b7280" }}>
      <span
        style={{
          width: "8px",
          height: "8px",
          "border-radius": "50%",
          background: props.connected ? "#22c55e" : "#ef4444",
          display: "inline-block",
        }}
      />
      <Show when={props.connected} fallback={<span>Disconnected</span>}>
        <span>Connected</span>
      </Show>
    </div>
  );
}
