const API_URL = process.env.NEXT_PUBLIC_PLATFORM_API_URL ?? "/platform-api";

export interface EventsPerDayMetric {
  date: string;
  event_count: number;
}

export interface ErrorRateMetric {
  date: string;
  event_type: string;
  total_events: number;
  error_events: number;
  error_rate: number;
}

export interface LatencyMetric {
  route_template: string;
  mean_latency_ms: number;
  sample_count: number;
}

export interface AuthFailureMetric {
  date: string;
  login_attempts: number;
  login_failures: number;
  failure_rate: number;
}

export interface TelemetryReport {
  period: { from: string; to: string };
  metrics: {
    events_per_day: EventsPerDayMetric[];
    error_rate_by_type: ErrorRateMetric[];
    latency_by_route: LatencyMetric[];
    auth_failure_rate: AuthFailureMetric[];
  };
}

export async function getTelemetryReport(): Promise<TelemetryReport> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/telemetry/report`, { cache: "no-store" });
  } catch {
    throw new Error("No se pudo conectar con el informe técnico.");
  }
  if (!response.ok) {
    throw new Error("El informe técnico no está disponible en este momento.");
  }
  try {
    return (await response.json()) as TelemetryReport;
  } catch {
    throw new Error("El servicio devolvió un informe no válido.");
  }
}
