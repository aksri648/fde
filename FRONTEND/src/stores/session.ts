import { createSignal, batch } from "solid-js";
import type { SessionSnapshot, FollowUpQuestion, ProposalResponse, HandoffStatus, WebSocketEvent } from "../api/types";
import { api } from "../api/client";

export interface SessionState {
  session: SessionSnapshot | null;
  questions: FollowUpQuestion[];
  proposal: ProposalResponse | null;
  handoff: HandoffStatus | null;
  messages: Array<{ role: string; content: string; timestamp?: string }>;
  connected: boolean;
  loading: boolean;
  error: string | null;
}

const [state, setState] = createSignal<SessionState>({
  session: null,
  questions: [],
  proposal: null,
  handoff: null,
  messages: [],
  connected: false,
  loading: false,
  error: null,
});

let ws: WebSocket | null = null;
let shouldReconnect = false;

function addMessage(role: string, content: string) {
  setState((s) => ({
    ...s,
    messages: [...s.messages, { role, content, timestamp: new Date().toISOString() }],
  }));
}

export const sessionStore = {
  state,
  async createSession(message: string) {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const session = await api.createSession(message);
      addMessage("user", message);
      setState((s) => ({ ...s, session, loading: false }));
      this.connectWs(session.id);
      await this.refresh(session.id);
    } catch (e: any) {
      setState((s) => ({ ...s, loading: false, error: e.message || "Failed to create session" }));
    }
  },
  async refresh(sessionId: string) {
    try {
      const session = await api.getSession(sessionId);
      batch(() => {
        setState((s) => ({ ...s, session }));
      });
      if (session.state === "AWAITING_ANSWERS") {
        const { questions } = await api.getQuestions(sessionId);
        setState((s) => ({ ...s, questions }));
      }
      if (session.state === "AWAITING_APPROVAL") {
        const proposal = await api.getProposal(sessionId);
        setState((s) => ({ ...s, proposal }));
      }
      if (["HANDOFF_QUEUED", "HANDOFF_FAILED", "HANDED_OFF"].includes(session.state)) {
        const handoff = await api.getHandoff(sessionId);
        setState((s) => ({ ...s, handoff }));
      }
    } catch (e: any) {
      setState((s) => ({ ...s, error: e.message }));
    }
  },
  async addTurn(message: string) {
    const sid = state().session?.id;
    if (!sid) return;
    addMessage("user", message);
    setState((s) => ({ ...s, loading: true }));
    try {
      const session = await api.addTurn(sid, message);
      setState((s) => ({ ...s, session, loading: false }));
      await this.refresh(sid);
    } catch (e: any) {
      setState((s) => ({ ...s, loading: false, error: e.message }));
    }
  },
  async submitAnswers(answers: Record<string, unknown>) {
    const sid = state().session?.id;
    if (!sid) return;
    setState((s) => ({ ...s, loading: true }));
    try {
      const session = await api.submitAnswers(sid, answers);
      setState((s) => ({ ...s, session, loading: false, questions: [] }));
      await this.refresh(sid);
    } catch (e: any) {
      setState((s) => ({ ...s, loading: false, error: e.message }));
    }
  },
  async approve() {
    const sid = state().session?.id;
    const pv = state().session?.plan_version;
    if (!sid || !pv) return;
    setState((s) => ({ ...s, loading: true }));
    try {
      await api.submitApproval(sid, "approve", pv);
      setState((s) => ({ ...s, loading: false, proposal: null }));
      await this.refresh(sid);
    } catch (e: any) {
      setState((s) => ({ ...s, loading: false, error: e.message }));
    }
  },
  async requestChanges(feedback: string) {
    const sid = state().session?.id;
    const pv = state().session?.plan_version;
    if (!sid || !pv) return;
    setState((s) => ({ ...s, loading: true }));
    try {
      await api.submitApproval(sid, "request_changes", pv, feedback);
      setState((s) => ({ ...s, loading: false, proposal: null }));
      await this.refresh(sid);
    } catch (e: any) {
      setState((s) => ({ ...s, loading: false, error: e.message }));
    }
  },
  async cancel() {
    const sid = state().session?.id;
    if (!sid) return;
    setState((s) => ({ ...s, loading: true }));
    try {
      const session = await api.cancelSession(sid);
      setState((s) => ({ ...s, session, loading: false }));
    } catch (e: any) {
      setState((s) => ({ ...s, loading: false, error: e.message }));
    }
  },
  async retryHandoff() {
    const sid = state().session?.id;
    const pv = state().session?.plan_version;
    if (!sid || !pv) return;
    setState((s) => ({ ...s, loading: true }));
    try {
      await api.retryHandoff(sid, pv);
      setState((s) => ({ ...s, loading: false }));
      await this.refresh(sid);
    } catch (e: any) {
      setState((s) => ({ ...s, loading: false, error: e.message }));
    }
  },
  async connectWs(sessionId: string) {
    if (ws) ws.close();
    shouldReconnect = true;
    ws = await api.connectEvents(sessionId, (event: WebSocketEvent) => {
      if (event.event === "assistant_message" || event.event === "proposal_ready" || event.event === "questions_ready" || event.event === "handoff_queued" || event.event === "handoff_completed" || event.event === "state_changed") {
        this.refresh(sessionId);
      }
    });
    ws.onopen = () => setState((s) => ({ ...s, connected: true }));
    ws.onclose = () => {
      setState((s) => ({ ...s, connected: false }));
      if (shouldReconnect) {
        setTimeout(() => {
          if (shouldReconnect) this.connectWs(sessionId);
        }, 3000);
      }
    };
    ws.onerror = () => setState((s) => ({ ...s, connected: false }));
  },
  disconnect() {
    shouldReconnect = false;
    if (ws) { ws.close(); ws = null; }
    setState((s) => ({
      ...s,
      session: null,
      questions: [],
      proposal: null,
      handoff: null,
      messages: [],
      connected: false,
    }));
  },
};
