const API_URL =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL ??
  process.env.NEXT_PUBLIC_SUPPLIERS_API_URL ??
  "http://localhost:8000";

export const SESSION_TOKEN_KEY = "nexova_access_token";

export const INCIDENT_STATUSES = ["open", "in_progress", "resolved", "discarded"] as const;
export type IncidentStatus = (typeof INCIDENT_STATUSES)[number];
export const STATUS_LABELS: Record<IncidentStatus, string> = {
  open: "Abierto",
  in_progress: "En progreso",
  resolved: "Resuelto",
  discarded: "Descartado",
};

export const INCIDENT_ORIGINS = ["customer", "branch", "internal"] as const;
export type IncidentOrigin = (typeof INCIDENT_ORIGINS)[number];
export const ORIGIN_LABELS: Record<IncidentOrigin, string> = {
  customer: "Cliente",
  branch: "Sede",
  internal: "Interno",
};

export const INCIDENT_BRANCHES = ["central", "valencia_operations", "miami_office", "remote"] as const;
export type IncidentBranch = (typeof INCIDENT_BRANCHES)[number];
export const BRANCH_LABELS: Record<IncidentBranch, string> = {
  central: "Central — Valencia HQ",
  valencia_operations: "Valencia — Operations",
  miami_office: "Miami Office",
  remote: "Remote (no fixed office)",
};

export const INCIDENT_CATEGORIES = [
  "technical_failure",
  "process_error",
  "client_complaint",
  "candidate_issue",
  "staff_issue",
  "sla_breach",
  "data_quality",
  "other",
] as const;
export type IncidentCategory = (typeof INCIDENT_CATEGORIES)[number];
export const CATEGORY_LABELS: Record<IncidentCategory, string> = {
  technical_failure: "Fallo técnico",
  process_error: "Error de proceso",
  client_complaint: "Queja de cliente",
  candidate_issue: "Incidencia de candidato",
  staff_issue: "Incidencia de personal",
  sla_breach: "Incumplimiento de SLA",
  data_quality: "Calidad de datos",
  other: "Otro",
};

export const NEXT_STATUSES: Record<IncidentStatus, IncidentStatus[]> = {
  open: ["in_progress", "discarded"],
  in_progress: ["resolved", "discarded"],
  resolved: [],
  discarded: [],
};

export interface Incident {
  id: number;
  title: string;
  description: string;
  category: IncidentCategory;
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: IncidentBranch;
  created_at: string;
  updated_at: string;
}

export type IncidentInput = Omit<Incident, "id" | "created_at" | "updated_at">;

export interface IncidentSummary {
  total: number;
  by_status: Record<IncidentStatus, number>;
  by_category: Record<IncidentCategory, number>;
  by_origin: Record<IncidentOrigin, number>;
  by_branch: Record<IncidentBranch, number>;
}

export interface IncidentFilters {
  status?: string;
  origin?: string;
  branch?: string;
  category?: string;
}

export interface IncidentAnalysisSummary {
  source_file: string;
  total_records: number;
  valid_records: number;
  invalid_records: number;
  invalid_breakdown: Record<string, number>;
  category_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  satisfaction: {
    closed_tickets: number;
    scored_tickets: number;
    average_score: number | null;
    score_breakdown: Record<string, number>;
  };
}

export class IncidentApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly fields: Record<string, string> = {},
  ) {
    super(message);
  }
}

function sessionToken(): string {
  return typeof window === "undefined" ? "" : window.localStorage.getItem(SESSION_TOKEN_KEY) ?? "";
}

async function request<T>(path: string, init?: RequestInit, authenticated = true): Promise<T> {
  let response: Response;
  const token = authenticated ? sessionToken() : "";
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new IncidentApiError("No se pudo conectar con el servicio de incidentes. Inténtalo de nuevo.");
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const payload = body && typeof body === "object" ? (body as Record<string, unknown>) : {};
    const fields = payload.fields && typeof payload.fields === "object"
      ? (payload.fields as Record<string, string>)
      : {};
    const safeMessage = response.status === 401
      ? "Tu sesión no es válida o ha expirado. Inicia sesión de nuevo."
      : response.status === 400
        ? "Revisa los datos indicados e inténtalo de nuevo."
        : response.status === 404
          ? "El incidente ya no está disponible."
          : "No pudimos completar la operación. Inténtalo de nuevo.";
    throw new IncidentApiError(safeMessage, response.status, fields);
  }
  return body as T;
}

export const incidentsApi = {
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string; expires_in: number }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    ),
  list: (filters: IncidentFilters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const query = params.toString();
    return request<Incident[]>(`/api/incidents${query ? `?${query}` : ""}`);
  },
  summary: () => request<IncidentSummary>("/api/incidents/summary"),
  create: (payload: IncidentInput) =>
    request<Incident>("/api/incidents", { method: "POST", body: JSON.stringify(payload) }),
  updateStatus: (id: number, status: IncidentStatus) =>
    request<Incident>(`/api/incidents/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  analyze: async (file: File): Promise<IncidentAnalysisSummary> => {
    const formData = new FormData();
    formData.append("file", file);
    return requestAnalysis<IncidentAnalysisSummary>("/api/incidents/analyze", {
      method: "POST",
      body: formData,
    });
  },
  exportAnalysis: async (): Promise<Blob> => {
    const token = sessionToken();
    let response: Response;
    try {
      response = await fetch(`${API_URL}/api/incidents/results/export`, {
        cache: "no-store",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch {
      throw new IncidentApiError("No se pudo conectar con el servicio de incidentes.");
    }
    if (!response.ok) {
      throw new IncidentApiError(
        response.status === 401
          ? "Tu sesión no es válida o ha expirado."
          : "No hay resultados disponibles para descargar.",
        response.status,
      );
    }
    return response.blob();
  },
};

async function requestAnalysis<T>(path: string, init: RequestInit): Promise<T> {
  const token = sessionToken();
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch {
    throw new IncidentApiError("No se pudo conectar con el servicio de incidentes.");
  }

  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : "No se pudo analizar el archivo.";
    throw new IncidentApiError(detail, response.status);
  }
  return body as T;
}
