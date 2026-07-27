import { createSignal, For, Show } from "solid-js";
import type { FollowUpQuestion } from "../api/types";

interface QuestionPanelProps {
  questions: FollowUpQuestion[];
  onAnswer: (answers: Record<string, unknown>) => void;
  loading?: boolean;
}

export default function QuestionPanel(props: QuestionPanelProps) {
  const [answers, setAnswers] = createSignal<Record<string, unknown>>({});

  function updateAnswer(id: string, value: unknown) {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  }

  return (
    <div style={{ padding: "16px", "border-top": "1px solid #e5e7eb", background: "#fafafa" }}>
      <h3 style={{ margin: "0 0 12px 0", "font-size": "14px" }}>Follow-up Questions</h3>
      <For each={props.questions}>
        {(q) => (
          <div style={{ "margin-bottom": "12px" }}>
            <label style={{ display: "block", "font-size": "13px", "font-weight": 500, "margin-bottom": "4px" }}>
              {q.question}
              {q.required && <span style={{ color: "#ef4444" }}> *</span>}
            </label>
            <div style={{ "font-size": "12px", color: "#6b7280", "margin-bottom": "4px" }}>
              {q.why_it_matters}
            </div>
            <Show when={q.answer_type === "text"}>
              <input
                type="text"
                onInput={(e) => updateAnswer(q.id, e.currentTarget.value)}
                style={{ width: "100%", padding: "6px 8px", border: "1px solid #d1d5db", "border-radius": "4px", "font-size": "13px" }}
              />
            </Show>
            <Show when={q.answer_type === "single_select"}>
              <For each={q.options}>
                {(opt) => (
                  <label style={{ display: "block", "font-size": "13px", padding: "2px 0" }}>
                    <input
                      type="radio"
                      name={q.id}
                      value={opt.value}
                      onChange={(e) => updateAnswer(q.id, e.currentTarget.value)}
                    />
                    {" "}{opt.label}
                  </label>
                )}
              </For>
            </Show>
            <Show when={q.answer_type === "multi_select"}>
              <For each={q.options}>
                {(opt) => (
                  <label style={{ display: "block", "font-size": "13px", padding: "2px 0" }}>
                    <input
                      type="checkbox"
                      value={opt.value}
                      onChange={(e) => {
                        const current = (answers()[q.id] as string[]) || [];
                        if (e.currentTarget.checked) {
                          updateAnswer(q.id, [...current, opt.value]);
                        } else {
                          updateAnswer(q.id, current.filter((v) => v !== opt.value));
                        }
                      }}
                    />
                    {" "}{opt.label}
                  </label>
                )}
              </For>
            </Show>
            <Show when={q.answer_type === "number"}>
              <input
                type="number"
                onInput={(e) => updateAnswer(q.id, Number(e.currentTarget.value))}
                style={{ width: "100%", padding: "6px 8px", border: "1px solid #d1d5db", "border-radius": "4px", "font-size": "13px" }}
              />
            </Show>
            <Show when={q.answer_type === "boolean"}>
              <label style={{ "font-size": "13px" }}>
                <input
                  type="checkbox"
                  onChange={(e) => updateAnswer(q.id, e.currentTarget.checked)}
                />
                {" "}Yes
              </label>
            </Show>
          </div>
        )}
      </For>
      <button
        onClick={() => props.onAnswer(answers())}
        disabled={props.loading}
        style={{
          padding: "8px 16px",
          background: "#3b82f6",
          color: "white",
          border: "none",
          "border-radius": "4px",
          cursor: props.loading ? "not-allowed" : "pointer",
          "font-size": "13px",
          opacity: props.loading ? 0.6 : 1,
        }}
      >
        Submit Answers
      </button>
    </div>
  );
}
