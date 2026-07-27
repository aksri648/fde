import type {
  SessionSnapshot, FollowUpQuestion, ProposalResponse,
  HandoffStatus, ApprovalAction, WebSocketEvent
} from './types';
import { getSessionToken } from '../auth/clerk';

const API_BASE = () => import.meta.env.VITE_FDE_API_BASE_URL || 'http://localhost:8000';
const WS_BASE = () => import.meta.env.VITE_FDE_WS_BASE_URL || 'ws://localhost:8000';

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getSessionToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ message: res.statusText }));
    throw { status: res.status, ...body };
  }
  return res.json();
}

export const api = {
  async createSession(initialMessage: string, clientRequestId?: string): Promise<SessionSnapshot> {
    const res = await fetch(`${API_BASE()}/v1/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
      body: JSON.stringify({ initial_message: initialMessage, client_request_id: clientRequestId }),
    });
    return handleResponse<SessionSnapshot>(res);
  },

  async getSession(sessionId: string): Promise<SessionSnapshot> {
    const res = await fetch(`${API_BASE()}/v1/sessions/${sessionId}`, { headers: await authHeaders() });
    return handleResponse<SessionSnapshot>(res);
  },

  async listSessions(): Promise<SessionSnapshot[]> {
    const res = await fetch(`${API_BASE()}/v1/sessions`, { headers: await authHeaders() });
    return handleResponse<SessionSnapshot[]>(res);
  },

  async addTurn(sessionId: string, message: string): Promise<SessionSnapshot> {
    const res = await fetch(`${API_BASE()}/v1/sessions/${sessionId}/turns`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
      body: JSON.stringify({ message }),
    });
    return handleResponse<SessionSnapshot>(res);
  },

  async submitAnswers(sessionId: string, answers: Record<string, unknown>): Promise<SessionSnapshot> {
    const res = await fetch(`${API_BASE()}/v1/sessions/${sessionId}/answers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
      body: JSON.stringify({ answers }),
    });
    return handleResponse<SessionSnapshot>(res);
  },

  async getQuestions(sessionId: string): Promise<{ questions: FollowUpQuestion[] }> {
    const res = await fetch(`${API_BASE()}/v1/sessions/${sessionId}/questions`, { headers: await authHeaders() });
    return handleResponse(res);
  },

  async getProposal(sessionId: string): Promise<ProposalResponse> {
    const res = await fetch(`${API_BASE()}/v1/sessions/${sessionId}/proposal`, { headers: await authHeaders() });
    return handleResponse<ProposalResponse>(res);
  },

  async submitApproval(
    sessionId: string, action: ApprovalAction, planVersion: number, feedback?: string
  ): Promise<{ status: string; session_id: string; plan_version?: number }> {
    const res = await fetch(`${API_BASE()}/v1/sessions/${sessionId}/approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
      body: JSON.stringify({ action, plan_version: planVersion, feedback }),
    });
    return handleResponse(res);
  },

  async getHandoff(sessionId: string): Promise<HandoffStatus> {
    const res = await fetch(`${API_BASE()}/v1/sessions/${sessionId}/handoff`, { headers: await authHeaders() });
    return handleResponse<HandoffStatus>(res);
  },

  async retryHandoff(sessionId: string, planVersion: number): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE()}/v1/sessions/${sessionId}/handoff/retry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
      body: JSON.stringify({ plan_version: planVersion }),
    });
    return handleResponse(res);
  },

  async cancelSession(sessionId: string): Promise<SessionSnapshot> {
    const res = await fetch(`${API_BASE()}/v1/sessions/${sessionId}/cancel`, {
      method: 'POST',
      headers: await authHeaders(),
    });
    return handleResponse<SessionSnapshot>(res);
  },

  async connectEvents(sessionId: string, onEvent: (event: WebSocketEvent) => void): Promise<WebSocket> {
    const token = await getSessionToken();
    const ws = new WebSocket(`${WS_BASE()}/v1/sessions/${sessionId}/events?token=${token}`);
    ws.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data));
      } catch { /* ignore malformed */ }
    };
    return ws;
  },
};
