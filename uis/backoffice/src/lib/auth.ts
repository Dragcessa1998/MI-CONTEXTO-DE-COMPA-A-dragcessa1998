export const AUTH_API_URL =
  process.env.NEXT_PUBLIC_AUTH_API_URL ??
  process.env.NEXT_PUBLIC_PLATFORM_API_URL ??
  process.env.NEXT_PUBLIC_SUPPLIERS_API_URL ??
  "http://localhost:8000";

export const SESSION_TOKEN_KEY = "nexova_access_token";
export const AUTH_EXPIRED_EVENT = "nexova:auth-expired";

export interface Profile {
  id: number;
  user_id: number;
  name: string;
  phone: string;
  address: string;
}

export interface AuthUser {
  id: number;
  email: string;
  is_active: boolean;
  role: "admin" | "manager" | "user";
  created_at: string;
  profile: Profile;
}

export interface RegistrationInput {
  email: string;
  password: string;
  name: string;
  phone: string;
  address: string;
}

export class AuthError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly fields: Record<string, string> = {},
  ) {
    super(message);
    this.name = "AuthError";
  }
}

export function sessionToken(): string {
  return typeof window === "undefined"
    ? ""
    : window.localStorage.getItem(SESSION_TOKEN_KEY) ?? "";
}

export function authenticatedHeaders(headers?: HeadersInit): HeadersInit {
  const result = new Headers(headers);
  if (!result.has("Content-Type")) result.set("Content-Type", "application/json");
  const token = sessionToken();
  if (token && !result.has("Authorization")) result.set("Authorization", `Bearer ${token}`);
  return result;
}

export function clearExpiredSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(SESSION_TOKEN_KEY);
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
}

function parseError(body: unknown): { message: string; fields: Record<string, string> } {
  if (!body || typeof body !== "object") {
    return { message: "No se pudo completar la operación.", fields: {} };
  }
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return { message: detail, fields: {} };
  if (!Array.isArray(detail)) {
    return { message: "No se pudo completar la operación.", fields: {} };
  }
  const fields: Record<string, string> = {};
  for (const item of detail) {
    const issue = item as { loc?: unknown[]; msg?: string };
    const field = Array.isArray(issue.loc) ? String(issue.loc.at(-1) ?? "form") : "form";
    fields[field] = (issue.msg ?? "Valor no válido").replace(/^Value error, /, "");
  }
  return { message: "Revisa los campos indicados.", fields };
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = false): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${AUTH_API_URL}${path}`, {
      ...init,
      cache: "no-store",
      headers: authenticated
        ? authenticatedHeaders(init.headers)
        : { "Content-Type": "application/json", ...(init.headers ?? {}) },
    });
  } catch {
    throw new AuthError("No se pudo conectar con el servicio de autenticación.");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && authenticated) clearExpiredSession();
    const parsed = parseError(body);
    throw new AuthError(parsed.message, response.status, parsed.fields);
  }
  return body as T;
}

export const authApi = {
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string; expires_in: number }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
    ),
  register: (input: RegistrationInput) =>
    request<AuthUser>("/users", { method: "POST", body: JSON.stringify(input) }),
  me: () => request<AuthUser>("/auth/me", {}, true),
};
