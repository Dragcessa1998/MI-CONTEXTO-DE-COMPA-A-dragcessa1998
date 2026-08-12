"""Tools read-only del agente sobre servicios operativos existentes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from incident_service import get_incident


INCIDENT_TOOL_TIMEOUT_SECONDS = 4.0


class IncidentLookupInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_id: int = Field(gt=0)


class IncidentLookupResult(BaseModel):
    ticket_id: int
    found: bool
    status: Literal["open", "in_progress", "resolved", "discarded"] | None = None
    category: str | None = None
    origin: str | None = None
    branch: str | None = None
    title: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    error: Literal["not_found", "timeout", "unavailable"] | None = None


def lookup_incident(
    request: IncidentLookupInput,
    *,
    timeout_seconds: float = INCIDENT_TOOL_TIMEOUT_SECONDS,
) -> IncidentLookupResult:
    """Consulta un ticket real en la capa existente; nunca escribe ni simula datos."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds debe ser positivo")
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="incident-read")
    future = executor.submit(get_incident, request.ticket_id)
    try:
        incident = future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        future.cancel()
        return IncidentLookupResult(
            ticket_id=request.ticket_id,
            found=False,
            error="timeout",
        )
    except Exception:
        return IncidentLookupResult(
            ticket_id=request.ticket_id,
            found=False,
            error="unavailable",
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if incident is None:
        return IncidentLookupResult(
            ticket_id=request.ticket_id,
            found=False,
            error="not_found",
        )
    return IncidentLookupResult(
        ticket_id=incident.id,
        found=True,
        status=incident.status,
        category=incident.category,
        origin=incident.origin,
        branch=incident.branch,
        title=incident.title,
        created_at=incident.created_at,
        updated_at=incident.updated_at,
    )
