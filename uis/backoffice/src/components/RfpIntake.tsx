"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { SESSION_TOKEN_KEY, incidentsApi } from "@/lib/incidents";
import { RfpApiError, rfpsApi, type RfpStatus, type RfpTicket } from "@/lib/rfps";

const STATUS_LABELS: Record<RfpStatus, string> = {
  analyzing: "Analizando",
  discarded: "Descartado",
  intake_complete: "Análisis completo",
};

export default function RfpIntake() {
  const [sessionReady, setSessionReady] = useState(false);
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);
  const [tickets, setTickets] = useState<RfpTicket[]>([]);
  const [selected, setSelected] = useState<RfpTicket | null>(null);
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setToken(window.localStorage.getItem(SESSION_TOKEN_KEY) ?? "");
    setSessionReady(true);
  }, []);

  const expireSession = useCallback(() => {
    window.localStorage.removeItem(SESSION_TOKEN_KEY);
    setToken("");
    setTickets([]);
    setSelected(null);
  }, []);

  const loadTickets = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      setTickets(await rfpsApi.list());
    } catch (error) {
      if (error instanceof RfpApiError && error.status === 401) expireSession();
      else setLoadError("No pudimos cargar los tickets RFP.");
    } finally {
      setLoading(false);
    }
  }, [expireSession]);

  useEffect(() => { if (token) void loadTickets(); }, [loadTickets, token]);

  useEffect(() => {
    if (!selected || selected.status !== "analyzing" || selected.processing_error) return;
    const timer = window.setInterval(async () => {
      try {
        const detail = await rfpsApi.detail(selected.ticket_id);
        setSelected(detail);
        setTickets((current) => current.map((item) => item.ticket_id === detail.ticket_id ? detail : item));
      } catch { /* El siguiente poll puede recuperar una interrupción transitoria. */ }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [selected]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginBusy(true);
    setLoginError("");
    try {
      const result = await incidentsApi.login(email, password);
      window.localStorage.setItem(SESSION_TOKEN_KEY, result.access_token);
      setToken(result.access_token);
      setPassword("");
    } catch {
      setLoginError("No pudimos iniciar sesión. Revisa tus credenciales.");
    } finally {
      setLoginBusy(false);
    }
  }

  if (!sessionReady) return <div className="h-48 animate-pulse rounded-2xl bg-slate-200/70" />;
  if (!token) return (
    <section className="mx-auto max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-widest text-brand-600">Acceso protegido</p>
      <h2 className="mt-1 text-2xl font-extrabold text-slate-900">Recepción de RFPs</h2>
      <p className="mt-2 text-sm text-slate-500">Inicia sesión con tu cuenta interna de Nexova.</p>
      <form onSubmit={login} className="mt-6 space-y-4">
        <label className="block text-sm font-medium text-slate-700">Email<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} className={inputClass} /></label>
        <label className="block text-sm font-medium text-slate-700">Contraseña<input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} className={inputClass} /></label>
        {loginError && <p role="alert" className="text-sm text-rose-700">{loginError}</p>}
        <button disabled={loginBusy} className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{loginBusy ? "Iniciando…" : "Iniciar sesión"}</button>
      </form>
    </section>
  );

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-bold uppercase tracking-widest text-brand-600">Ventas · Marcos Ibáñez</p>
        <h2 className="text-2xl font-extrabold text-slate-900">Recepción y enrutamiento de RFPs</h2>
        <p className="text-sm text-slate-500">Sube un PDF, recibe un ticket inmediatamente y sigue su análisis por departamento.</p>
      </header>
      <UploadPanel onCreated={async (ticketId) => {
        const detail = await rfpsApi.detail(ticketId);
        setSelected(detail);
        await loadTickets();
      }} />
      {loadError && <Retry message={loadError} retry={loadTickets} />}
      <div className="grid gap-6 xl:grid-cols-[340px_1fr]">
        <TicketList tickets={tickets} loading={loading} selectedId={selected?.ticket_id} onSelect={async (id) => setSelected(await rfpsApi.detail(id))} />
        <TicketDetail ticket={selected} />
      </div>
    </div>
  );
}

function UploadPanel({ onCreated }: { onCreated: (ticketId: string) => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) { setError("Selecciona un PDF."); return; }
    if (file.type !== "application/pdf") { setError("El archivo debe ser PDF."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const response = await rfpsApi.upload(file);
      setMessage(`Ticket ${response.ticket_id.slice(0, 8)} creado; análisis en curso.`);
      setFile(null);
      await onCreated(response.ticket_id);
    } catch (requestError) {
      setError(requestError instanceof RfpApiError ? requestError.message : "No pudimos cargar el PDF.");
    } finally { setBusy(false); }
  }
  return <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <h3 className="font-bold text-slate-900">Nueva RFP</h3>
    <form onSubmit={submit} className="mt-3 flex flex-wrap items-end gap-3">
      <label className="min-w-64 flex-1 text-sm font-medium text-slate-700">Documento PDF
        <input key={file?.name ?? "empty"} type="file" accept="application/pdf,.pdf" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white p-2 text-sm" />
      </label>
      <button disabled={busy} className="rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">{busy ? "Creando ticket…" : "Subir y analizar"}</button>
    </form>
    {error && <p role="alert" className="mt-2 text-sm text-rose-700">{error}</p>}
    {message && <p role="status" className="mt-2 text-sm text-emerald-700">{message}</p>}
  </section>;
}

function TicketList({ tickets, loading, selectedId, onSelect }: { tickets: RfpTicket[]; loading: boolean; selectedId?: string; onSelect: (id: string) => Promise<void> }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
    <h3 className="font-bold text-slate-900">Tickets recientes</h3>
    {loading && <div className="mt-3 h-32 animate-pulse rounded-xl bg-slate-100" />}
    {!loading && tickets.length === 0 && <p className="mt-4 text-sm text-slate-500">Todavía no hay RFPs.</p>}
    <ul className="mt-3 space-y-2">{tickets.map((ticket) => <li key={ticket.ticket_id}><button onClick={() => void onSelect(ticket.ticket_id)} className={`w-full rounded-xl border p-3 text-left ${selectedId === ticket.ticket_id ? "border-brand-400 bg-brand-50" : "border-slate-200 hover:bg-slate-50"}`}>
      <span className="block text-xs font-semibold uppercase text-slate-500">{ticket.ticket_id.slice(0, 8)}</span>
      <span className="mt-1 block font-semibold text-slate-900">{ticket.metadata?.client_name ?? "Documento en análisis"}</span>
      <Status status={ticket.status} error={ticket.processing_error} />
    </button></li>)}</ul>
  </section>;
}

function TicketDetail({ ticket }: { ticket: RfpTicket | null }) {
  if (!ticket) return <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">Selecciona un ticket para revisar su análisis.</section>;
  return <section className="space-y-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-mono text-slate-500">{ticket.ticket_id}</p><h3 className="text-xl font-bold text-slate-900">{ticket.metadata?.client_name ?? "Documento recibido"}</h3></div><Status status={ticket.status} error={ticket.processing_error} /></div>
    {ticket.processing_error && <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">El análisis se interrumpió. El PDF y el ticket se conservaron para reintento.</p>}
    {ticket.status === "analyzing" && !ticket.processing_error && <p className="animate-pulse rounded-lg bg-blue-50 p-3 text-sm text-blue-800">Conversión, clasificación y workers en curso…</p>}
    {ticket.classification_reason && <p className="text-sm text-slate-600"><strong>Clasificación:</strong> {ticket.classification_reason}</p>}
    {ticket.metadata && <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Metric label="Sede" value={ticket.metadata.client_hq} /><Metric label="Moneda" value={ticket.metadata.currency} /><Metric label="Fecha límite" value={ticket.metadata.deadline ?? "Por confirmar"} /><Metric label="Palabras" value={String(ticket.metadata.readability.word_count)} />
    </div>}
    {ticket.sales_summary && <div className="rounded-xl bg-slate-50 p-4"><h4 className="text-sm font-bold text-slate-900">Resumen para Ventas</h4><p className="mt-1 text-sm text-slate-600">{ticket.sales_summary}</p></div>}
    {ticket.sections.map((section) => <article key={section.department_id} className="rounded-xl border border-slate-200 p-4">
      <p className="text-xs font-bold uppercase tracking-wide text-brand-600">{section.department_name}</p><h4 className="font-bold text-slate-900">Responsable: {section.contact}</h4>
      <h5 className="mt-3 text-sm font-semibold text-slate-800">Aspectos clave</h5><ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-600">{section.key_aspects.map((item, index) => <li key={index}>{item}</li>)}</ul>
      {section.open_questions.length > 0 && <><h5 className="mt-3 text-sm font-semibold text-amber-800">Preguntas abiertas</h5><ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-amber-800">{section.open_questions.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
    </article>)}
  </section>;
}

function Status({ status, error }: { status: RfpStatus; error: string | null }) { const label = error ? "Error de proceso" : STATUS_LABELS[status]; return <span className={`mt-2 inline-flex rounded-full px-2 py-1 text-xs font-semibold ${error ? "bg-rose-100 text-rose-700" : status === "intake_complete" ? "bg-emerald-100 text-emerald-700" : status === "discarded" ? "bg-slate-200 text-slate-700" : "bg-blue-100 text-blue-700"}`}>{label}</span>; }
function Metric({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-slate-50 p-3"><p className="text-xs font-semibold uppercase text-slate-500">{label}</p><p className="mt-1 font-bold text-slate-900">{value}</p></div>; }
function Retry({ message, retry }: { message: string; retry: () => Promise<void> }) { return <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-800">{message}<button onClick={() => void retry()} className="ml-3 font-bold underline">Reintentar</button></div>; }
const inputClass = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200";
