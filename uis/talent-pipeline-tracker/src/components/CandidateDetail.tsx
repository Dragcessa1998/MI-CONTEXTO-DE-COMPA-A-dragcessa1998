"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { deleteRecord, getRecord } from "@/lib/api";
import type { TrackerRecord } from "@/types/tracker";
import { formatDate } from "@/lib/format";
import { LoadingState, ErrorState, StatusBadge, StageBadge, SuccessBanner } from "./ui";
import StatusStageControls from "./StatusStageControls";
import NotesSection from "./NotesSection";

/** Fila de un campo del candidato (etiqueta + valor o enlace). */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-900">{children}</dd>
    </div>
  );
}

export default function CandidateDetail({
  id,
  saved,
}: {
  id: string;
  saved?: "created" | "updated";
}) {
  const router = useRouter();
  const [record, setRecord] = useState<TrackerRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Estado del borrado de la candidatura (DELETE /records/:id).
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const fetchRecord = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRecord(await getRecord(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar la candidatura");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchRecord();
  }, [fetchRecord]);

  async function handleDelete() {
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteRecord(id);
      // Vuelve al listado y fuerza un refetch para que la candidatura ya no aparezca.
      router.push("/");
      router.refresh();
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "No se pudo eliminar la candidatura");
      setDeleting(false);
    }
  }

  if (loading) return <LoadingState label="Cargando candidatura…" />;
  if (error) return <ErrorState message={error} onRetry={fetchRecord} />;
  if (!record) return null;

  return (
    <div className="space-y-6">
      <Link href="/" className="inline-flex items-center text-sm font-medium text-brand-600 hover:text-brand-700">
        ← Volver al listado
      </Link>

      {saved && (
        <SuccessBanner
          message={
            saved === "created"
              ? "Candidatura registrada correctamente."
              : "Datos de la candidatura actualizados correctamente."
          }
        />
      )}

      <header className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900">{record.full_name}</h1>
            <p className="mt-1 text-slate-600">{record.position}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusBadge value={record.status} />
              <StageBadge value={record.stage} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/candidates/${record.id}/edit`}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              Editar datos
            </Link>
            <button
              type="button"
              onClick={() => {
                setConfirmingDelete(true);
                setDeleteError(null);
              }}
              className="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-700 transition hover:bg-red-50"
            >
              Eliminar
            </button>
          </div>
        </div>

        {confirmingDelete && (
          <div role="alertdialog" aria-label="Confirmar eliminación" className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-800">
              ¿Eliminar la candidatura de {record.full_name}? Esta acción no se puede deshacer.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-60"
              >
                {deleting ? "Eliminando…" : "Sí, eliminar"}
              </button>
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                disabled={deleting}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {deleteError && (
          <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {deleteError}
          </p>
        )}

        <dl className="mt-6 grid gap-4 sm:grid-cols-2">
          <Field label="Email">
            <a className="text-brand-700 hover:underline" href={`mailto:${record.email}`}>{record.email}</a>
          </Field>
          <Field label="Teléfono">{record.phone}</Field>
          <Field label="Años de experiencia">{record.experience_years}</Field>
          <Field label="Fecha de aplicación">{formatDate(record.applied_at)}</Field>
          <Field label="LinkedIn">
            {record.linkedin_url ? (
              <a className="text-brand-700 hover:underline" href={record.linkedin_url} target="_blank" rel="noopener noreferrer">
                Ver perfil
              </a>
            ) : (
              <span className="text-slate-400">—</span>
            )}
          </Field>
          <Field label="CV">
            {record.cv_url ? (
              <a className="text-brand-700 hover:underline" href={record.cv_url} target="_blank" rel="noopener noreferrer">
                Descargar CV
              </a>
            ) : (
              <span className="text-slate-400">—</span>
            )}
          </Field>
        </dl>
      </header>

      <StatusStageControls record={record} onUpdated={setRecord} />

      <NotesSection recordId={record.id} />
    </div>
  );
}
