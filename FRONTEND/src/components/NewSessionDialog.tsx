import { createSignal } from "solid-js";

interface NewSessionDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (message: string) => void;
}

export default function NewSessionDialog(props: NewSessionDialogProps) {
  const [message, setMessage] = createSignal("");

  return (
    <div style={{
      position: "fixed",
      top: 0, left: 0, right: 0, bottom: 0,
      background: "rgba(0,0,0,0.5)",
      display: "flex",
      "align-items": "center",
      "justify-content": "center",
      "z-index": 100,
    }}>
      <div style={{
        background: "white",
        "border-radius": "8px",
        padding: "24px",
        width: "500px",
        "max-width": "90vw",
        "box-shadow": "0 4px 24px rgba(0,0,0,0.15)",
      }}>
        <h3 style={{ margin: "0 0 12px 0", "font-size": "16px" }}>New Planning Session</h3>
        <textarea
          value={message()}
          onInput={(e) => setMessage(e.currentTarget.value)}
          placeholder="Describe what you want to build..."
          style={{
            width: "100%",
            height: "120px",
            padding: "8px",
            border: "1px solid #d1d5db",
            "border-radius": "4px",
            "font-size": "14px",
            resize: "vertical",
            "font-family": "inherit",
          }}
        />
        <div style={{ display: "flex", gap: "8px", "margin-top": "12px", "justify-content": "flex-end" }}>
          <button
            onClick={props.onClose}
            style={{
              padding: "8px 16px",
              border: "1px solid #d1d5db",
              "border-radius": "4px",
              background: "white",
              cursor: "pointer",
              "font-size": "13px",
            }}
          >
            Cancel
          </button>
          <button
            onClick={() => {
              if (message().trim()) {
                props.onSubmit(message().trim());
                setMessage("");
              }
            }}
            disabled={!message().trim()}
            style={{
              padding: "8px 16px",
              background: "#3b82f6",
              color: "white",
              border: "none",
              "border-radius": "4px",
              cursor: message().trim() ? "pointer" : "not-allowed",
              opacity: message().trim() ? 1 : 0.5,
              "font-size": "13px",
            }}
          >
            Start Session
          </button>
        </div>
      </div>
    </div>
  );
}
