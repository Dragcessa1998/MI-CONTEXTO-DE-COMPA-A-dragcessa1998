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

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "https://playground.4geeks.com/tracker/api/v1";

export class TrackerApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = "TrackerApiError";
  }
}

function safeHttpMessage(status: number): string {
  if (status === 400 || status === 422) return "Revisa los datos del formulario e inténtalo de nuevo.";
  if (status === 401) return "Tu sesión ha expirado. Vuelve a iniciar sesión.";
  if (status === 403) return "No tienes permiso para realizar esta acción.";
  if (status === 404) return "No encontramos la candidatura solicitada.";
  if (status === 409) return "Ya existe un registro con esos datos.";
  return "El servicio de candidaturas no está disponible. Reintenta en unos instantes.";
}

/** Traduce errores de validación conocidos sin mostrar mensajes técnicos del servidor. */
async function validationMessage(response: Response): Promise<string | null> {
  if (response.status !== 400 && response.status !== 422) return null;
  try {
    const body = await response.json() as { detail?: unknown };
    if (Array.isArray(body?.detail) && body.detail.length > 0) {
      const fields = body.detail
        .map((item) => {
          const entry = item as { loc?: unknown[] };
          const field = entry.loc?.at(-1);
          return typeof field === "string" ? field.replaceAll("_", " ") : null;
        })
        .filter((field): field is string => field !== null);
      if (fields.length > 0) return `Revisa: ${[...new Set(fields)].join(", ")}.`;
    }
  } catch {
    return null;
  }
  return null;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      ...options,
    });
  } catch {
    throw new TrackerApiError("No se pudo conectar con el servicio de candidaturas.");
  }

  if (!response.ok) {
    throw new TrackerApiError(
      (await validationMessage(response)) ?? safeHttpMessage(response.status),
      response.status,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new TrackerApiError("El servicio devolvió una respuesta ilegible. Reintenta la operación.");
  }
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
  return response?.data ?? [];
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
