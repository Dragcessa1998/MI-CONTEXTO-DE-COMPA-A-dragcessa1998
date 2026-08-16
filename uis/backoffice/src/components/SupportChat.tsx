"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { SESSION_TOKEN_KEY, incidentsApi } from "@/lib/incidents";
import { connectSupportChat, type ChatConnectionState, type ChatEvent, type ChatMessage, type ChatSessionSnapshot } from "@/lib/support-chat";


const SESSION_KEY = "nexova:support-chat-session";
const CLIENT_KEY = "nexova:support-chat-client";

function persistentId(key: string, prefix: string): string {
  const current = window.localStorage.getItem(key);
  if (current) return current;
  const created = `${prefix}_${crypto.randomUUID().replaceAll("-", "")}`;
  window.localStorage.setItem(key, created);
  return created;
}

export default function SupportChat() {
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [connection, setConnection] = useState<ChatConnectionState>({ status: "connecting" });
  const connectionRef = useRef<ReturnType<typeof connectSupportChat> | null>(null);
  const sessionIdRef = useRef("");

  useEffect(() => {
    setToken(window.localStorage.getItem(SESSION_TOKEN_KEY) ?? "");
    setReady(true);
  }, []);

  useEffect(() => {
    if (!token) return;
    const sessionId = persistentId(SESSION_KEY, "chat");
    const clientId = persistentId(CLIENT_KEY, "client");
    sessionIdRef.current = sessionId;
    const connectionHandle = connectSupportChat({
      sessionId,
      clientId,
      token,
      onState: setConnection,
      onUnauthorized: () => {
        window.localStorage.removeItem(SESSION_TOKEN_KEY);
        setToken("");
      },
      onEvent: applyEvent,
    });
    connectionRef.current = connectionHandle;
    return () => {
      connectionHandle.close();
      connectionRef.current = null;
    };
  }, [token]);

  function applyEvent(event: ChatEvent): void {
    if (event.event === "session_snapshot") {
      setMessages((event.data as unknown as ChatSessionSnapshot).messages);
      return;
    }
    if (event.event === "user_message") {
      const messageId = String(event.data.message_id);
      setMessages((current) => current.some((message) => message.message_id === messageId) ? current : [...current, {
        message_id: messageId,
        role: "user",
        content: String(event.data.text),
        status: "completed",
        created_at: new Date().toISOString(),
      }]);
      return;
    }
    if (event.event === "token_chunk") {
      const messageId = String(event.data.message_id);
      const tokenChunk = String(event.data.token);
      setMessages((current) => {
        const exists = current.some((message) => message.message_id === messageId);
        if (!exists) return [...current, {
          message_id: messageId,
          role: "assistant",
          content: tokenChunk,
          status: "streaming",
          created_at: new Date().toISOString(),
        }];
        return current.map((message) => message.message_id === messageId
          ? { ...message, content: message.content + tokenChunk, status: "streaming" }
          : message);
      });
      return;
    }
    if (event.event === "generation_completed" || event.event === "generation_interrupted" || event.event === "generation_failed") {
      const messageId = String(event.data.message_id);
      const status = event.event === "generation_completed" ? "completed" : event.event === "generation_interrupted" ? "interrupted" : "failed";
      setMessages((current) => current.map((message) => message.message_id === messageId ? { ...message, status } : message));
      if (event.event === "generation_failed") setError(String(event.data.detail));
      return;
    }
    if (event.event === "error") setError(String(event.data.detail ?? "No pudimos procesar el mensaje."));
  }

  async function login(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setLoginError("");
    try {
      const result = await incidentsApi.login(email, password);
      window.localStorage.setItem(SESSION_TOKEN_KEY, result.access_token);
      setToken(result.access_token);
      setPassword("");
    } catch {
      setLoginError("No pudimos iniciar sesión. Revisa tus credenciales.");
    }
  }

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const normalized = input.trim();
    if (!normalized || connection.status !== "connected") return;
    const streaming = messages.some((message) => message.role === "assistant" && message.status === "streaming");
    const sent = connectionRef.current?.send({
      event: streaming ? "interrupt_requested" : "user_message",
      data: streaming
        ? { session_id: sessionIdRef.current, new_input: normalized }
        : { session_id: sessionIdRef.current, text: normalized },
    });
    if (sent) {
      setInput("");
      setError("");
    }
  }

  if (!ready) return <div className="h-48 animate-pulse rounded-2xl bg-slate-200/70" />;
  if (!token) return <section className="mx-auto max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
    <p className="text-xs font-bold uppercase tracking-widest text-brand-600">Canal protegido</p>
    <h2 className="mt-1 text-2xl font-extrabold text-slate-900">Soporte en tiempo real</h2>
    <form onSubmit={(event) => void login(event)} className="mt-6 space-y-4">
      <label className="block text-sm font-medium text-slate-700">Email<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} className={inputClass} /></label>
      <label className="block text-sm font-medium text-slate-700">Contraseña<input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} className={inputClass} /></label>
      {loginError && <p role="alert" className="text-sm text-rose-700">{loginError}</p>}
      <button className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white">Iniciar sesión</button>
    </form>
  </section>;

  const streaming = messages.some((message) => message.role === "assistant" && message.status === "streaming");
  const stateLabel = connection.status === "connected" ? "Conectado"
    : connection.status === "reconnecting" ? `Reconectando en ${Math.ceil(connection.retryInMs / 1000)} s`
      : connection.status === "closed" ? "Cerrado" : "Conectando";

  return <section className="mx-auto flex max-w-4xl flex-col gap-5">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-xs font-bold uppercase tracking-widest text-brand-600">Customer Support · Roberto Díaz</p><h2 className="text-3xl font-black text-slate-950">Agente de soporte de primera línea</h2><p className="mt-1 text-sm text-slate-600">Las respuestas llegan token a token. Puedes redirigirlas sin esperar a que terminen.</p></div>
      <span className={`rounded-full px-3 py-1 text-xs font-bold ${connection.status === "connected" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>{stateLabel}</span>
    </header>
    <div aria-live="polite" className="min-h-[420px] space-y-3 rounded-2xl border border-slate-200 bg-slate-50 p-5 shadow-inner">
      {messages.length === 0 && <p className="py-24 text-center text-sm text-slate-500">Escribe una consulta sobre servicios, SLA o un ticket de soporte.</p>}
      {messages.map((message) => <article key={message.message_id} className={`max-w-[85%] rounded-2xl px-4 py-3 ${message.role === "user" ? "ml-auto bg-brand-600 text-white" : "bg-white text-slate-800 shadow-sm"}`}>
        <p className="whitespace-pre-wrap leading-7">{message.content || "…"}</p>
        {message.status === "streaming" && <span className="mt-2 inline-block h-4 w-1 animate-pulse bg-brand-500" aria-label="Generando respuesta" />}
        {message.status === "interrupted" && <p className="mt-2 text-xs font-bold uppercase tracking-wide text-amber-700">Respuesta interrumpida</p>}
        {message.status === "failed" && <p className="mt-2 text-xs font-bold uppercase tracking-wide text-rose-700">Generación fallida</p>}
      </article>)}
    </div>
    {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <label htmlFor="support-message" className="text-sm font-bold text-slate-800">{streaming ? "Redirigir la respuesta actual" : "Mensaje"}</label>
      <div className="mt-2 flex gap-2"><textarea id="support-message" value={input} onChange={(event) => setInput(event.target.value)} maxLength={500} rows={2} disabled={connection.status !== "connected"} className="min-w-0 flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 disabled:bg-slate-100" /><button disabled={!input.trim() || connection.status !== "connected"} className={`self-stretch rounded-xl px-5 text-sm font-bold text-white disabled:opacity-50 ${streaming ? "bg-amber-600" : "bg-brand-600"}`}>{streaming ? "Interrumpir y enviar" : "Enviar"}</button></div>
    </form>
  </section>;
}

const inputClass = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200";
