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
import os

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app_security import install_security_middleware
from database import suppliers_table
from routes.agent import router as agent_router
from routes.auth import router as auth_router
from routes.chat import router as chat_router
from routes.incidents import router as incidents_router
from routes.knowledge import router as knowledge_router
from routes.profiles import router as profiles_router
from routes.rfps import router as rfps_router
from routes.suppliers import router as suppliers_router
from routes.users import router as users_router

is_production = os.getenv("APP_ENV") == "production"
app = FastAPI(
    title="Nexova — Operations Platform API",
    description="Auth, proveedores e incidentes operativos centralizados sobre FastAPI y TinyDB.",
    version="3.0.0",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

install_security_middleware(app)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(suppliers_router)
app.include_router(incidents_router)
app.include_router(knowledge_router)
app.include_router(agent_router)
app.include_router(chat_router)
app.include_router(rfps_router)


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
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 consistente incluso si la entrada contiene Infinity/NaN: sin este
    handler, FastAPI eco-serializa el valor no finito y el 422 se convierte en 500."""
    detail = _sanitize_non_finite(jsonable_encoder(exc.errors()))
    if request.url.path.startswith("/api/incidents"):
        fields: dict[str, str] = {}
        messages = {
            "missing": "Este campo es obligatorio",
            "string_too_short": "El texto es demasiado corto",
            "string_too_long": "El texto es demasiado largo",
            "extra_forbidden": "Este campo no está permitido",
            "int_parsing": "Debe ser un número entero",
        }
        for error in exc.errors():
            location = error.get("loc", ())
            field = str(location[-1]) if location else "body"
            message = messages.get(str(error.get("type")), "Valor no válido")
            if error.get("type") == "value_error":
                message = str(error.get("msg", "Valor no válido")).replace("Value error, ", "")
            fields[field] = message
        return JSONResponse(
            status_code=400,
            content={"error": "Datos del incidente no válidos", "fields": fields},
        )
    return JSONResponse(status_code=422, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """El cliente nunca recibe detalles internos ni trazas del servidor."""
    return JSONResponse(
        status_code=500,
        content={"detail": "No se pudo completar la operación. Inténtalo de nuevo."},
    )


@app.get("/health", tags=["health"])
def health() -> dict:
    """Estado del servicio y tamaño del directorio."""
    return {"status": "ok", "suppliers": len(suppliers_table())}
