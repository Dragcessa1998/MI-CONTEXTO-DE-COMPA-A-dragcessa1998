"""Collector mínimo de telemetría para validar la captura por lotes."""

import logging
import os
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# Se declara desde el primer hito para que un collector futuro pueda reenviar a
# otro servicio sin introducir una URL en el código.
TELEMETRY_ENDPOINT = os.getenv("TELEMETRY_ENDPOINT", "")


class TelemetryEvent(BaseModel):
    """Envelope 1.0.0 compartido por todos los productores de Nexova."""

    model_config = ConfigDict(extra="forbid")

    eventId: UUID
    timestamp: datetime
    sessionId: str | None = Field(min_length=8)
    userId: str | None = Field(min_length=1)
    event_type: str = Field(pattern=r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")
    schemaVersion: Literal["1.0.0"]
    requestId: str = Field(min_length=8)
    properties: dict[str, Any]

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        return value


class TelemetryBatch(BaseModel):
    """Cuerpo del endpoint; el frontend siempre envía uno o más eventos."""

    model_config = ConfigDict(extra="forbid")

    events: list[TelemetryEvent] = Field(min_length=1)


@router.post("/events")
def collect_events(payload: TelemetryBatch) -> dict[str, int]:
    """Registra metadatos seguros del lote y confirma cuántos eventos recibió."""

    event_types = [event.event_type for event in payload.events]
    logger.info(
        "telemetry_events_received count=%d event_types=%s",
        len(payload.events),
        ",".join(event_types),
    )
    return {"received": len(payload.events)}
