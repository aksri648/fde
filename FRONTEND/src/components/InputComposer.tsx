import { createSignal } from "solid-js";

interface InputComposerProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

export default function InputComposer(props: InputComposerProps) {
  const [text, setText] = createSignal("");

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const t = text().trim();
    if (t && !props.disabled) {
      props.onSubmit(t);
      setText("");
    }
  }

  return (
    <div style={{ padding: "12px 16px", "border-top": "1px solid #e5e7eb", display: "flex", gap: "8px" }}>
      <textarea
        value={text()}
        onInput={(e) => setText(e.currentTarget.value)}
        onKeyDown={handleKeyDown}
        placeholder="Describe what you want to build..."
        disabled={props.disabled}
        rows={2}
        style={{
          flex: 1,
          padding: "8px",
          border: "1px solid #d1d5db",
          "border-radius": "6px",
          "font-size": "14px",
          resize: "none",
          "font-family": "inherit",
          opacity: props.disabled ? 0.5 : 1,
        }}
      />
      <button
        onClick={submit}
        disabled={props.disabled || !text().trim()}
        style={{
          padding: "8px 16px",
          background: "#3b82f6",
          color: "white",
          border: "none",
          "border-radius": "6px",
          cursor: props.disabled ? "not-allowed" : "pointer",
          "align-self": "flex-end",
          "font-size": "14px",
          opacity: props.disabled || !text().trim() ? 0.5 : 1,
        }}
      >
        Send
      </button>
    </div>
  );
}
