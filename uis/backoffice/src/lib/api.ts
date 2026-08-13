/**
 * Cliente HTTP tipado de la Nexova Talent API (Hito 5).
 *
 * El backoffice ya NO importa la lógica del Hito 2 de forma estática: ahora
 * consume la API real por la red (con CORS). Reutiliza los tipos de dominio
 * (`@logic/types/models`) para tipar las respuestas — la misma fuente de verdad
 * que usa el backend.
 *
 * La URL base se configura con `NEXT_PUBLIC_API_URL` (por defecto :4000).
 */

import type { Candidate, Vacancy } from "@logic/types/models";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:4000";

/** Error de API con (opcional) código de estado HTTP. */
export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// ----- Formas de respuesta de la API -----

export interface SummaryResponse {
  totalCandidates: number;
  averageExpectedSalary: number;
  byStatus: Record<string, number>;
  topSkills: { skill: string; count: number }[];
}

export interface FillRateResponse {
  totalProcesses: number;
  fillRatePercent: number;
}

export interface RankingApiRow {
  candidateId: string;
  fullName: string;
  seniority: string;
  score: number;
}

export interface RankingResponse {
  vacancyId: string;
  title: string;
  ranking: RankingApiRow[];
}

export interface ListResponse<T> {
  total: number;
  data: T[];
}

/** Proceso de selección tal y como lo devuelve la API (fechas serializadas como string). */
export interface ProcessDto {
  id: string;
  candidateId: string;
  vacancyId: string;
  stage: string;
  score: number;
  notes: string;
  createdAt: string;
  updatedAt: string;
}

/** Extrae solo mensajes públicos del contrato de error de la API. */
export function extractError(body: unknown): string | null {
  if (body && typeof body === "object") {
    const b = body as {
      errors?: unknown;
      error?: unknown;
    };
    if (b.error && typeof b.error === "object") {
      const structured = b.error as { message?: unknown; details?: unknown };
      const message = typeof structured.message === "string" ? structured.message : null;
      const details = Array.isArray(structured.details)
        ? structured.details.filter((item): item is string => typeof item === "string")
        : [];
      return [message, ...details].filter(Boolean).join(" · ") || null;
    }
    if (Array.isArray(b.errors)) return b.errors.join(" · ");
    if (typeof b.error === "string") return b.error;
  }
  return null;
}

export function safeHttpMessage(status: number): string {
  if (status === 400 || status === 422) return "Revisa los datos enviados e inténtalo de nuevo.";
  if (status === 401) return "Tu sesión no es válida. Inicia sesión de nuevo.";
  if (status === 403) return "No tienes permiso para realizar esta acción.";
  if (status === 404) return "No encontramos el recurso solicitado.";
  if (status === 409) return "Los datos entran en conflicto con un registro existente.";
  return "El servicio no pudo completar la operación. Reintenta en unos instantes.";
}

/** Realiza una petición a la API y normaliza errores de red y de negocio. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("No se pudo conectar con el servicio de talento.");
  }

  if (res.status === 204) {
    return undefined as T;
  }

  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    const contractedMessage = res.status < 500 ? extractError(body) : null;
    throw new ApiError(contractedMessage ?? safeHttpMessage(res.status), res.status);
  }

  if (body === null) {
    throw new ApiError("El servicio devolvió una respuesta que no se pudo leer. Reintenta la operación.");
  }
  return body as T;
}

/** Superficie pública del cliente, una función por endpoint del backend. */
export const api = {
  url: API_URL,
  getSummary: () => request<SummaryResponse>("/reports/summary"),
  getFillRate: () => request<FillRateResponse>("/reports/fill-rate"),
  listCandidates: () => request<ListResponse<Candidate>>("/candidates"),
  listVacancies: () => request<ListResponse<Vacancy>>("/vacancies"),
  getRanking: (vacancyId: string) => request<RankingResponse>(`/vacancies/${vacancyId}/ranking`),
  createCandidate: (payload: Record<string, unknown>) =>
    request<Candidate>("/candidates", { method: "POST", body: JSON.stringify(payload) }),
  listProcesses: () => request<ListResponse<ProcessDto>>("/processes"),
  patchProcess: (id: string, body: Record<string, unknown>) =>
    request<ProcessDto>(`/processes/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
};
