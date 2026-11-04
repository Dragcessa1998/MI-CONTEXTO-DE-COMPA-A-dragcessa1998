/**
 * Cliente HTTP tipado de la Supplier Directory API (FastAPI + TinyDB).
 *
 * Es un servicio distinto de la talent-api: corre en :8000 y devuelve los
 * errores en el formato de FastAPI ({"detail": [...]}), así que tiene su propio
 * parseo. La URL se configura con NEXT_PUBLIC_SUPPLIERS_API_URL.
 */

import { ApiError } from "@/lib/api";
import { SESSION_TOKEN_KEY } from "@/lib/incidents";

const SUPPLIERS_API_URL = process.env.NEXT_PUBLIC_SUPPLIERS_API_URL ?? "/platform-api";

// ----- Dominio (espejo exacto del CONTEXT del supplier-directory) -----

export const SUPPLIER_COUNTRIES = ["Spain", "USA"] as const;
export type SupplierCountry = (typeof SUPPLIER_COUNTRIES)[number];

export const SUPPLIER_STATUSES = ["active", "suspended"] as const;
export type SupplierStatus = (typeof SUPPLIER_STATUSES)[number];

export const VALID_CATEGORIES = [
  "job_boards",
  "ats_software",
  "assessment_tools",
  "training_platforms",
  "payroll_and_hr_software",
  "video_interview",
  "background_check",
  "office_and_facilities",
  "it_and_software_licenses",
] as const;
export type SupplierCategory = (typeof VALID_CATEGORIES)[number];

/** Categoría → etiqueta en español (la UI nunca muestra el valor crudo). */
export const CATEGORY_LABELS: Record<SupplierCategory, string> = {
  job_boards: "Portales de empleo",
  ats_software: "Software ATS",
  assessment_tools: "Herramientas de evaluación",
  training_platforms: "Plataformas de formación",
  payroll_and_hr_software: "Nóminas y RRHH",
  video_interview: "Videoentrevistas",
  background_check: "Verificación de antecedentes",
  office_and_facilities: "Oficinas e instalaciones",
  it_and_software_licenses: "Licencias IT y software",
};

/** Estado → etiqueta en español. */
export const SUPPLIER_STATUS_LABELS: Record<SupplierStatus, string> = {
  active: "Activo",
  suspended: "Suspendido",
};

/** Moneda esperada según el país (restricción del CONTEXT: Spain→EUR, USA→USD). */
export const CURRENCY_BY_COUNTRY: Record<SupplierCountry, "EUR" | "USD"> = {
  Spain: "EUR",
  USA: "USD",
};

/** Proveedor tal y como lo devuelve la API. */
export interface Supplier {
  id: number;
  name: string;
  country: SupplierCountry;
  categories: string[];
  monthly_rate: number;
  currency: "EUR" | "USD";
  status: SupplierStatus;
  contract_renewal_date: string | null;
  contact_email: string | null;
  notes: string | null;
  rate_updated_at: string;
}

/** Payload de alta (sin id ni rate_updated_at: los genera el sistema). */
export type SupplierInput = Omit<Supplier, "id" | "rate_updated_at">;

// ----- Transporte -----

/** Convierte el cuerpo de error de FastAPI en un mensaje legible.
 *  422 → {"detail": [{loc, msg, ...}]} · 404 → {"detail": "..."} */
function extractFastApiError(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const entry = item as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(entry.loc) ? String(entry.loc[entry.loc.length - 1]) : "";
        const rawMessage = (entry.msg ?? "").replace(/^Value error, /, "");
        const message = rawMessage === "Field required"
          ? "Este campo es obligatorio"
          : rawMessage.includes("valid number")
            ? "Debe ser un número válido"
            : rawMessage;
        return field && field !== "body" ? `${field}: ${message}` : message;
      })
      .join(" · ");
  }
  return null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const token = typeof window === "undefined" ? "" : window.localStorage.getItem(SESSION_TOKEN_KEY) ?? "";
  try {
    res = await fetch(`${SUPPLIERS_API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("No se pudo conectar con el directorio de proveedores.");
  }

  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    const message = res.status === 401
      ? "Tu sesión no es válida. Inicia sesión desde el gestor de incidentes y vuelve a intentarlo."
      : res.status === 403
        ? "No tienes permiso para realizar esta acción."
        : res.status >= 500
          ? "El directorio no pudo completar la operación. Reintenta en unos instantes."
          : extractFastApiError(body) ?? "Revisa los datos enviados e inténtalo de nuevo.";
    throw new ApiError(message, res.status);
  }
  if (body === null) throw new ApiError("El directorio devolvió una respuesta ilegible. Reintenta la operación.");
  return body as T;
}

/** Superficie pública: una función por endpoint de la Supplier API. */
export const suppliersApi = {
  url: SUPPLIERS_API_URL,
  list: (filters?: { country?: string; category?: string }) => {
    const params = new URLSearchParams();
    if (filters?.country) params.set("country", filters.country);
    if (filters?.category) params.set("category", filters.category);
    const qs = params.toString();
    return request<Supplier[]>(`/suppliers${qs ? `?${qs}` : ""}`);
  },
  create: (payload: SupplierInput) =>
    request<Supplier>("/suppliers", { method: "POST", body: JSON.stringify(payload) }),
  updateRate: (id: number, monthlyRate: number) =>
    request<Supplier>(`/suppliers/${id}/rate`, {
      method: "PATCH",
      body: JSON.stringify({ monthly_rate: monthlyRate }),
    }),
  updateStatus: (id: number, status: SupplierStatus) =>
    request<Supplier>(`/suppliers/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
};
