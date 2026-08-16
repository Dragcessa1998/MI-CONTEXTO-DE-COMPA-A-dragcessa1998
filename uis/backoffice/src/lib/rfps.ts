import { SESSION_TOKEN_KEY } from "@/lib/incidents";

const API_URL = process.env.NEXT_PUBLIC_PLATFORM_API_URL ?? "/platform-api";

export type RfpStatus =
  | "analyzing"
  | "discarded"
  | "intake_complete"
  | "drafting"
  | "under_evaluation"
  | "needs_human_review"
  | "waiting_for_approval"
  | "done";

export type ApprovalDecision = "approve" | "reject" | "request_changes";

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
  draft_content?: string | null;
  evaluation_results?: EvaluationResult[] | null;
  generation_iteration?: number;
  approval_status?: "pending" | "approved" | "rejected" | null;
  approval_iteration?: number;
  approval_feedback?: string | null;
  approver?: string | null;
  approved_at?: string | null;
}

export interface EvaluationResult {
  section_id: DepartmentSection["department_id"];
  readability: { pass: boolean; score: number; details: string };
  relevance: { pass: boolean; missing_aspects: string[] };
  compliance: { pass: boolean; rule_ids: string[]; violations: string[] };
  overall_pass: boolean;
  actionable_feedback: string[];
  iteration: number;
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

export interface FinalDocument {
  ticket_id: string;
  content: string;
  file_path: string;
  currency: "EUR" | "USD";
  sections: DepartmentSection["department_id"][];
  generated_at: string;
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
  generate: (ticketId: string) => request<{ ticket_id: string; status: RfpStatus; status_url: string }>(
    `/api/rfps/${ticketId}/draft`,
    { method: "POST" },
  ),
  startApprovals: (ticketId: string) => request<{ ticket_id: string; status: RfpStatus }>(
    `/api/rfps/${ticketId}/approvals/start`,
    { method: "POST" },
  ),
  resumeApproval: (ticketId: string, departmentId: DepartmentSection["department_id"], decision: ApprovalDecision, feedback?: string) => request<{
    ticket_id: string;
    status: RfpStatus;
    final_document: FinalDocument | null;
  }>(`/api/rfps/${ticketId}/approvals/${departmentId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, ...(feedback ? { feedback } : {}) }),
  }),
  final: (ticketId: string) => request<FinalDocument>(`/api/rfps/${ticketId}/final`),
};
