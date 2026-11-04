"use client";

import { useCallback, useEffect, useState } from "react";
import { addNote, deleteNote, listNotes, TrackerApiError } from "@/lib/api";
import type { Note } from "@/types/tracker";
import { formatDateTime } from "@/lib/format";
import { LoadingState, ErrorState, EmptyState } from "./ui";

/**
 * Notas internas de la candidatura: listar (GET), añadir (POST) y eliminar
 * (DELETE). Cada operación maneja sus propios estados de carga y error.
 */
export default function NotesSection({ recordId }: { recordId: string }) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [content, setContent] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchNotes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setNotes(await listNotes(recordId));
    } catch (err) {
      setError(err instanceof TrackerApiError ? err.message : "No se pudieron cargar las notas.");
    } finally {
      setLoading(false);
    }
  }, [recordId]);

  useEffect(() => {
    fetchNotes();
  }, [fetchNotes]);

  async function handleAdd(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = content.trim();
    if (trimmed === "") {
      setAddError("Escribe una nota antes de guardarla.");
      return;
    }
    setAdding(true);
    setAddError(null);
    try {
      await addNote(recordId, { content: trimmed });
      setContent("");
      await fetchNotes();
    } catch (err) {
      setAddError(err instanceof TrackerApiError ? err.message : "No se pudo añadir la nota.");
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(noteId: string) {
    setDeletingId(noteId);
    setError(null);
    try {
      await deleteNote(recordId, noteId);
      setNotes((current) => current.filter((note) => note.id !== noteId));
    } catch (err) {
      setError(err instanceof TrackerApiError ? err.message : "No se pudo eliminar la nota.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-lg font-bold text-slate-900">Notas internas</h2>
      <p className="mt-1 text-sm text-slate-500">Visibles solo en el detalle del candidato.</p>

      {/* Formulario para añadir nota */}
      <form onSubmit={handleAdd} className="mt-4">
        <label htmlFor="new-note" className="sr-only">
          Nueva nota
        </label>
        <textarea
          id="new-note"
          value={content}
          onChange={(event) => setContent(event.target.value)}
          rows={3}
          placeholder="Añade una nota tras una llamada o entrevista…"
          className="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-600/30"
        />
        {addError && (
          <div role="alert" className="mt-1 text-sm text-red-600">
            <p>{addError}</p>
            <p className="text-xs">La nota sigue en el formulario: revisa el texto y vuelve a pulsar “Añadir nota”.</p>
          </div>
        )}
        <div className="mt-2 flex justify-end">
          <button
            type="submit"
            disabled={adding}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-60"
          >
            {adding ? "Guardando…" : "Añadir nota"}
          </button>
        </div>
      </form>

      {/* Listado de notas */}
      <div className="mt-4">
        {loading ? (
          <LoadingState label="Cargando notas…" />
        ) : error ? (
          <ErrorState message={error} onRetry={fetchNotes} />
        ) : notes.length === 0 ? (
          <EmptyState message="Aún no hay notas para esta candidatura." />
        ) : (
          <ul className="space-y-3">
            {notes.map((note) => (
              <li key={note.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="whitespace-pre-wrap text-sm text-slate-800">{note.content}</p>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-xs text-slate-400">{formatDateTime(note.created_at)}</span>
                  <button
                    type="button"
                    onClick={() => handleDelete(note.id)}
                    disabled={deletingId === note.id}
                    className="text-xs font-medium text-red-600 hover:text-red-700 disabled:opacity-60"
                  >
                    {deletingId === note.id ? "Eliminando…" : "Eliminar"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
