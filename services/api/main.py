"""
Directorio de Proveedores de Nexova — Lightweight Storage API.

FastAPI + TinyDB + Pydantic. Registro oficial y único de los servicios externos
que contrata Nexova (job boards, ATS, formación, nóminas…), en sustitución de la
hoja de cálculo de Patricia Solís (HR Manager). Proyecto solicitado por el CTO,
Sergio Molina.

Arranque:
    uv run seed                          # carga inicial (idempotente)
    uv run uvicorn main:app --port 8000  # API + Swagger en /docs
"""

import math

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import suppliers_table
from routes.auth import router as auth_router
from routes.profiles import router as profiles_router
from routes.suppliers import router as suppliers_router
from routes.users import router as users_router

app = FastAPI(
    title="Nexova — Authenticated Supplier API",
    description="Directorio de proveedores protegido con usuarios y perfiles TinyDB y JWT.",
    version="2.0.0",
)

# CORS: el backoffice (uis/backoffice, :3000) consume esta API desde el navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(suppliers_router)


def _sanitize_non_finite(value: object) -> object:
    """Sustituye inf/-inf/nan por su representación en texto para que el cuerpo
    del 422 sea serializable (el JSON estándar no admite esos literales)."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _sanitize_non_finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_non_finite(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 consistente incluso si la entrada contiene Infinity/NaN: sin este
    handler, FastAPI eco-serializa el valor no finito y el 422 se convierte en 500."""
    detail = _sanitize_non_finite(jsonable_encoder(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get("/health", tags=["health"])
def health() -> dict:
    """Estado del servicio y tamaño del directorio."""
    return {"status": "ok", "suppliers": len(suppliers_table())}
