"""Configuración web defensiva compartida por la API FastAPI."""

from __future__ import annotations

import os
from collections.abc import Iterable

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response


DEFAULT_CORS_ORIGINS = ("http://localhost:3001", "http://127.0.0.1:3001")
DEFAULT_TRUSTED_HOSTS = ("localhost", "127.0.0.1", "testserver", "backend")


def _csv_setting(name: str, default: Iterable[str]) -> tuple[str, ...]:
    raw_value = os.getenv(name)
    values = tuple(item.strip() for item in raw_value.split(",")) if raw_value else tuple(default)
    cleaned = tuple(item for item in values if item)
    if not cleaned or "*" in cleaned:
        raise RuntimeError(f"{name} debe ser una allowlist explícita y no vacía")
    return cleaned


def allowed_cors_origins() -> tuple[str, ...]:
    return _csv_setting("CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ORIGINS)


def trusted_hosts() -> tuple[str, ...]:
    return _csv_setting("TRUSTED_HOSTS", DEFAULT_TRUSTED_HOSTS)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault("Cache-Control", "no-store")
        if request.url.scheme == "https" or os.getenv("APP_ENV") == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


def install_security_middleware(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(trusted_hosts()))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_cors_origins()),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
        expose_headers=["Retry-After"],
        max_age=600,
    )


__all__ = [
    "SecurityHeadersMiddleware",
    "allowed_cors_origins",
    "install_security_middleware",
    "trusted_hosts",
]
