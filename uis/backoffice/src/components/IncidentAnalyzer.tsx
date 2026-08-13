"use client";

import { FormEvent, type ReactNode, useEffect, useState } from "react";

import {
  IncidentApiError,
  SESSION_TOKEN_KEY,
  incidentsApi,
  type IncidentAnalysisSummary,
} from "@/lib/incidents";


const CATEGORY_LABELS: Record<string, string> = {
  TECHNICAL: "Problemas técnicos",
  BILLING: "Facturación",
  ACCESS: "Acceso y permisos",
  HR_QUERY: "Consultas de RR. HH.",
  COMPLAINT: "Quejas formales",
};
const STATUS_LABELS: Record<string, string> = {
  OPEN: "Abiertos",
  CLOSED: "Cerrados",
  DISCARDED: "Descartados",
};
const ERROR_LABELS: Record<string, string> = {
  invalid_ticket_id: "ID de ticket ausente o no válido",
  invalid_date: "Fecha ausente o no válida",
  missing_client_company: "Empresa cliente ausente",
  invalid_category: "Categoría ausente o no válida",
  invalid_description: "Descripción ausente o demasiado corta",
  invalid_agent_id: "ID de agente ausente o no válido",
  invalid_status: "Estado ausente o no válido",
  invalid_email: "Email ausente o no válido",
  closed_without_score: "Ticket cerrado sin satisfacción",
  invalid_score: "Satisfacción fuera del rango 1–5",
};
const SCORE_LABELS: Record<string, string> = {
  "1": "1 · Muy insatisfecho",
  "2": "2 · Insatisfecho",
  "3": "3 · Neutral",
  "4": "4 · Satisfecho",
  "5": "5 · Muy satisfecho",
};


export default function IncidentAnalyzer() {
  const [sessionReady, setSessionReady] = useState(false);
  const [hasSession, setHasSession] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<IncidentAnalysisSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setHasSession(Boolean(window.localStorage.getItem(SESSION_TOKEN_KEY)));
    setSessionReady(true);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setError("Selecciona un archivo CSV antes de analizar.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      setAnalysis(await incidentsApi.analyze(selectedFile));
    } catch (caught) {
      if (caught instanceof IncidentApiError && caught.status === 401) {
        setHasSession(false);
      }
      setError(caught instanceof Error ? caught.message : "No se pudo analizar el archivo.");
    } finally {
      setBusy(false);
    }
  }

  async function downloadResults() {
    setExportBusy(true);
    setError("");
    try {
      const blob = await incidentsApi.exportAnalysis();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "results.csv";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo descargar el CSV.");
    } finally {
      setExportBusy(false);
    }
  }

  if (!sessionReady) {
    return <div className="h-40 animate-pulse rounded-2xl bg-slate-200/70" />;
  }

  if (!hasSession) {
    return (
      <section className="mx-auto max-w-xl rounded-2xl border border-amber-200 bg-amber-50 p-6">
        <p className="text-xs font-bold uppercase tracking-widest text-amber-700">Acceso protegido</p>
        <h2 className="mt-1 text-2xl font-extrabold text-slate-900">Analizador de incidentes</h2>
        <p className="mt-2 text-sm text-slate-700">
          Inicia sesión primero en el gestor de incidentes. Después podrás cargar y analizar el CSV sin exponer datos personales.
        </p>
        <a href="/incidents" className="mt-5 inline-flex rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700">
          Ir a iniciar sesión
        </a>
      </section>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <p className="text-xs font-bold uppercase tracking-widest text-brand-600">Operaciones · Soporte</p>
        <h2 className="text-3xl font-extrabold text-slate-900">Analizador de incidentes CSV</h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">
          Valida y resume el histórico dentro de Nexova. Los emails y detalles de cada cliente nunca aparecen en los resultados.
        </p>
      </header>

      <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <label htmlFor="incident-csv" className="block text-sm font-semibold text-slate-800">
          Archivo CSV de incidentes
        </label>
        <p id="incident-csv-help" className="mt-1 text-sm text-slate-500">
          Debe usar UTF-8 e incluir las nueve columnas del formato Nexova. Límite: 10 MB.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <input
            id="incident-csv"
            type="file"
            accept=".csv,text/csv"
            aria-describedby="incident-csv-help"
            onChange={(event) => {
              setSelectedFile(event.target.files?.[0] ?? null);
              setError("");
            }}
            className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:font-semibold file:text-white"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-wait disabled:opacity-60"
          >
            {busy ? "Analizando…" : "Analizar archivo"}
          </button>
        </div>
        {error && <p role="alert" className="mt-4 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      </form>

      {analysis && (
        <section aria-live="polite" className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-xl font-bold text-slate-900">Resumen de {analysis.source_file}</h3>
              <p className="text-sm text-slate-500">Solo se muestran métricas agregadas.</p>
            </div>
            <button
              type="button"
              onClick={downloadResults}
              disabled={exportBusy}
              className="rounded-lg border border-brand-600 bg-white px-4 py-2 text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:cursor-wait disabled:opacity-60"
            >
              {exportBusy ? "Preparando CSV…" : "Descargar resultados CSV"}
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Metric label="Registros totales" value={analysis.total_records} />
            <Metric label="Registros válidos" value={analysis.valid_records} tone="success" />
            <Metric label="Inválidos o incompletos" value={analysis.invalid_records} tone={analysis.invalid_records ? "warning" : "success"} />
          </div>

          {analysis.invalid_records > 0 && (
            <BreakdownCard title="Problemas detectados" description="Una fila puede activar más de una regla.">
              <BreakdownList
                values={Object.fromEntries(Object.entries(analysis.invalid_breakdown).filter(([, count]) => count > 0))}
                labels={ERROR_LABELS}
              />
            </BreakdownCard>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            <BreakdownCard title="Categorías" description="Solo registros válidos.">
              <BreakdownList values={analysis.category_breakdown} labels={CATEGORY_LABELS} />
            </BreakdownCard>
            <BreakdownCard title="Estados" description="Solo registros válidos.">
              <BreakdownList values={analysis.status_breakdown} labels={STATUS_LABELS} />
            </BreakdownCard>
          </div>

          <BreakdownCard title="Índice de satisfacción" description="Tickets cerrados con puntuación registrada.">
            <div className="grid gap-4 sm:grid-cols-3">
              <Metric label="Cerrados" value={analysis.satisfaction.closed_tickets} />
              <Metric label="Con puntuación" value={analysis.satisfaction.scored_tickets} />
              <Metric
                label="Media sobre 5"
                value={analysis.satisfaction.average_score?.toFixed(2) ?? "—"}
                tone="success"
              />
            </div>
            <div className="mt-4">
              <BreakdownList values={analysis.satisfaction.score_breakdown} labels={SCORE_LABELS} />
            </div>
          </BreakdownCard>
        </section>
      )}
    </div>
  );
}


function Metric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number | string;
  tone?: "neutral" | "success" | "warning";
}) {
  const toneClass = tone === "success" ? "text-emerald-700" : tone === "warning" ? "text-amber-700" : "text-slate-900";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-3xl font-extrabold ${toneClass}`}>{value}</p>
    </div>
  );
}


function BreakdownCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-bold text-slate-900">{title}</h3>
      <p className="mb-4 text-sm text-slate-500">{description}</p>
      {children}
    </section>
  );
}


function BreakdownList({ values, labels }: { values: Record<string, number>; labels: Record<string, string> }) {
  return (
    <dl className="divide-y divide-slate-100">
      {Object.entries(values).map(([key, value]) => (
        <div key={key} className="flex items-center justify-between gap-4 py-2.5">
          <dt className="text-sm text-slate-700">{labels[key] ?? key}</dt>
          <dd className="font-mono text-sm font-bold text-slate-900">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
