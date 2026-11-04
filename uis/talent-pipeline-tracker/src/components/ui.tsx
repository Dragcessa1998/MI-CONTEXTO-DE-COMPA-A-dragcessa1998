/**
 * Componentes presentacionales reutilizables: estados asíncronos (carga, error,
 * vacío) y badges de estado/etapa. Son puros y sin estado.
 */

import {
  statusLabel,
  stageLabel,
  STATUS_BADGE_CLASSES,
} from "@/lib/labels";
import Link from "next/link";
import type { RecordStatus } from "@/types/tracker";

/** Indicador de carga. */
export function LoadingState({ label = "Cargando…" }: { label?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-10 text-slate-500"
    >
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      {label}
    </div>
  );
}

/** Mensaje de error con opción de reintento. */
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-red-200 bg-red-50 px-4 py-6 text-red-800"
    >
      <p className="font-semibold">Algo salió mal</p>
      <p className="mt-1 text-sm">{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-100"
        >
          Reintentar
        </button>
      ) : (
        <Link href="/" className="mt-3 inline-block text-sm font-semibold text-red-700 underline">
          Volver al listado
        </Link>
      )}
    </div>
  );
}

/** Estado vacío (sin resultados). */
export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-12 text-center text-slate-500">
      {message}
    </div>
  );
}

/** Badge legible para el estado de una candidatura. */
export function StatusBadge({ value }: { value: RecordStatus }) {
  const classes =
    STATUS_BADGE_CLASSES[value] ?? "bg-slate-100 text-slate-700 ring-slate-200";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${classes}`}
    >
      {statusLabel(value)}
    </span>
  );
}

/** Badge legible para la etapa de una candidatura. */
export function StageBadge({ value }: { value: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700 ring-1 ring-inset ring-brand-100">
      {stageLabel(value)}
    </span>
  );
}

/** Banner de éxito (feedback tras una operación). */
export function SuccessBanner({ message }: { message: string }) {
  return (
    <div
      role="status"
      className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
    >
      {message}
    </div>
  );
}
