import type { Response } from "express";

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    details?: string[];
  };
}

/** Construye el único formato de error público; nunca acepta una excepción. */
export function errorPayload(
  code: string,
  message: string,
  details?: string[],
): ApiErrorPayload {
  return {
    error: {
      code,
      message,
      ...(details && details.length > 0 ? { details } : {}),
    },
  };
}

export function sendError(
  response: Response,
  status: number,
  code: string,
  message: string,
  details?: string[],
): Response {
  return response.status(status).json(errorPayload(code, message, details));
}

export function isMalformedJson(error: unknown): boolean {
  return error instanceof SyntaxError && typeof error === "object" && error !== null && "body" in error;
}
