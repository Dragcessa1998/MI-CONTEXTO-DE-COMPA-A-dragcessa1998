"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { listRecords } from "@/lib/api";
import { filterRecords } from "@/lib/filters";
import type { TrackerRecord } from "@/types/tracker";
import Filters from "./Filters";
import CandidateTable from "./CandidateTable";
import { LoadingState, ErrorState, EmptyState } from "./ui";

/**
 * Vista de listado de candidaturas. Lee los filtros desde la URL (query params)
 * y consulta la API; maneja explícitamente los estados de carga, error y vacío.
 */
export default function CandidatesView() {
  const searchParams = useSearchParams();
  const status = searchParams.get("status") ?? "";
  const stage = searchParams.get("stage") ?? "";
  const search = searchParams.get("q") ?? "";

  const [records, setRecords] = useState<TrackerRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listRecords({ status, stage, search });
      const visibleRecords = filterRecords(response.data, { status, stage, search });
      setRecords(visibleRecords);
      setTotal(visibleRecords.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido al cargar las candidaturas");
    } finally {
      setLoading(false);
    }
  }, [status, stage, search]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900">Candidaturas</h1>
          <p className="text-sm text-slate-500">
            Proceso activo: <span className="font-medium text-slate-700">Asistente de Dirección</span> · Sede de Valencia
          </p>
        </div>
        {!loading && !error && (
          <p className="text-sm text-slate-500" aria-live="polite">
            Mostrando <span className="font-semibold text-slate-700">{records.length}</span> de {total}
          </p>
        )}
      </div>

      <Filters status={status} stage={stage} search={search} />

      {loading ? (
        <LoadingState label="Cargando candidaturas…" />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchData} />
      ) : records.length === 0 ? (
        <EmptyState message="No hay candidaturas que coincidan con los filtros aplicados." />
      ) : (
        <CandidateTable records={records} />
      )}
    </div>
  );
}
