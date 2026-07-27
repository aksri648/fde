interface EmptyStateProps {
  onStartNew: () => void;
}

export default function EmptyState(props: EmptyStateProps) {
  return (
    <div style={{ display: "flex", "flex-direction": "column", "align-items": "center", "justify-content": "center", height: "100%", color: "#6b7280" }}>
      <h2 style={{ "font-size": "20px", "margin-bottom": "8px", color: "#374151" }}>FDE Desktop</h2>
      <p style={{ "font-size": "14px", "margin-bottom": "16px" }}>
        Start a planning session to design your architecture
      </p>
      <button
        onClick={props.onStartNew}
        style={{
          padding: "10px 20px",
          background: "#3b82f6",
          color: "white",
          border: "none",
          "border-radius": "6px",
          cursor: "pointer",
          "font-size": "14px",
          "font-weight": 500,
        }}
      >
        Start New Session
      </button>
    </div>
  );
}
