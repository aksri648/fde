import { createSignal, Show } from "solid-js";
import SessionList from "./components/SessionList";
import ConversationSurface from "./components/ConversationSurface";
import InputComposer from "./components/InputComposer";
import QuestionPanel from "./components/QuestionPanel";
import ProposalReview from "./components/ProposalReview";
import SessionStatus from "./components/SessionStatus";
import ConnectionIndicator from "./components/ConnectionIndicator";
import EmptyState from "./components/EmptyState";
import NewSessionDialog from "./components/NewSessionDialog";
import { sessionStore } from "./stores/session";
import type { SessionSnapshot } from "./api/types";

const [sessions, setSessions] = createSignal<SessionSnapshot[]>([]);
const [selectedId, setSelectedId] = createSignal<string | null>(null);
const [showNewDialog, setShowNewDialog] = createSignal(false);

function selectSession(id: string) {
  setSelectedId(id);
  sessionStore.connectWs(id);
  sessionStore.refresh(id);
}

async function handleNewSession(message: string) {
  setShowNewDialog(false);
  await sessionStore.createSession(message);
  const s = sessionStore.state();
  if (s.session) {
    setSessions((prev) => [s.session!, ...prev]);
    setSelectedId(s.session.id);
  }
}

export default function App() {
  return (
    <div style={{ display: "flex", height: "100vh", "font-family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif", overflow: "hidden" }}>
      <SessionList
        sessions={sessions()}
        selectedId={selectedId()}
        onSelect={selectSession}
        onNew={() => setShowNewDialog(true)}
      />
      <div style={{ flex: 1, display: "flex", "flex-direction": "column", overflow: "hidden" }}>
        <div style={{ padding: "8px 16px", "border-bottom": "1px solid #e5e7eb", display: "flex", "justify-content": "space-between", "align-items": "center" }}>
          <h1 style={{ margin: 0, "font-size": "16px", "font-weight": 600 }}>FDE Desktop</h1>
          <ConnectionIndicator connected={sessionStore.state().connected} />
        </div>
        <Show when={selectedId()} fallback={<EmptyState onStartNew={() => setShowNewDialog(true)} />}>
          <Show when={sessionStore.state().session}>
            <SessionStatus
              session={sessionStore.state().session!}
              handoff={sessionStore.state().handoff || undefined}
              onRetry={() => sessionStore.retryHandoff()}
            />
            <ConversationSurface
              messages={sessionStore.state().messages}
              isStreaming={sessionStore.state().loading}
            />
            <Show when={sessionStore.state().questions.length > 0}>
              <QuestionPanel
                questions={sessionStore.state().questions}
                onAnswer={(a) => sessionStore.submitAnswers(a)}
                loading={sessionStore.state().loading}
              />
            </Show>
            <Show when={sessionStore.state().proposal}>
              <ProposalReview
                proposal={sessionStore.state().proposal!}
                onApprove={() => sessionStore.approve()}
                onRequestChanges={(f) => sessionStore.requestChanges(f)}
                onCancel={() => sessionStore.cancel()}
                loading={sessionStore.state().loading}
              />
            </Show>
            <Show when={["DISCOVERING", "AWAITING_ANSWERS"].includes(sessionStore.state().session?.state || "") && !sessionStore.state().proposal}>
              <InputComposer
                onSubmit={(m) => sessionStore.addTurn(m)}
                disabled={sessionStore.state().loading}
              />
            </Show>
          </Show>
        </Show>
        <Show when={sessionStore.state().error}>
          <div style={{ padding: "8px 16px", background: "#fee2e2", color: "#991b1b", "font-size": "13px" }}>
            {sessionStore.state().error}
          </div>
        </Show>
      </div>
      <Show when={showNewDialog()}>
        <NewSessionDialog
          open={showNewDialog()}
          onClose={() => setShowNewDialog(false)}
          onSubmit={handleNewSession}
        />
      </Show>
    </div>
  );
}
