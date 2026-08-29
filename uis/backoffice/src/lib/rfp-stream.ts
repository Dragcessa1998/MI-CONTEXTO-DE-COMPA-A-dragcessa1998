import type { RfpStatus } from "@/lib/rfps";

const API_URL = process.env.NEXT_PUBLIC_PLATFORM_API_URL ?? "/platform-api";

export interface RfpTicketCreatedEvent {
  eventId: string;
  ticket_id: string;
  rfp_id: string;
  status: Extract<RfpStatus, "analyzing">;
  created_at: string;
}

export type RfpStreamState =
  | { status: "connecting" | "connected" }
  | { status: "reconnecting"; retryInMs: number };

interface RfpStreamOptions {
  token: string;
  signal: AbortSignal;
  onEvent: (event: RfpTicketCreatedEvent) => void;
  onRecovery: () => Promise<void>;
  onState: (state: RfpStreamState) => void;
  onUnauthorized: () => void;
}

interface ParsedSseEvent {
  id: string;
  event: string;
  data: string;
}

function parseBlock(block: string): ParsedSseEvent | null {
  if (!block.trim() || block.trimStart().startsWith(":")) return null;
  const parsed: ParsedSseEvent = { id: "", event: "", data: "" };
  for (const line of block.split("\n")) {
    if (line.startsWith("id:")) parsed.id = line.slice(3).trim();
    if (line.startsWith("event:")) parsed.event = line.slice(6).trim();
    if (line.startsWith("data:")) parsed.data += line.slice(5).trim();
  }
  return parsed.event && parsed.data ? parsed : null;
}

function abortableDelay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = window.setTimeout(resolve, milliseconds);
    signal.addEventListener("abort", () => {
      window.clearTimeout(timer);
      resolve();
    }, { once: true });
  });
}

export function connectRfpStream(options: RfpStreamOptions): () => void {
  let lastEventId = "";
  let retryAttempt = 0;
  let hasConnected = false;

  async function run(): Promise<void> {
    options.onState({ status: "connecting" });
    while (!options.signal.aborted) {
      try {
        const response = await fetch(`${API_URL}/api/rfps/events`, {
          cache: "no-store",
          headers: {
            Accept: "text/event-stream",
            Authorization: `Bearer ${options.token}`,
            ...(lastEventId ? { "Last-Event-ID": lastEventId } : {}),
          },
          signal: options.signal,
        });
        if (response.status === 401) {
          options.onUnauthorized();
          return;
        }
        if (!response.ok || !response.body) throw new Error("SSE unavailable");
        if (hasConnected) await options.onRecovery();
        hasConnected = true;
        options.onState({ status: "connected" });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!options.signal.aborted) {
          const { value, done } = await reader.read();
          if (done) throw new Error("SSE closed");
          buffer += decoder.decode(value, { stream: true }).replaceAll("\r\n", "\n");
          let boundary = buffer.indexOf("\n\n");
          while (boundary >= 0) {
            const block = parseBlock(buffer.slice(0, boundary));
            buffer = buffer.slice(boundary + 2);
            boundary = buffer.indexOf("\n\n");
            if (!block || block.event !== "rfp_ticket_created") continue;
            const payload = JSON.parse(block.data) as Omit<RfpTicketCreatedEvent, "eventId">;
            lastEventId = block.id;
            retryAttempt = 0;
            options.onEvent({ ...payload, eventId: block.id });
          }
        }
      } catch {
        if (options.signal.aborted) return;
        retryAttempt += 1;
        const retryInMs = Math.min(30_000, 1_000 * 2 ** (retryAttempt - 1));
        options.onState({ status: "reconnecting", retryInMs });
        await abortableDelay(retryInMs, options.signal);
      }
    }
  }

  void run();
  return () => undefined;
}
