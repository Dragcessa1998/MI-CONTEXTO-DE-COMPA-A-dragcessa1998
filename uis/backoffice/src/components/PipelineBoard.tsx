"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ApiError, type ProcessDto } from "@/lib/api";
import type { Candidate, Vacancy } from "@logic/types/models";
import { PROCESS_STAGES, PROCESS_STAGE_LABELS } from "@/lib/labels";
import ApiErrorState from "@/components/ApiErrorState";

type LoadState = "loading" | "ready" | "error";

interface BoardData {
  processes: ProcessDto[];
  candidates: Candidate[];
  vacancies: Vacancy[];
}

/**
 * Tablero del pipeline de selección, en vivo desde la Talent API. Agrupa los
 * procesos por etapa y permite moverlos de etapa con `PATCH /processes/:id`,
 * recargando el tablero al instante.
 */
export default function PipelineBoard() {
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [data, setData] = useState<BoardData | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState("loading");
    setError("");
    try {
      const [processesRes, candidatesRes, vacanciesRes] = await Promise.all([
        api.listProcesses(),
        api.listCandidates(),
        api.listVacancies(),
      ]);
      setData({
        processes: processesRes.data,
        candidates: candidatesRes.data,
        vacancies: vacanciesRes.data,
      });
      setState("ready");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudieron cargar los procesos.");
      setState("error");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const changeStage = useCallback(
    async (processId: string, stage: string) => {
      setUpdatingId(processId);
      try {
        await api.patchProcess(processId, { stage });
        await load();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "No se pudo actualizar el proceso.");
        setState("error");
      } finally {
        setUpdatingId(null);
      }
    },
    [load],
  );

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-900">Procesos de selección</h2>
          <p className="text-sm text-slate-500">
            Pipeline de candidatos por etapa, en vivo desde la <strong>Nexova Talent API</strong>. Mueve a un candidato de etapa y se guarda con{" "}
            <code className="rounded bg-slate-100 px-1">PATCH /processes/:id</code>.
          </p>
        </div>
        <button
          onClick={load}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Refrescar
        </button>
      </div>

      {state === "loading" && <BoardSkeleton />}
      {state === "error" && <ApiErrorState message={error} onRetry={load} />}
      {state === "ready" && data && (
        <Board data={data} updatingId={updatingId} onChangeStage={changeStage} />
      )}
    </div>
  );
}

/** Esqueleto de carga del tablero. */
function BoardSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="h-40 animate-pulse rounded-2xl border border-slate-200 bg-slate-200/60" />
      ))}
    </div>
  );
}

/** Columnas por etapa con las tarjetas de cada proceso. */
function Board({
  data,
  updatingId,
  onChangeStage,
}: {
  data: BoardData;
  updatingId: string | null;
  onChangeStage: (id: string, stage: string) => void;
}) {
  const candidateName = (id: string) => data.candidates.find((c) => c.id === id)?.fullName ?? id;
  const vacancyTitle = (id: string) => data.vacancies.find((v) => v.id === id)?.title ?? id;

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {PROCESS_STAGES.map((stage) => {
        const items = data.processes.filter((process) => process.stage === stage);
        return (
          <section key={stage} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-3">
            <header className="mb-3 flex items-center justify-between px-1">
              <h3 className="text-sm font-bold text-slate-900">{PROCESS_STAGE_LABELS[stage]}</h3>
              <span className="rounded-full bg-slate-200 px-2 text-xs font-semibold text-slate-600">{items.length}</span>
            </header>
            <ul className="space-y-2">
              {items.length === 0 ? (
                <li className="rounded-lg border border-dashed border-slate-200 px-3 py-4 text-center text-xs text-slate-400">
                  Sin candidatos
                </li>
              ) : (
                items.map((process) => (
                  <li key={process.id} className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-900">{candidateName(process.candidateId)}</p>
                      <span className="shrink-0 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-700">{process.score}</span>
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500">{vacancyTitle(process.vacancyId)}</p>
                    <select
                      value={process.stage}
                      disabled={updatingId === process.id}
                      onChange={(event) => onChangeStage(process.id, event.target.value)}
                      className="mt-3 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:opacity-50"
                      aria-label={`Cambiar etapa de ${candidateName(process.candidateId)}`}
                    >
                      {PROCESS_STAGES.map((option) => (
                        <option key={option} value={option}>{PROCESS_STAGE_LABELS[option]}</option>
                      ))}
                    </select>
                  </li>
                ))
              )}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
