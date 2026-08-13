/**
 * Capa de acceso a datos: un wrapper de fetch tipado y una función por endpoint
 * de la API del tracker. Todas las peticiones son asíncronas (async/await) y
 * lanzan un Error con un mensaje legible cuando la respuesta no es correcta.
 */

import type {
  TrackerRecord,
  Note,
  RecordListResponse,
  NotesListResponse,
  RecordCreateInput,
  RecordPatchInput,
  NoteCreateInput,
  RecordFilters,
} from "@/types/tracker";
import { authenticatedHeaders, clearExpiredSession } from "@/lib/auth";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "https://playground.4geeks.com/tracker/api/v1";

/** Extrae un mensaje de error legible del cuerpo de una respuesta fallida. */
async function extractError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail.length > 0) {
      return body.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ");
    }
  } catch {
    /* el cuerpo no era JSON */
  }
  return `Error ${response.status} ${response.statusText}`.trim();
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: authenticatedHeaders(options?.headers),
    cache: "no-store",
  });

  if (!response.ok) {
    if (response.status === 401) clearExpiredSession();
    throw new Error(await extractError(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** GET /records con filtros opcionales (status, stage, search). */
export function listRecords(filters: RecordFilters = {}): Promise<RecordListResponse> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.stage) params.set("stage", filters.stage);
  if (filters.search) params.set("search", filters.search);
  params.set("limit", "100");
  const query = params.toString();
  return request<RecordListResponse>(`/records${query ? `?${query}` : ""}`);
}

/** GET /records/:id */
export function getRecord(id: string): Promise<TrackerRecord> {
  return request<TrackerRecord>(`/records/${id}`);
}

/** POST /records */
export function createRecord(input: RecordCreateInput): Promise<TrackerRecord> {
  return request<TrackerRecord>(`/records`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** PUT /records/:id (reemplazo completo) */
export function updateRecord(id: string, input: RecordCreateInput): Promise<TrackerRecord> {
  return request<TrackerRecord>(`/records/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

/** PATCH /records/:id (estado y/o etapa) */
export function patchRecord(id: string, input: RecordPatchInput): Promise<TrackerRecord> {
  return request<TrackerRecord>(`/records/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

/** DELETE /records/:id (elimina la candidatura por completo) */
export function deleteRecord(id: string): Promise<void> {
  return request<void>(`/records/${id}`, {
    method: "DELETE",
  });
}

/** GET /records/:id/notes */
export async function listNotes(id: string): Promise<Note[]> {
  const response = await request<NotesListResponse>(`/records/${id}/notes`);
  return response.data;
}

/** POST /records/:id/notes */
export function addNote(id: string, input: NoteCreateInput): Promise<Note> {
  return request<Note>(`/records/${id}/notes`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** DELETE /records/:id/notes/:noteId */
export function deleteNote(id: string, noteId: string): Promise<void> {
  return request<void>(`/records/${id}/notes/${noteId}`, {
    method: "DELETE",
  });
}
