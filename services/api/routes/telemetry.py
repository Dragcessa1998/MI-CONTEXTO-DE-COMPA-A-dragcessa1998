"""Collector mínimo de telemetría para validar la captura por lotes."""

import json
import logging
import os
from datetime import datetime
from typing import Any, Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


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


class TelemetryStore(Protocol):
    """Puerto de persistencia: una llamada representa un único bulk insert."""

    def bulk_insert(self, rows: list[dict[str, Any]]) -> None: ...


class SupabaseTelemetryStore:
    """Inserta un lote mediante la API REST de Supabase en una sola petición."""

    def bulk_insert(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not supabase_url or not service_key:
            raise RuntimeError("Supabase telemetry storage is not configured")

        request = UrlRequest(
            f"{supabase_url}/rest/v1/telemetry_events",
            data=json.dumps(rows).encode("utf-8"),
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                if response.status not in {200, 201, 204}:
                    raise RuntimeError("Supabase rejected telemetry bulk insert")
        except (HTTPError, URLError) as exc:
            raise RuntimeError("Supabase telemetry bulk insert failed") from exc


storage: TelemetryStore = SupabaseTelemetryStore()


def event_to_row(event: TelemetryEvent) -> dict[str, Any]:
    """Mapea el envelope al contrato fijo de ocho columnas del proyecto."""

    error_events = {"frontend_error_captured", "backend_error_captured"}
    warning_events = {"login_failed", "permission_denied", "direct_stock_edit_rejected"}
    level = (
        "error"
        if event.event_type in error_events
        else "warn"
        if event.event_type in warning_events
        else "info"
    )
    numeric_keys = (
        "duration_ms",
        "lcp_ms",
        "quantity",
        "available_quantity",
        "variance_percent",
        "result_count",
    )
    value = next(
        (
            float(event.properties[key])
            for key in numeric_keys
            if key in event.properties
            and isinstance(event.properties[key], (int, float))
            and not isinstance(event.properties[key], bool)
        ),
        None,
    )
    return {
        "id": str(event.eventId),
        "timestamp": event.timestamp.isoformat().replace("+00:00", "Z"),
        "service": "backoffice",
        "event_type": event.event_type,
        "level": level,
        "value": value,
        "message": event.event_type.replace("_", " "),
        "tags": event.properties,
    }


@router.post("/events")
def collect_events(payload: dict[str, Any]) -> dict[str, int]:
    """Valida por evento y persiste los válidos sin cancelar un lote mixto."""

    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        raise HTTPException(status_code=422, detail="events must be an array")

    valid_events: list[TelemetryEvent] = []
    rejected = 0
    for raw_event in raw_events:
        try:
            valid_events.append(TelemetryEvent.model_validate(raw_event))
        except ValidationError:
            rejected += 1

    rows = [event_to_row(event) for event in valid_events]
    if rows:
        try:
            storage.bulk_insert(rows)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail="Telemetry storage is unavailable") from exc

    event_types = [event.event_type for event in valid_events]
    logger.info(
        "telemetry_events_received count=%d stored=%d rejected=%d event_types=%s",
        len(raw_events),
        len(rows),
        rejected,
        ",".join(event_types),
    )
    return {"received": len(raw_events), "stored": len(rows), "rejected": rejected}
