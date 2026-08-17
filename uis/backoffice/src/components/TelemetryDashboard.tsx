"use client";

import { useCallback, useEffect, useState } from "react";

import { getTelemetryReport, type TelemetryReport } from "@/lib/telemetryReport";


export default function TelemetryDashboard() {
  const [report, setReport] = useState<TelemetryReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setReport(await getTelemetryReport());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo cargar el informe técnico.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-brand-600">Ingeniería · Observabilidad</p>
          <h2 className="text-2xl font-extrabold text-slate-900">Informe técnico de telemetría</h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-500">
            Volumen, errores, latencia y autenticación. Esta vista no contiene métricas de ventas ni conversión.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60"
        >
          {loading ? "Actualizando…" : "Actualizar"}
        </button>
      </header>

      {loading && !report && <div className="h-48 animate-pulse rounded-2xl bg-slate-200/70" />}

      {error && (
        <section role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-5">
          <h3 className="font-bold text-rose-900">Informe no disponible</h3>
          <p className="mt-1 text-sm text-rose-800">{error}</p>
          <button type="button" onClick={() => void load()} className="mt-3 text-sm font-bold text-rose-900 underline">
            Reintentar
          </button>
        </section>
      )}

      {report && (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Periodo UTC mostrado</p>
            <p className="mt-2 text-sm font-semibold text-slate-800">
              {formatTimestamp(report.period.from)} <span className="font-normal text-slate-400">hasta</span>{" "}
              {formatTimestamp(report.period.to)}
            </p>
            <p className="mt-1 text-xs text-slate-500">Inicio incluido · fin excluido · caché del servidor: 60 segundos.</p>
          </section>

          <div className="grid gap-6 xl:grid-cols-2">
            <MetricCard title="Eventos por día" description="Permite detectar caídas o picos de instrumentación.">
              <MetricTable
                headers={["Fecha", "Eventos"]}
                rows={report.metrics.events_per_day.map((item) => [item.date, item.event_count.toLocaleString("es-ES")])}
              />
            </MetricCard>

            <MetricCard title="Tasa de error por tipo" description="Segmenta los fallos por fecha y señal técnica.">
              <MetricTable
                headers={["Fecha", "Tipo", "Errores", "Tasa"]}
                rows={report.metrics.error_rate_by_type.map((item) => [
                  item.date,
                  readableEvent(item.event_type),
                  `${item.error_events}/${item.total_events}`,
                  formatPercent(item.error_rate),
                ])}
              />
            </MetricCard>

            <MetricCard title="Latencia por ruta" description="Media observada y tamaño de muestra por endpoint.">
              <MetricTable
                headers={["Ruta", "Media", "Muestras"]}
                rows={report.metrics.latency_by_route.map((item) => [
                  item.route_template,
                  `${item.mean_latency_ms.toLocaleString("es-ES")} ms`,
                  item.sample_count.toLocaleString("es-ES"),
                ])}
              />
            </MetricCard>

            <MetricCard title="Fallos de autenticación" description="Proporción diaria de intentos de login fallidos.">
              <MetricTable
                headers={["Fecha", "Fallos", "Intentos", "Tasa"]}
                rows={report.metrics.auth_failure_rate.map((item) => [
                  item.date,
                  item.login_failures.toLocaleString("es-ES"),
                  item.login_attempts.toLocaleString("es-ES"),
                  formatPercent(item.failure_rate),
                ])}
              />
            </MetricCard>
          </div>
        </>
      )}
    </div>
  );
}

function MetricCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-5 py-4">
        <h3 className="font-extrabold text-slate-900">{title}</h3>
        <p className="text-sm text-slate-500">{description}</p>
      </div>
      {children}
    </section>
  );
}

function MetricTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  if (rows.length === 0) {
    return <p className="px-5 py-8 text-sm text-slate-500">No hay eventos para esta métrica en el periodo.</p>;
  }
  return (
    <div className="max-h-80 overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>{headers.map((header) => <th key={header} scope="col" className="px-4 py-3">{header}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-slate-700">
          {rows.map((row, rowIndex) => (
            <tr key={`${row[0]}-${rowIndex}`}>
              {row.map((value, cellIndex) => <td key={`${cellIndex}-${value}`} className="px-4 py-3">{value}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(value));
}

function formatPercent(value: number): string {
  return new Intl.NumberFormat("es-ES", { style: "percent", maximumFractionDigits: 2 }).format(value);
}

function readableEvent(value: string): string {
  return value.replaceAll("_", " ");
}
