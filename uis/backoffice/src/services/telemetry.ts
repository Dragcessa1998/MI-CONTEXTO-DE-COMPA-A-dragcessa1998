"use client";

export const TELEMETRY_SCHEMA_VERSION = "1.0.0";

const TELEMETRY_ENDPOINT = process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT;
const TELEMETRY_RELEASE = process.env.NEXT_PUBLIC_RELEASE ?? "development";
const BATCH_SIZE = 20;
const DEBOUNCE_MS = 10_000;
const MAX_RETRIES = 3;
const SESSION_ID_KEY = "nexova_telemetry_session_id";
const USER_ID_KEY = "nexova_telemetry_user_id";
const ACTOR_ROLE_KEY = "nexova_telemetry_actor_role";

const PROPERTY_ALLOWLISTS: Record<string, readonly string[]> = {
  inbound_order_created: ["office", "product_id", "product_category", "programme_id", "quantity", "currency", "order_id", "supplier_id", "unit_cost"],
  outbound_order_created: ["office", "product_id", "product_category", "programme_id", "quantity", "currency", "order_id", "recipient_type"],
  stock_threshold_triggered: ["office", "product_id", "product_category", "programme_id", "quantity", "currency", "threshold", "available_quantity"],
  direct_stock_edit_rejected: ["office", "product_id", "product_category", "programme_id", "quantity", "currency", "attempted_operation", "actor_role", "reason_code"],
  kit_cost_variance_detected: ["office", "product_id", "product_category", "programme_id", "quantity", "currency", "supplier_id", "previous_unit_cost", "current_unit_cost", "variance_percent", "threshold_percent"],
  order_validation_failed: ["office", "order_type", "product_id", "programme_id", "error_code", "field_name", "actor_role"],
  stock_level_viewed: ["office", "product_id", "product_category", "programme_id", "view_source", "below_threshold"],
  inventory_export_requested: ["office", "export_format", "filters_count", "row_count_bucket", "actor_role"],
  login_succeeded: ["office", "actor_role", "auth_method"],
  login_failed: ["office", "actor_role", "auth_method", "reason_code", "attempt_count_bucket"],
  session_expired: ["office", "actor_role", "section", "session_age_bucket", "had_unsaved_changes"],
  permission_denied: ["office", "actor_role", "resource_type", "action", "reason_code"],
  api_latency_recorded: ["route_template", "method", "status_class", "duration_ms", "office", "sample_rate"],
  page_load_recorded: ["section", "device_class", "navigation_type", "ttfb_ms", "lcp_ms", "cls", "inp_ms", "sample_rate"],
  frontend_error_captured: ["section", "error_fingerprint", "release", "handled", "office"],
  backend_error_captured: ["route_template", "method", "error_fingerprint", "release", "office", "retryable"],
  section_viewed: ["section", "previous_section", "office", "actor_role"],
  flow_abandoned: ["flow_name", "last_step", "elapsed_ms_bucket", "validation_error_count", "office", "actor_role"],
};

export type TelemetryOffice = "valencia" | "miami" | "unknown";
export type TelemetryActorRole = "admin" | "ld_manager" | "hr_manager" | "operator" | "auditor" | "unknown";
export type TelemetrySection = "dashboard" | "inventory" | "inbound_orders" | "outbound_orders" | "suppliers" | "incidents" | "users" | "reports" | "login" | "unknown";

export interface TelemetryEvent {
  eventId: string;
  timestamp: string;
  sessionId: string | null;
  userId: string | null;
  event_type: string;
  schemaVersion: string;
  requestId: string;
  properties: Record<string, unknown>;
}

const queue: TelemetryEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let sending = false;
let initialized = false;

function uuid(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
    const value = Math.floor(Math.random() * 16);
    const nibble = character === "x" ? value : (value & 0x3) | 0x8;
    return nibble.toString(16);
  });
}

function readSessionValue(key: string): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(key);
}

function ensureSessionId(): string {
  const current = readSessionValue(SESSION_ID_KEY);
  if (current) return current;
  const generated = uuid();
  window.sessionStorage.setItem(SESSION_ID_KEY, generated);
  return generated;
}

export function currentTelemetryOffice(): TelemetryOffice {
  const office = process.env.NEXT_PUBLIC_OFFICE;
  return office === "valencia" || office === "miami" ? office : "unknown";
}

export function currentTelemetryActorRole(): TelemetryActorRole {
  const role = readSessionValue(ACTOR_ROLE_KEY);
  const valid: TelemetryActorRole[] = ["admin", "ld_manager", "hr_manager", "operator", "auditor", "unknown"];
  return valid.includes(role as TelemetryActorRole) ? (role as TelemetryActorRole) : "unknown";
}

export function startTelemetrySession(userId: string, actorRole: TelemetryActorRole): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(SESSION_ID_KEY, uuid());
  window.sessionStorage.setItem(USER_ID_KEY, userId);
  window.sessionStorage.setItem(ACTOR_ROLE_KEY, actorRole);
}

export function restoreTelemetryIdentity(userId: string, actorRole: TelemetryActorRole): void {
  if (typeof window === "undefined") return;
  ensureSessionId();
  window.sessionStorage.setItem(USER_ID_KEY, userId);
  window.sessionStorage.setItem(ACTOR_ROLE_KEY, actorRole);
}

export function clearTelemetryIdentity(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(SESSION_ID_KEY);
  window.sessionStorage.removeItem(USER_ID_KEY);
  window.sessionStorage.removeItem(ACTOR_ROLE_KEY);
}

function allowedProperties(eventType: string, properties: Record<string, unknown>): Record<string, unknown> | null {
  const allowlist = PROPERTY_ALLOWLISTS[eventType];
  if (!allowlist) return null;
  return Object.fromEntries(
    Object.entries(properties).filter(([key]) => allowlist.includes(key)),
  );
}

function scheduleFlush(): void {
  if (flushTimer || typeof window === "undefined") return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    void flushTelemetry();
  }, DEBOUNCE_MS);
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

async function postBatch(events: TelemetryEvent[]): Promise<boolean> {
  if (!TELEMETRY_ENDPOINT) return false;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt += 1) {
    try {
      const response = await fetch(TELEMETRY_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events }),
        keepalive: true,
      });
      if (response.ok) return true;
    } catch {
      // El retry centralizado evita que los componentes conozcan fallos de red.
    }
    if (attempt < MAX_RETRIES) await wait(250 * 2 ** attempt);
  }
  return false;
}

export async function flushTelemetry(): Promise<void> {
  if (sending || queue.length === 0) return;
  sending = true;
  const batch = queue.splice(0, queue.length);
  try {
    await postBatch(batch);
  } finally {
    sending = false;
    if (queue.length > 0) scheduleFlush();
  }
}

function flushWithBeacon(): void {
  if (!TELEMETRY_ENDPOINT || queue.length === 0 || typeof navigator.sendBeacon !== "function") return;
  const batch = queue.splice(0, queue.length);
  const body = new Blob([JSON.stringify({ events: batch })], { type: "application/json" });
  if (!navigator.sendBeacon(TELEMETRY_ENDPOINT, body)) queue.unshift(...batch);
}

export function initializeTelemetry(): () => void {
  if (typeof window === "undefined" || initialized) return () => undefined;
  initialized = true;
  const onVisibilityChange = () => {
    if (document.visibilityState === "hidden") flushWithBeacon();
  };
  document.addEventListener("visibilitychange", onVisibilityChange);
  return () => {
    document.removeEventListener("visibilitychange", onVisibilityChange);
    if (flushTimer) clearTimeout(flushTimer);
    flushTimer = null;
    initialized = false;
  };
}

/** Única entrada pública para capturar telemetría desde componentes. */
export function track(eventType: string, properties: Record<string, unknown>): void {
  if (typeof window === "undefined") return;
  const safeProperties = allowedProperties(eventType, properties);
  if (!safeProperties) return;
  queue.push({
    eventId: uuid(),
    timestamp: new Date().toISOString(),
    sessionId: ensureSessionId(),
    userId: readSessionValue(USER_ID_KEY),
    event_type: eventType,
    schemaVersion: TELEMETRY_SCHEMA_VERSION,
    requestId: uuid(),
    properties: safeProperties,
  });
  if (queue.length >= BATCH_SIZE) void flushTelemetry();
  else scheduleFlush();
}

function stableFingerprint(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `error_${(hash >>> 0).toString(16)}`;
}

export function trackFrontendError(error: unknown, handled: boolean, section: TelemetrySection): void {
  const category = error instanceof Error ? error.name : typeof error;
  track("frontend_error_captured", {
    section,
    error_fingerprint: stableFingerprint(`${category}:${handled ? "handled" : "unhandled"}`),
    release: TELEMETRY_RELEASE,
    handled,
    office: currentTelemetryOffice(),
  });
}
