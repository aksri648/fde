import { Show } from "solid-js";
import type { SessionSnapshot, HandoffStatus } from "../api/types";

interface SessionStatusProps {
  session: SessionSnapshot;
  handoff?: HandoffStatus;
  onRetry?: () => void;
}

function stateLabel(state: string): string {
  switch (state) {
    case "DISCOVERING": return "Discovering";
    case "AWAITING_ANSWERS": return "Awaiting Answers";
    case "AWAITING_APPROVAL": return "Awaiting Approval";
    case "HANDOFF_QUEUED": return "Handoff Queued";
    case "HANDOFF_FAILED": return "Handoff Failed";
    case "HANDED_OFF": return "Handed Off";
    case "FAILED": return "Failed";
    case "CANCELLED": return "Cancelled";
    default: return state;
  }
}

function stateBadgeColor(state: string): string {
  switch (state) {
    case "HANDED_OFF": return "#dcfce7";
    case "HANDOFF_QUEUED":
    case "AWAITING_APPROVAL": return "#dbeafe";
    case "FAILED":
    case "HANDOFF_FAILED": return "#fee2e2";
    case "CANCELLED": return "#f3f4f6";
    default: return "#f3f4f6";
  }
}

export default function SessionStatus(props: SessionStatusProps) {
  return (
    <div style={{ padding: "8px 16px", "border-bottom": "1px solid #e5e7eb", display: "flex", "align-items": "center", gap: "12px", "font-size": "13px" }}>
      <span style={{ padding: "2px 8px", "border-radius": "12px", background: stateBadgeColor(props.session.state), "font-size": "12px", "font-weight": 500 }}>
        {stateLabel(props.session.state)}
      </span>
      <Show when={props.session.route}>
        <span style={{ color: "#6b7280" }}>
          Route: <strong>{props.session.route}</strong>
        </span>
      </Show>
      <span style={{ color: "#9ca3af", "font-size": "12px" }}>
        v{props.session.plan_version}
      </span>
      <Show when={props.handoff?.receipt}>
        <span style={{ color: "#6b7280", "font-size": "12px" }}>
          {props.handoff!.receipt!.route}: {props.handoff!.receipt!.downstream_id.slice(0, 12)}...
        </span>
      </Show>
      <Show when={props.session.state === "HANDOFF_FAILED" && props.onRetry}>
        <button
          onClick={props.onRetry}
          style={{ padding: "4px 8px", background: "#f59e0b", color: "white", border: "none", "border-radius": "4px", cursor: "pointer", "font-size": "12px" }}
        >
          Retry
        </button>
      </Show>
    </div>
  );
}
