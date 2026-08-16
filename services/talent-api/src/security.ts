import { createHmac, timingSafeEqual } from "node:crypto";
import type { NextFunction, Request, Response } from "express";


const TOKEN_ISSUER = "nexova-platform";
const TOKEN_AUDIENCE = "nexova-internal";
const DEFAULT_ALLOWED_ORIGINS = ["http://localhost:3001", "http://127.0.0.1:3001"];
const DEFAULT_ALLOWED_ROLES = ["manager", "admin"];

interface JwtHeader {
  alg?: unknown;
  typ?: unknown;
}

interface JwtPayload {
  sub?: unknown;
  role?: unknown;
  iss?: unknown;
  aud?: unknown;
  exp?: unknown;
}

export interface TalentPrincipal {
  userId: string;
  role: string;
}

function commaSeparated(name: string, defaults: string[]): string[] {
  const rawValue = process.env[name];
  const values = (rawValue ? rawValue.split(",") : defaults).map((item) => item.trim()).filter(Boolean);
  if (values.length === 0 || values.includes("*")) {
    throw new Error(`${name} debe ser una allowlist explícita y no vacía`);
  }
  return values;
}

function jwtSecret(): string {
  const secret = process.env.JWT_SECRET ?? "";
  if (secret.length < 32) throw new Error("JWT_SECRET debe tener al menos 32 caracteres");
  return secret;
}

function parseJsonPart<T>(part: string): T {
  return JSON.parse(Buffer.from(part, "base64url").toString("utf8")) as T;
}

export function verifyTalentToken(
  token: string,
  secret: string = jwtSecret(),
  allowedRoles: string[] = commaSeparated("TALENT_API_ALLOWED_ROLES", DEFAULT_ALLOWED_ROLES),
  nowSeconds: number = Math.floor(Date.now() / 1000),
): TalentPrincipal {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("token malformado");
  const [encodedHeader, encodedPayload, encodedSignature] = parts;
  if (!encodedHeader || !encodedPayload || !encodedSignature) throw new Error("token incompleto");

  const header = parseJsonPart<JwtHeader>(encodedHeader);
  const payload = parseJsonPart<JwtPayload>(encodedPayload);
  if (header.alg !== "HS256" || (header.typ !== undefined && header.typ !== "JWT")) {
    throw new Error("algoritmo JWT no permitido");
  }

  const received = Buffer.from(encodedSignature, "base64url");
  const expected = createHmac("sha256", secret)
    .update(`${encodedHeader}.${encodedPayload}`)
    .digest();
  if (received.length !== expected.length || !timingSafeEqual(received, expected)) {
    throw new Error("firma JWT no válida");
  }
  if (payload.iss !== TOKEN_ISSUER || payload.aud !== TOKEN_AUDIENCE) {
    throw new Error("emisor o audiencia JWT no válidos");
  }
  if (typeof payload.exp !== "number" || payload.exp <= nowSeconds) throw new Error("JWT expirado");
  if (typeof payload.sub !== "string" || !/^\d+$/.test(payload.sub)) throw new Error("subject no válido");
  if (typeof payload.role !== "string") throw new Error("rol ausente");
  if (!allowedRoles.includes(payload.role)) throw new Error("rol no autorizado");
  return { userId: payload.sub, role: payload.role };
}

export function securityHeaders(_req: Request, res: Response, next: NextFunction): void {
  res.setHeader("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'");
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()");
  res.setHeader("Cache-Control", "no-store");
  if (process.env.NODE_ENV === "production") {
    res.setHeader("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  }
  next();
}

export function corsAllowlist(req: Request, res: Response, next: NextFunction): void {
  let allowedOrigins: string[];
  try {
    allowedOrigins = commaSeparated("TALENT_API_CORS_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS);
  } catch {
    res.status(503).json({ error: { code: "SECURITY_CONFIG_ERROR", message: "Configuración de seguridad no disponible." } });
    return;
  }
  const origin = req.header("Origin");
  if (origin && allowedOrigins.includes(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Vary", "Origin");
    res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Authorization,Content-Type");
    res.setHeader("Access-Control-Max-Age", "600");
  }
  if (req.method === "OPTIONS") {
    res.sendStatus(origin && allowedOrigins.includes(origin) ? 204 : 403);
    return;
  }
  next();
}

export function requireTalentAccess(req: Request, res: Response, next: NextFunction): void {
  const authorization = req.header("Authorization") ?? "";
  const match = /^Bearer\s+(.+)$/i.exec(authorization);
  if (!match?.[1]) {
    res.status(401).setHeader("WWW-Authenticate", "Bearer");
    res.json({ error: { code: "UNAUTHORIZED", message: "Autenticación obligatoria." } });
    return;
  }
  try {
    res.locals.principal = verifyTalentToken(match[1]);
    next();
  } catch (error) {
    const message = error instanceof Error ? error.message : "";
    const configurationFailure = message.startsWith("JWT_SECRET");
    const authorizationFailure = message === "rol no autorizado";
    const status = configurationFailure ? 503 : authorizationFailure ? 403 : 401;
    if (status === 401) res.setHeader("WWW-Authenticate", "Bearer");
    res.status(status).json({
      error: {
        code: configurationFailure ? "SECURITY_CONFIG_ERROR" : authorizationFailure ? "FORBIDDEN" : "UNAUTHORIZED",
        message: configurationFailure
          ? "Configuración de seguridad no disponible."
          : authorizationFailure
            ? "No tienes permiso para acceder al servicio de talento."
            : "La sesión no es válida o ha caducado.",
      },
    });
  }
}

export function validateTalentSecurityConfiguration(): void {
  jwtSecret();
  commaSeparated("TALENT_API_ALLOWED_ROLES", DEFAULT_ALLOWED_ROLES);
  commaSeparated("TALENT_API_CORS_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS);
}
