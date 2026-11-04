"use client";

import { useState } from "react";
import { patchRecord, TrackerApiError } from "@/lib/api";
import type { TrackerRecord, RecordStatus, RecordStage } from "@/types/tracker";
import { STATUS_OPTIONS, STAGE_OPTIONS } from "@/lib/labels";

interface Props {
  record: TrackerRecord;
  /** Se llama con la candidatura actualizada tras un PATCH correcto. */
  onUpdated: (record: TrackerRecord) => void;
}

/**
 * Controles para actualizar el estado y la etapa de la candidatura mediante
 * PATCH. Refleja el cambio en la UI sin recargar y muestra carga/éxito/error.
 */
export default function StatusStageControls({ record, onUpdated }: Props) {
  const [saving, setSaving] = useState<null | "status" | "stage">(null);
  const [error, setError] = useState<string | null>(null);
  const [savedField, setSavedField] = useState<null | "status" | "stage">(null);

  async function update(field: "status" | "stage", value: string) {
    setSaving(field);
    setError(null);
    setSavedField(null);
    try {
      const payload =
        field === "status"
          ? { status: value as RecordStatus }
          : { stage: value as RecordStage };
      const updated = await patchRecord(record.id, payload);
      onUpdated(updated);
      setSavedField(field);
    } catch (err) {
      setError(err instanceof TrackerApiError ? err.message : "No se pudo actualizar el proceso.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-lg font-bold text-slate-900">Estado del proceso</h2>
      <p className="mt-1 text-sm text-slate-500">Cambia el estado o la etapa; se guarda automáticamente.</p>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="control-status" className="block text-xs font-medium text-slate-600">
            Estado
          </label>
          <select
            id="control-status"
            value={record.status}
            disabled={saving !== null}
            onChange={(event) => update("status", event.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/30 disabled:opacity-60"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {saving === "status" && <p className="mt-1 text-xs text-slate-500">Guardando…</p>}
          {savedField === "status" && <p className="mt-1 text-xs text-emerald-600">Estado actualizado ✓</p>}
        </div>

        <div>
          <label htmlFor="control-stage" className="block text-xs font-medium text-slate-600">
            Etapa
          </label>
          <select
            id="control-stage"
            value={record.stage}
            disabled={saving !== null}
            onChange={(event) => update("stage", event.target.value)}
            className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/30 disabled:opacity-60"
          >
            {STAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {saving === "stage" && <p className="mt-1 text-xs text-slate-500">Guardando…</p>}
          {savedField === "stage" && <p className="mt-1 text-xs text-emerald-600">Etapa actualizada ✓</p>}
        </div>
      </div>

      {error && (
        <div role="alert" className="mt-3 text-sm text-red-600">
          <p>{error}</p>
          <p className="text-xs">La selección anterior sigue activa; vuelve a elegir una opción para reintentar.</p>
        </div>
      )}
    </section>
  );
}
