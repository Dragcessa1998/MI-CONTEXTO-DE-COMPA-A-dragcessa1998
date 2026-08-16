import { sessionToken } from "@/lib/session";


const API_URL = process.env.NEXT_PUBLIC_PLATFORM_API_URL ?? "/platform-api";

export interface WeeklyPerformanceEntry {
  office: string;
  programme_id: string;
  total_material_cost: number;
  kits_delivered_count: number;
  shortage_events_count: number;
  cost_variance_events_count: number;
  currency: string;
}

export interface WeeklyPerformanceReport {
  week_start: string | null;
  entries: WeeklyPerformanceEntry[];
}

export class ReportingApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message);
  }
}

export async function getWeeklyPerformance(weekStart?: string): Promise<WeeklyPerformanceReport> {
  const query = weekStart ? `?week_start=${encodeURIComponent(weekStart)}` : "";
  const token = sessionToken();
  let response: Response;
  try {
    response = await fetch(`${API_URL}/reporting/weekly-office-program-performance${query}`, {
      cache: "no-store",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
  } catch {
    throw new ReportingApiError("No se pudo conectar con el servicio de reporting.");
  }

  if (!response.ok) {
    const message = response.status === 401
      ? "Inicia sesión para consultar el informe ejecutivo."
      : response.status === 422
        ? "La semana debe comenzar en lunes."
        : "El informe semanal no está disponible en este momento.";
    throw new ReportingApiError(message, response.status);
  }

  try {
    return (await response.json()) as WeeklyPerformanceReport;
  } catch {
    throw new ReportingApiError("El servicio devolvió un informe no válido.");
  }
}
