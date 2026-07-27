import { createSignal, onCleanup } from "solid-js";
import type { WebSocketEvent } from "../api/types";

export function createReconnectWs(
  sessionId: string,
  token: string,
  onEvent: (event: WebSocketEvent) => void,
  onStateChange: (connected: boolean) => void
) {
  let ws: WebSocket | null = null;
  let retryCount = 0;
  let maxRetry = 10;

  function connect() {
    const baseWs = import.meta.env.VITE_FDE_WS_BASE_URL || "ws://localhost:8000";
    ws = new WebSocket(`${baseWs}/v1/sessions/${sessionId}/events?token=${token}`);

    ws.onopen = () => {
      retryCount = 0;
      onStateChange(true);
    };

    ws.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data));
      } catch { /* ignore */ }
    };

    ws.onclose = () => {
      onStateChange(false);
      if (retryCount < maxRetry) {
        const delay = Math.min(1000 * Math.pow(2, retryCount), 30000) + Math.random() * 1000;
        retryCount++;
        setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      onStateChange(false);
    };
  }

  connect();

  onCleanup(() => {
    if (ws) ws.close();
  });

  return { close: () => ws?.close() };
}
