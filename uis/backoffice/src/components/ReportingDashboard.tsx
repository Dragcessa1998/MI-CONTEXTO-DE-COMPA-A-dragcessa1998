"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getWeeklyPerformance,
  ReportingApiError,
  type WeeklyPerformanceEntry,
  type WeeklyPerformanceReport,
} from "@/lib/reporting";


export default function ReportingDashboard() {
  const [report, setReport] = useState<WeeklyPerformanceReport | null>(null);
  const [weekStart, setWeekStart] = useState("");
  const [office, setOffice] = useState("all");
  const [programme, setProgramme] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [unauthorized, setUnauthorized] = useState(false);

  const load = useCallback(async (selectedWeek?: string) => {
    setLoading(true);
    setError("");
    setUnauthorized(false);
    try {
      const nextReport = await getWeeklyPerformance(selectedWeek || undefined);
      setReport(nextReport);
    } catch (caught) {
      setReport(null);
      setUnauthorized(caught instanceof ReportingApiError && caught.status === 401);
      setError(caught instanceof Error ? caught.message : "No se pudo cargar el informe semanal.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const offices = useMemo(
    () => sortedUnique(report?.entries.map((entry) => entry.office) ?? []),
    [report],
  );
  const programmes = useMemo(
    () => sortedUnique(
      (report?.entries ?? [])
        .filter((entry) => office === "all" || entry.office === office)
        .map((entry) => entry.programme_id),
    ),
    [office, report],
  );
  const visibleEntries = useMemo(
    () => (report?.entries ?? []).filter(
      (entry) => (office === "all" || entry.office === office)
        && (programme === "all" || entry.programme_id === programme),
    ),
    [office, programme, report],
  );

  useEffect(() => {
    if (programme !== "all" && !programmes.includes(programme)) setProgramme("all");
  }, [programme, programmes]);

  const totals = useMemo(() => summarize(visibleEntries), [visibleEntries]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-brand-600">Dirección · Informe semanal</p>
          <h2 className="text-2xl font-extrabold text-slate-900">Rendimiento por oficina y programa</h2>
          <p className="mt-1 max-w-3xl text-sm text-slate-500">
            Vista de Laura Mendoza y Elena Vargas para controlar coste de materiales, entregas y riesgos operativos.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load(weekStart || undefined)}
          disabled={loading}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60"
        >
          {loading ? "Actualizando…" : "Actualizar datos"}
        </button>
      </header>

      <section className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm md:grid-cols-3">
        <label className="text-sm font-semibold text-slate-700">
          Semana (lunes UTC)
          <input
            type="date"
            value={weekStart}
            onChange={(event) => setWeekStart(event.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 font-normal"
          />
        </label>
        <label className="text-sm font-semibold text-slate-700">
          Oficina
          <select
            value={office}
            onChange={(event) => setOffice(event.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 font-normal"
          >
            <option value="all">Todas</option>
            {offices.map((value) => <option key={value} value={value}>{title(value)}</option>)}
          </select>
        </label>
        <label className="text-sm font-semibold text-slate-700">
          Programa
          <select
            value={programme}
            onChange={(event) => setProgramme(event.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 font-normal"
          >
            <option value="all">Todos</option>
            {programmes.map((value) => <option key={value} value={value}>{title(value)}</option>)}
          </select>
        </label>
      </section>

      {loading && !report && <div className="h-48 animate-pulse rounded-2xl bg-slate-200/70" />}

      {error && (
        <section role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-5">
          <h3 className="font-bold text-rose-900">Informe no disponible</h3>
          <p className="mt-1 text-sm text-rose-800">{error}</p>
          <div className="mt-3 flex gap-4 text-sm font-bold text-rose-900">
            {unauthorized && <a className="underline" href="/incidents">Iniciar sesión</a>}
            <button type="button" onClick={() => void load(weekStart || undefined)} className="underline">Reintentar</button>
          </div>
        </section>
      )}

      {report && (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Periodo del informe</p>
            <p className="mt-2 text-sm font-semibold text-slate-800">
              {report.week_start ? weekRange(report.week_start) : "Sin semana publicada"}
            </p>
            <p className="mt-1 text-xs text-slate-500">Inicio incluido · fin excluido · granularidad: oficina, programa y semana ISO.</p>
          </section>

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Cuatro KPI del informe semanal">
            <KpiCard label="Coste de materiales" value={formatCurrencyTotals(totals.materialByCurrency)} detail="Suma de cantidad × coste unitario" />
            <KpiCard label="Kits entregados" value={totals.kits.toLocaleString("es-ES")} detail="Eventos de salida aceptados" />
            <KpiCard label="Frecuencia de faltantes" value={totals.shortages.toLocaleString("es-ES")} detail="Alertas de umbral de stock" />
            <KpiCard label="Frecuencia de variación" value={totals.variances.toLocaleString("es-ES")} detail="Anomalías de coste detectadas" />
          </section>

          <PerformanceTable entries={visibleEntries} />
        </>
      )}
    </div>
  );
}

function KpiCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-black text-slate-900">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </article>
  );
}

function PerformanceTable({ entries }: { entries: WeeklyPerformanceEntry[] }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-5 py-4">
        <h3 className="font-extrabold text-slate-900">Detalle operativo</h3>
        <p className="text-sm text-slate-500">Comparación sin mezclar monedas entre oficinas.</p>
      </div>
      {entries.length === 0 ? (
        <p className="px-5 py-8 text-sm text-slate-500">No hay resultados para los filtros seleccionados.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                {["Oficina", "Programa", "Coste material", "Kits", "Faltantes", "Variaciones"].map((header) => (
                  <th key={header} scope="col" className="px-4 py-3">{header}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {entries.map((entry) => (
                <tr key={`${entry.office}-${entry.programme_id}`}>
                  <td className="px-4 py-3 font-semibold">{title(entry.office)}</td>
                  <td className="px-4 py-3">{title(entry.programme_id)}</td>
                  <td className="px-4 py-3">{formatMoney(entry.total_material_cost, entry.currency)}</td>
                  <td className="px-4 py-3">{entry.kits_delivered_count.toLocaleString("es-ES")}</td>
                  <td className="px-4 py-3">{entry.shortage_events_count.toLocaleString("es-ES")}</td>
                  <td className="px-4 py-3">{entry.cost_variance_events_count.toLocaleString("es-ES")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function summarize(entries: WeeklyPerformanceEntry[]) {
  return entries.reduce(
    (total, entry) => ({
      materialByCurrency: {
        ...total.materialByCurrency,
        [entry.currency]: (total.materialByCurrency[entry.currency] ?? 0) + entry.total_material_cost,
      },
      kits: total.kits + entry.kits_delivered_count,
      shortages: total.shortages + entry.shortage_events_count,
      variances: total.variances + entry.cost_variance_events_count,
    }),
    { materialByCurrency: {} as Record<string, number>, kits: 0, shortages: 0, variances: 0 },
  );
}

function formatCurrencyTotals(totals: Record<string, number>): string {
  const values = Object.entries(totals).sort().map(([currency, value]) => formatMoney(value, currency));
  return values.length ? values.join(" · ") : "—";
}

function formatMoney(value: number, currency: string): string {
  return new Intl.NumberFormat("es-ES", { style: "currency", currency }).format(value);
}

function sortedUnique(values: string[]): string[] {
  return [...new Set(values)].sort((left, right) => left.localeCompare(right));
}

function title(value: string): string {
  return value.replaceAll("-", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function weekRange(weekStart: string): string {
  const start = new Date(`${weekStart}T00:00:00Z`);
  const end = new Date(start);
  end.setUTCDate(start.getUTCDate() + 7);
  const formatter = new Intl.DateTimeFormat("es-ES", { dateStyle: "long", timeZone: "UTC" });
  return `${formatter.format(start)} — ${formatter.format(end)} UTC`;
}
