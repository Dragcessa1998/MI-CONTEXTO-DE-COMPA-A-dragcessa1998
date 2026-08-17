"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  BRANCH_LABELS,
  CATEGORY_LABELS,
  INCIDENT_BRANCHES,
  INCIDENT_CATEGORIES,
  INCIDENT_ORIGINS,
  INCIDENT_STATUSES,
  IncidentApiError,
  NEXT_STATUSES,
  ORIGIN_LABELS,
  SESSION_TOKEN_KEY,
  STATUS_LABELS,
  incidentsApi,
  type Incident,
  type IncidentBranch,
  type IncidentCategory,
  type IncidentFilters,
  type IncidentInput,
  type IncidentOrigin,
  type IncidentStatus,
  type IncidentSummary,
} from "@/lib/incidents";

type LoadState = "idle" | "loading" | "ready" | "error";

const EMPTY_FORM: IncidentInput = {
  title: "",
  description: "",
  category: "technical_failure",
  status: "open",
  origin: "internal",
  branch: "central",
};

export default function IncidentManager() {
  const [sessionReady, setSessionReady] = useState(false);
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [filters, setFilters] = useState<IncidentFilters>({});
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [listState, setListState] = useState<LoadState>("idle");
  const [listError, setListError] = useState("");
  const [summary, setSummary] = useState<IncidentSummary | null>(null);
  const [summaryState, setSummaryState] = useState<LoadState>("idle");
  const [summaryError, setSummaryError] = useState("");

  useEffect(() => {
    setToken(window.localStorage.getItem(SESSION_TOKEN_KEY) ?? "");
    setSessionReady(true);
  }, []);

  const expireSession = useCallback(() => {
    window.localStorage.removeItem(SESSION_TOKEN_KEY);
    setToken("");
    setLoginError("Tu sesión ha expirado. Inicia sesión de nuevo.");
  }, []);

  const loadIncidents = useCallback(async () => {
    setListState("loading");
    setListError("");
    try {
      setIncidents(await incidentsApi.list(filters));
      setListState("ready");
    } catch (error) {
      if (error instanceof IncidentApiError && error.status === 401) {
        expireSession();
        return;
      }
      setListError("No pudimos cargar los incidentes.");
      setListState("error");
    }
  }, [expireSession, filters]);

  const loadSummary = useCallback(async () => {
    setSummaryState("loading");
    setSummaryError("");
    try {
      setSummary(await incidentsApi.summary());
      setSummaryState("ready");
    } catch (error) {
      if (error instanceof IncidentApiError && error.status === 401) {
        expireSession();
        return;
      }
      setSummaryError("Las métricas no están disponibles en este momento.");
      setSummaryState("error");
    }
  }, [expireSession]);

  useEffect(() => {
    if (!token) return;
    void loadIncidents();
  }, [loadIncidents, token]);

  useEffect(() => {
    if (!token) return;
    void loadSummary();
  }, [loadSummary, token]);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginBusy(true);
    setLoginError("");
    try {
      const result = await incidentsApi.login(email, password);
      window.localStorage.setItem(SESSION_TOKEN_KEY, result.access_token);
      setToken(result.access_token);
      setPassword("");
    } catch {
      setLoginError("No pudimos iniciar sesión. Revisa el email y la contraseña.");
    } finally {
      setLoginBusy(false);
    }
  }

  function signOut() {
    window.localStorage.removeItem(SESSION_TOKEN_KEY);
    setToken("");
    setIncidents([]);
    setSummary(null);
  }

  if (!sessionReady) {
    return <div className="h-48 animate-pulse rounded-2xl bg-slate-200/70" />;
  }

  if (!token) {
    return (
      <section className="mx-auto max-w-lg rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-widest text-brand-600">Acceso protegido</p>
        <h2 className="mt-1 text-2xl font-extrabold text-slate-900">Gestor de incidentes</h2>
        <p className="mt-2 text-sm text-slate-500">
          Inicia sesión con una cuenta de Nexova para consultar o registrar información operativa.
        </p>
        <form onSubmit={submitLogin} className="mt-6 space-y-4">
          <Field label="Email">
            <input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Contraseña">
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={inputClass}
            />
          </Field>
          {loginError && <p role="alert" className="text-sm text-rose-700">{loginError}</p>}
          <button
            type="submit"
            disabled={loginBusy}
            className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-wait disabled:opacity-60"
          >
            {loginBusy ? "Iniciando sesión…" : "Iniciar sesión"}
          </button>
        </form>
      </section>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-brand-600">Operaciones · Nexova</p>
          <h2 className="text-2xl font-extrabold text-slate-900">Gestor centralizado de incidentes</h2>
          <p className="text-sm text-slate-500">Registro, ciclo de vida y métricas en tiempo real.</p>
        </div>
        <button onClick={signOut} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          Cerrar sesión
        </button>
      </header>

      <IncidentSummaryPanel
        summary={summary}
        state={summaryState}
        error={summaryError}
        onRetry={loadSummary}
      />

      <IncidentForm
        onCreated={async () => {
          await Promise.all([loadIncidents(), loadSummary()]);
        }}
        onUnauthorized={expireSession}
      />

      <IncidentList
        incidents={incidents}
        filters={filters}
        setFilters={setFilters}
        state={listState}
        error={listError}
        onRetry={loadIncidents}
        onReplace={(updated) => setIncidents((current) => current.map((item) => item.id === updated.id ? updated : item))}
        onOptimisticStatus={(id, status) => setIncidents((current) => current.map((item) => item.id === id ? { ...item, status } : item))}
        onSummaryChanged={loadSummary}
        onUnauthorized={expireSession}
      />
    </div>
  );
}

function IncidentForm({
  onCreated,
  onUnauthorized,
}: {
  onCreated: () => Promise<void>;
  onUnauthorized: () => void;
}) {
  const [form, setForm] = useState<IncidentInput>(EMPTY_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState("");
  const [generalError, setGeneralError] = useState("");

  function setField<K extends keyof IncidentInput>(field: K, value: IncidentInput[K]) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: "" }));
    setSuccess("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clientErrors: Record<string, string> = {};
    if (!form.title.trim()) clientErrors.title = "Escribe un título breve.";
    if (form.description.trim().length < 5) clientErrors.description = "Añade una descripción de al menos 5 caracteres.";
    if (!form.category) clientErrors.category = "Selecciona una categoría.";
    if (!form.origin) clientErrors.origin = "Selecciona el origen.";
    if (!form.branch) clientErrors.branch = "Selecciona la sede responsable.";
    if (Object.keys(clientErrors).length) {
      setErrors(clientErrors);
      return;
    }

    setBusy(true);
    setErrors({});
    setGeneralError("");
    try {
      await incidentsApi.create({ ...form, title: form.title.trim(), description: form.description.trim() });
      setForm(EMPTY_FORM);
      setSuccess("Incidente registrado correctamente.");
      await onCreated();
    } catch (error) {
      if (error instanceof IncidentApiError && error.status === 401) {
        onUnauthorized();
        return;
      }
      if (error instanceof IncidentApiError) setErrors(error.fields);
      setGeneralError("No pudimos registrar el incidente. Revisa los campos indicados.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-bold text-slate-900">Registrar incidente</h3>
      <p className="text-sm text-slate-500">Los campos marcados son obligatorios. Las fechas las genera el sistema.</p>
      <form onSubmit={submit} className="mt-5 grid gap-4 md:grid-cols-2">
        <Field label="Título *" error={errors.title}>
          <input value={form.title} onChange={(event) => setField("title", event.target.value)} className={inputClass} />
        </Field>
        <Field label="Categoría *" error={errors.category}>
          <select value={form.category} onChange={(event) => setField("category", event.target.value as IncidentCategory)} className={inputClass}>
            {INCIDENT_CATEGORIES.map((value) => <option key={value} value={value}>{CATEGORY_LABELS[value]}</option>)}
          </select>
        </Field>
        <div className="md:col-span-2">
          <Field label="Descripción *" error={errors.description}>
            <textarea rows={3} value={form.description} onChange={(event) => setField("description", event.target.value)} className={inputClass} />
          </Field>
        </div>
        <Field label="Estado inicial *" error={errors.status}>
          <select value={form.status} onChange={(event) => setField("status", event.target.value as IncidentStatus)} className={inputClass}>
            {INCIDENT_STATUSES.map((value) => <option key={value} value={value}>{STATUS_LABELS[value]}</option>)}
          </select>
        </Field>
        <Field label="Origen *" error={errors.origin}>
          <select value={form.origin} onChange={(event) => setField("origin", event.target.value as IncidentOrigin)} className={inputClass}>
            {INCIDENT_ORIGINS.map((value) => <option key={value} value={value}>{ORIGIN_LABELS[value]}</option>)}
          </select>
        </Field>
        <div className={`rounded-xl p-3 md:col-span-2 ${form.origin === "branch" ? "bg-amber-50 ring-2 ring-amber-300" : "bg-slate-50"}`}>
          <Field label={form.origin === "branch" ? "Sede que reporta * — confirma la ubicación" : "Sede responsable *"} error={errors.branch}>
            <select value={form.branch} onChange={(event) => setField("branch", event.target.value as IncidentBranch)} className={inputClass}>
              {INCIDENT_BRANCHES.map((value) => <option key={value} value={value}>{BRANCH_LABELS[value]}</option>)}
            </select>
          </Field>
        </div>
        <div className="flex flex-wrap items-center gap-3 md:col-span-2">
          <button type="submit" disabled={busy} className="rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-wait disabled:opacity-60">
            {busy ? "Registrando…" : "Registrar incidente"}
          </button>
          {success && <p role="status" className="text-sm font-medium text-emerald-700">{success}</p>}
          {generalError && <p role="alert" className="text-sm font-medium text-rose-700">{generalError}</p>}
        </div>
      </form>
    </section>
  );
}

function IncidentList({
  incidents,
  filters,
  setFilters,
  state,
  error,
  onRetry,
  onReplace,
  onOptimisticStatus,
  onSummaryChanged,
  onUnauthorized,
}: {
  incidents: Incident[];
  filters: IncidentFilters;
  setFilters: (filters: IncidentFilters) => void;
  state: LoadState;
  error: string;
  onRetry: () => Promise<void>;
  onReplace: (incident: Incident) => void;
  onOptimisticStatus: (id: number, status: IncidentStatus) => void;
  onSummaryChanged: () => Promise<void>;
  onUnauthorized: () => void;
}) {
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState("");

  async function changeStatus(incident: Incident, nextStatus: IncidentStatus) {
    const previousStatus = incident.status;
    setActionError("");
    setBusyId(incident.id);
    onOptimisticStatus(incident.id, nextStatus);
    try {
      onReplace(await incidentsApi.updateStatus(incident.id, nextStatus));
      await onSummaryChanged();
    } catch (requestError) {
      onOptimisticStatus(incident.id, previousStatus);
      if (requestError instanceof IncidentApiError && requestError.status === 401) {
        onUnauthorized();
        return;
      }
      setActionError("No se pudo cambiar el estado; se restauró el valor anterior.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mr-auto text-lg font-bold text-slate-900">Incidentes registrados</h3>
        <FilterSelect label="Estado" value={filters.status ?? ""} onChange={(value) => setFilters({ ...filters, status: value })} options={INCIDENT_STATUSES.map((value) => [value, STATUS_LABELS[value]])} />
        <FilterSelect label="Origen" value={filters.origin ?? ""} onChange={(value) => setFilters({ ...filters, origin: value })} options={INCIDENT_ORIGINS.map((value) => [value, ORIGIN_LABELS[value]])} />
        <FilterSelect label="Sede" value={filters.branch ?? ""} onChange={(value) => setFilters({ ...filters, branch: value })} options={INCIDENT_BRANCHES.map((value) => [value, BRANCH_LABELS[value]])} />
        {(filters.status || filters.origin || filters.branch) && (
          <button onClick={() => setFilters({})} className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">Limpiar</button>
        )}
      </div>

      {actionError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">{actionError}</p>}
      {state === "loading" && <div aria-label="Cargando incidentes" className="h-48 animate-pulse rounded-2xl bg-slate-200/70" />}
      {state === "error" && <RetryState message={error} onRetry={onRetry} />}
      {state === "ready" && incidents.length === 0 && (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-500">No hay incidentes con los filtros seleccionados.</p>
      )}
      {state === "ready" && incidents.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr><th className="px-4 py-3">Incidente</th><th className="px-4 py-3">Categoría</th><th className="px-4 py-3">Origen / sede</th><th className="px-4 py-3">Fecha</th><th className="px-4 py-3">Estado</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {incidents.map((incident) => (
                <tr key={incident.id}>
                  <td className="max-w-md px-4 py-3"><p className="font-semibold text-slate-900">{incident.title}</p><p className="line-clamp-2 text-xs text-slate-500">{incident.description}</p></td>
                  <td className="px-4 py-3"><span className="rounded-full bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700">{CATEGORY_LABELS[incident.category]}</span></td>
                  <td className="px-4 py-3"><p>{ORIGIN_LABELS[incident.origin]}</p><p className="text-xs text-slate-500">{BRANCH_LABELS[incident.branch]}</p></td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-500">{new Date(incident.created_at).toLocaleDateString("es-ES")}</td>
                  <td className="px-4 py-3">
                    <select
                      aria-label={`Estado de ${incident.title}`}
                      value={incident.status}
                      disabled={busyId === incident.id || NEXT_STATUSES[incident.status].length === 0}
                      onChange={(event) => void changeStatus(incident, event.target.value as IncidentStatus)}
                      className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm disabled:bg-slate-100 disabled:text-slate-500"
                    >
                      <option value={incident.status}>{STATUS_LABELS[incident.status]}</option>
                      {NEXT_STATUSES[incident.status].map((status) => <option key={status} value={status}>{STATUS_LABELS[status]}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function IncidentSummaryPanel({ summary, state, error, onRetry }: { summary: IncidentSummary | null; state: LoadState; error: string; onRetry: () => Promise<void> }) {
  if (state === "loading" || state === "idle") return <div aria-label="Cargando métricas" className="h-36 animate-pulse rounded-2xl bg-slate-200/70" />;
  if (state === "error" || !summary) return <RetryState message={error} onRetry={onRetry} />;
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-baseline justify-between"><h3 className="text-lg font-bold text-slate-900">Resumen operativo</h3><span className="text-3xl font-black text-brand-600">{summary.total}</span></div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricGroup title="Por estado" values={summary.by_status} labels={STATUS_LABELS} />
        <MetricGroup title="Por categoría" values={summary.by_category} labels={CATEGORY_LABELS} />
        <MetricGroup title="Por origen" values={summary.by_origin} labels={ORIGIN_LABELS} />
        <MetricGroup title="Por sede" values={summary.by_branch} labels={BRANCH_LABELS} />
      </div>
    </section>
  );
}

function MetricGroup({ title, values, labels }: { title: string; values: Record<string, number>; labels: Record<string, string> }) {
  return <div><h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">{title}</h4><ul className="space-y-1">{Object.entries(values).map(([key, count]) => <li key={key} className="flex justify-between gap-2 text-xs"><span className="truncate text-slate-600">{labels[key] ?? key}</span><strong className="text-slate-900">{count}</strong></li>)}</ul></div>;
}

function RetryState({ message, onRetry }: { message: string; onRetry: () => Promise<void> }) {
  return <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4"><p className="text-sm text-amber-800">{message}</p><button onClick={() => void onRetry()} className="mt-2 rounded-lg bg-amber-700 px-3 py-1.5 text-sm font-semibold text-white">Reintentar</button></div>;
}

function FilterSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: Array<readonly [string, string]> }) {
  return <label><span className="mb-1 block text-xs font-medium text-slate-600">{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm"><option value="">Todos</option>{options.map(([option, text]) => <option key={option} value={option}>{text}</option>)}</select></label>;
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-1 block text-xs font-semibold text-slate-600">{label}</span>{children}{error && <span className="mt-1 block text-xs text-rose-700">{error}</span>}</label>;
}

const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-100";
