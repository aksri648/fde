import { Show, For, createSignal } from "solid-js";
import type { ProposalResponse } from "../api/types";

interface ProposalReviewProps {
  proposal: ProposalResponse;
  onApprove: () => void;
  onRequestChanges: (feedback: string) => void;
  onCancel: () => void;
  loading?: boolean;
}

export default function ProposalReview(props: ProposalReviewProps) {
  const [feedback, setFeedback] = createSignal("");
  const [showChanges, setShowChanges] = createSignal(false);

  return (
    <div style={{ padding: "16px", background: "#f8fafc", "border-radius": "8px", border: "1px solid #e2e8f0" }}>
      <h3 style={{ margin: "0 0 8px 0", "font-size": "16px" }}>{props.proposal.proposal.title}</h3>
      <p style={{ "font-size": "13px", color: "#475569", margin: "0 0 12px 0" }}>
        {props.proposal.proposal.business_problem}
      </p>

      <div style={{ "margin-bottom": "12px" }}>
        <h4 style={{ margin: "0 0 4px 0", "font-size": "13px" }}>Risks</h4>
        <For each={props.proposal.proposal.risks}>
          {(risk) => <div style={{ "font-size": "12px", color: "#6b7280" }}>• {risk}</div>}
        </For>
      </div>

      <div style={{ "margin-bottom": "12px" }}>
        <h4 style={{ margin: "0 0 4px 0", "font-size": "13px" }}>Assumptions</h4>
        <For each={props.proposal.proposal.assumptions}>
          {(a) => <div style={{ "font-size": "12px", color: "#6b7280" }}>• {a}</div>}
        </For>
      </div>

      <Show when={props.proposal.proposal.delivery_phases.length > 0}>
        <div style={{ "margin-bottom": "12px" }}>
          <h4 style={{ margin: "0 0 4px 0", "font-size": "13px" }}>Delivery Phases</h4>
          <For each={props.proposal.proposal.delivery_phases}>
            {(phase) => (
              <div style={{ "font-size": "12px", color: "#6b7280", padding: "2px 0" }}>
                <strong>{phase.name}</strong>: {phase.description}
              </div>
            )}
          </For>
        </div>
      </Show>

      <Show when={props.proposal.citations.length > 0}>
        <div style={{ "margin-bottom": "12px" }}>
          <h4 style={{ margin: "0 0 4px 0", "font-size": "13px" }}>Documentation</h4>
          <For each={props.proposal.citations}>
            {(c) => (
              <a href={c.url} target="_blank" rel="noopener noreferrer" style={{ "font-size": "12px", color: "#3b82f6", display: "block" }}>
                {c.title}
              </a>
            )}
          </For>
        </div>
      </Show>

      <div style={{ display: "flex", gap: "8px", "margin-top": "12px" }}>
        <button
          onClick={props.onApprove}
          disabled={props.loading}
          style={{ padding: "8px 16px", background: "#22c55e", color: "white", border: "none", "border-radius": "4px", cursor: "pointer", "font-size": "13px" }}
        >
          Approve
        </button>
        <button
          onClick={() => setShowChanges(true)}
          disabled={props.loading}
          style={{ padding: "8px 16px", background: "#f59e0b", color: "white", border: "none", "border-radius": "4px", cursor: "pointer", "font-size": "13px" }}
        >
          Request Changes
        </button>
        <button
          onClick={props.onCancel}
          disabled={props.loading}
          style={{ padding: "8px 16px", background: "#ef4444", color: "white", border: "none", "border-radius": "4px", cursor: "pointer", "font-size": "13px" }}
        >
          Cancel
        </button>
      </div>

      <Show when={showChanges()}>
        <div style={{ "margin-top": "8px" }}>
          <textarea
            value={feedback()}
            onInput={(e) => setFeedback(e.currentTarget.value)}
            placeholder="Describe the changes needed..."
            style={{ width: "100%", padding: "6px 8px", border: "1px solid #d1d5db", "border-radius": "4px", "font-size": "13px", height: "60px" }}
          />
          <button
            onClick={() => props.onRequestChanges(feedback())}
            disabled={props.loading}
            style={{ padding: "6px 12px", background: "#f59e0b", color: "white", border: "none", "border-radius": "4px", cursor: "pointer", "font-size": "12px", "margin-top": "4px" }}
          >
            Submit Changes
          </button>
        </div>
      </Show>
    </div>
  );
}
