"""API autenticada del gestor centralizado de incidentes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from nexova_shared.incidents import (
    INCIDENT_BRANCHES,
    INCIDENT_CATEGORIES,
    INCIDENT_ORIGINS,
    INCIDENT_STATUSES,
    is_valid_transition,
)

from incident_models import IncidentCreate, IncidentOut, IncidentStatusUpdate, IncidentSummary
from incident_service import (
    create_incident,
    get_incident,
    incident_summary,
    list_incidents,
    set_incident_status,
)
from security import get_current_user


router = APIRouter(
    prefix="/api/incidents",
    tags=["incidents"],
    dependencies=[Depends(get_current_user)],
)


def _validate_filter(field: str, value: str | None, allowed: tuple[str, ...]) -> None:
    if value is not None and value not in allowed:
        raise HTTPException(
            status_code=400,
            detail={"field": field, "message": f"Valor no permitido para {field}"},
        )


@router.post("", status_code=201, response_model=IncidentOut)
def create(payload: IncidentCreate) -> IncidentOut:
    return create_incident(payload)


@router.get("", response_model=list[IncidentOut])
def read_incidents(
    status: str | None = Query(default=None),
    origin: str | None = Query(default=None),
    branch: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> list[IncidentOut]:
    _validate_filter("status", status, INCIDENT_STATUSES)
    _validate_filter("origin", origin, INCIDENT_ORIGINS)
    _validate_filter("branch", branch, INCIDENT_BRANCHES)
    _validate_filter("category", category, INCIDENT_CATEGORIES)
    return list_incidents(
        {"status": status, "origin": origin, "branch": branch, "category": category}
    )


@router.get("/summary", response_model=IncidentSummary)
def read_summary() -> IncidentSummary:
    return incident_summary()


@router.get("/{incident_id}", response_model=IncidentOut)
def read_incident(incident_id: int) -> IncidentOut:
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    return incident


@router.patch("/{incident_id}/status", response_model=IncidentOut)
def update_status(incident_id: int, payload: IncidentStatusUpdate) -> IncidentOut:
    incident = get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    if not is_valid_transition(incident.status, payload.status):
        raise HTTPException(
            status_code=400,
            detail={
                "field": "status",
                "message": f"Transición no permitida: {incident.status} → {payload.status}",
            },
        )
    updated = set_incident_status(incident_id, payload.status)
    if updated is None:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    return updated
