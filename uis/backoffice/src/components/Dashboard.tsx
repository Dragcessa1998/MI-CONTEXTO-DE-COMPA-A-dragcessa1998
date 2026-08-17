"use client";

import { useCallback, useEffect, useState } from "react";

import {
  api,
  ApiError,
  type SummaryResponse,
  type FillRateResponse,
  type RankingResponse,
} from "@/lib/api";
import type { Candidate, Vacancy } from "@logic/types/models";
import { STATUS_LABELS } from "@/lib/labels";
import Kpi from "@/components/Kpi";
import RankingTable, { type RankingRow } from "@/components/RankingTable";
import AddCandidateForm from "@/components/AddCandidateForm";
import ApiErrorState from "@/components/ApiErrorState";

interface DashboardData {
  summary: SummaryResponse;
  fillRate: FillRateResponse;
  candidates: Candidate[];
  vacancy: Vacancy | undefined;
  ranking: RankingResponse | null;
}

type LoadState = "loading" | "ready" | "error";

/**
 * Panel del backoffice servido por datos EN VIVO de la Nexova Talent API (Hito 5).
 * Carga reportes, candidatos y ranking en paralelo; permite refrescar y dar de alta
 * candidatos (que recalculan el panel al instante).
 */
export default function Dashboard() {
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string>("");
  const [data, setData] = useState<DashboardData | null>(null);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setState("loading");
    setError("");
    try {
      const [summary, fillRate, candidatesRes, vacanciesRes] = await Promise.all([
        api.getSummary(),
        api.getFillRate(),
        api.listCandidates(),
        api.listVacancies(),
      ]);
      const vacancy = vacanciesRes.data[0];
      const ranking = vacancy ? await api.getRanking(vacancy.id) : null;
      setData({ summary, fillRate, candidates: candidatesRes.data, vacancy, ranking });
      setState("ready");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cargar el panel de talento.");
      setState("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-900">Panel de talento</h2>
          <p className="text-sm text-slate-500">
            Datos en vivo desde la <strong>Nexova Talent API</strong> (Hito 5) — scoring y reportes calculados con la lógica del Hito 2.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ConnectionBadge state={state} />
          <button
            onClick={load}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Refrescar
          </button>
          <button
            onClick={() => setShowForm((value) => !value)}
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-700"
          >
            {showForm ? "Cerrar" : "Nuevo candidato"}
          </button>
        </div>
      </div>

      {showForm && (
        <AddCandidateForm
          onCreated={() => {
            setShowForm(false);
            load();
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {state === "loading" && <LoadingState />}
      {state === "error" && <ApiErrorState message={error} onRetry={load} />}
      {state === "ready" && data && <DashboardContent data={data} />}
    </div>
  );
}

/** Indicador de conexión con la API. */
function ConnectionBadge({ state }: { state: LoadState }) {
  const map = {
    loading: { dot: "bg-amber-400", text: "Conectando…" },
    ready: { dot: "bg-emerald-500", text: "Conectado" },
    error: { dot: "bg-rose-500", text: "Sin conexión" },
  } as const;
  const current = map[state];
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600">
      <span className={`h-2 w-2 rounded-full ${current.dot}`} />
      {current.text}
    </span>
  );
}

/** Esqueleto de carga. */
function LoadingState() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-24 animate-pulse rounded-2xl border border-slate-200 bg-slate-200/60" />
      ))}
    </div>
  );
}

/** Contenido del panel cuando los datos están listos. */
function DashboardContent({ data }: { data: DashboardData }) {
  const { summary, fillRate, candidates, vacancy, ranking } = data;
  const best = ranking?.ranking[0];
  const statuses = Object.keys(summary.byStatus);

  // Componemos las filas del ranking enriqueciéndolas con email y salario del
  // listado de candidatos (el endpoint de ranking devuelve solo lo esencial).
  const rankingRows: RankingRow[] = (ranking?.ranking ?? []).map((row) => {
    const candidate = candidates.find((item) => item.id === row.candidateId);
    return {
      id: row.candidateId,
      fullName: row.fullName,
      email: candidate?.email,
      seniority: row.seniority,
      expectedSalary: candidate?.expectedSalary,
      score: row.score,
    };
  });

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi value={summary.totalCandidates} label="Candidatos en el banco" />
        <Kpi value={`${summary.averageExpectedSalary.toLocaleString("es-ES")} $`} label="Salario esperado medio" />
        <Kpi value={`${fillRate.fillRatePercent}%`} label="Cobertura (procesos → Hired)" />
        <Kpi value={best?.score ?? 0} label={`Mejor match · ${best?.fullName ?? "—"}`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-bold text-slate-900">Candidatos por estado</h3>
          {statuses.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">Sin datos.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {statuses.map((status) => (
                <li key={status} className="flex items-center justify-between">
                  <span className="text-slate-600">
                    {STATUS_LABELS[status as keyof typeof STATUS_LABELS] ?? status}
                  </span>
                  <span className="font-semibold text-slate-900">{summary.byStatus[status]}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <h3 className="text-sm font-bold text-slate-900">Habilidades más frecuentes</h3>
          {summary.topSkills.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">Sin datos.</p>
          ) : (
            <ul className="mt-3 flex flex-wrap gap-2">
              {summary.topSkills.map((item) => (
                <li
                  key={item.skill}
                  className="inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-sm text-brand-700 ring-1 ring-inset ring-brand-100"
                >
                  {item.skill}
                  <span className="rounded-full bg-brand-600 px-1.5 text-xs font-semibold text-white">{item.count}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="space-y-3">
        <div>
          <h3 className="text-lg font-bold text-slate-900">Ranking para: {vacancy?.title ?? "—"}</h3>
          <p className="text-sm text-slate-500">
            {vacancy?.companyName ?? ""} · scoring 0-100 vía{" "}
            <code className="rounded bg-slate-100 px-1">GET /vacancies/:id/ranking</code>
          </p>
        </div>
        {rankingRows.length === 0 ? (
          <p className="text-sm text-slate-400">No hay candidatos para rankear.</p>
        ) : (
          <RankingTable rows={rankingRows} />
        )}
      </section>
    </>
  );
}
