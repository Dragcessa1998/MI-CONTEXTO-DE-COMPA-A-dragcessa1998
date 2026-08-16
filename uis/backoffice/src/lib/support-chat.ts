export type ChatMessageStatus = "streaming" | "completed" | "interrupted" | "failed";

export interface ChatMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  status: ChatMessageStatus;
  created_at: string;
}

export interface ChatSessionSnapshot {
  session_id: string;
  agent_id: "first_line_support";
  user_id: number;
  client_id: string;
  status: "active" | "interrupted" | "closed";
  created_at: string;
  messages: ChatMessage[];
}

export type ChatConnectionState =
  | { status: "connecting" | "connected" | "closed" }
  | { status: "reconnecting"; retryInMs: number };

export interface ChatEvent {
  event: string;
  data: Record<string, unknown>;
}

interface ConnectOptions {
  sessionId: string;
  clientId: string;
  token: string;
  onEvent: (event: ChatEvent) => void;
  onState: (state: ChatConnectionState) => void;
  onUnauthorized: () => void;
}

function websocketBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_PLATFORM_WS_URL;
  if (configured) return configured.replace(/\/$/, "");
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.hostname}:8000`;
}

export function connectSupportChat(options: ConnectOptions): {
  send: (event: ChatEvent) => boolean;
  close: () => void;
} {
  let socket: WebSocket | null = null;
  let stopped = false;
  let retryAttempt = 0;
  let reconnectTimer: number | null = null;

  function open(): void {
    if (stopped) return;
    options.onState({ status: "connecting" });
    const query = new URLSearchParams({ token: options.token, client_id: options.clientId });
    socket = new WebSocket(`${websocketBaseUrl()}/agent/ws/${encodeURIComponent(options.sessionId)}?${query}`);
    socket.onopen = () => {
      options.onState({ status: "connected" });
    };
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(String(message.data)) as ChatEvent;
        retryAttempt = 0;
        options.onEvent(event);
      } catch {
        options.onEvent({ event: "error", data: { detail: "El servidor envió un evento no válido" } });
      }
    };
    socket.onclose = (event) => {
      socket = null;
      if (stopped) {
        options.onState({ status: "closed" });
        return;
      }
      if (event.code === 4401 || event.code === 4403) {
        options.onUnauthorized();
        return;
      }
      retryAttempt += 1;
      const retryInMs = Math.min(30_000, 1_000 * 2 ** (retryAttempt - 1));
      options.onState({ status: "reconnecting", retryInMs });
      reconnectTimer = window.setTimeout(open, retryInMs);
    };
  }

  open();
  return {
    send(event) {
      if (socket?.readyState !== WebSocket.OPEN) return false;
      socket.send(JSON.stringify(event));
      return true;
    },
    close() {
      stopped = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close(1000, "component unmounted");
      socket = null;
    },
  };
}
