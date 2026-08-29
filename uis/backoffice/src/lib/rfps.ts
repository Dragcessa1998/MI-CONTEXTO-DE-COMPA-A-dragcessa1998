import { SESSION_TOKEN_KEY } from "@/lib/incidents";

const API_URL = process.env.NEXT_PUBLIC_PLATFORM_API_URL ?? "/platform-api";

export type RfpStatus = "analyzing" | "discarded" | "intake_complete";

export interface RfpMetadata {
  client_name: string;
  client_hq: "España" | "Miami" | "desconocida";
  currency: "EUR" | "USD" | "por_confirmar";
  services_requested: string[];
  scope: string;
  volumes: Record<string, number>;
  deadline: string | null;
  budget_range: string | null;
  departments_needed: Array<"seleccion" | "capacitacion" | "soporte">;
  readability: {
    word_count: number;
    sentence_count: number;
    average_words_per_sentence: number;
    flesch_reading_ease: number;
    gunning_fog: number;
  };
}

export interface DepartmentSection {
  department_id: "seleccion" | "capacitacion" | "soporte";
  department_name: string;
  contact: string;
  key_aspects: string[];
  open_questions: string[];
  relevant_excerpts: string[];
}

export interface RfpTicket {
  ticket_id: string;
  rfp_id: string;
  status: RfpStatus;
  raw_pdf_path: string;
  markdown_path: string | null;
  classification_reason: string | null;
  sales_summary: string | null;
  processing_error: string | null;
  created_at: string;
  updated_at: string;
  metadata: RfpMetadata | null;
  sections: DepartmentSection[];
}

export class RfpApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
  }
}

function token(): string {
  return typeof window === "undefined" ? "" : window.localStorage.getItem(SESSION_TOKEN_KEY) ?? "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: { ...(token() ? { Authorization: `Bearer ${token()}` } : {}), ...(init?.headers ?? {}) },
    });
  } catch {
    throw new RfpApiError("No se pudo conectar con el servicio de RFPs.");
  }
  let body: unknown = null;
  try { body = await response.json(); } catch { body = null; }
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : "No se pudo completar la operación.";
    throw new RfpApiError(response.status < 500 ? detail : "El servicio RFP no está disponible.", response.status);
  }
  return body as T;
}

export const rfpsApi = {
  upload(file: File) {
    const data = new FormData();
    data.append("file", file);
    return request<{ ticket_id: string; status: RfpStatus; status_url: string }>("/api/rfps", {
      method: "POST",
      body: data,
    });
  },
  list: () => request<RfpTicket[]>("/api/rfps"),
  detail: (ticketId: string) => request<RfpTicket>(`/api/rfps/${ticketId}`),
};
