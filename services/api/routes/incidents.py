"""API autenticada del gestor centralizado y analizador de incidentes."""

from threading import Lock

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from nexova_shared.incident_analysis import (
    IncidentAnalysis,
    IncidentAnalysisError,
    analysis_to_csv,
    analyze_csv_bytes,
)
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

_analysis_lock = Lock()
_last_analysis: IncidentAnalysis | None = None


def _validate_filter(field: str, value: str | None, allowed: tuple[str, ...]) -> None:
    if value is not None and value not in allowed:
        raise HTTPException(
            status_code=400,
            detail={"field": field, "message": f"Valor no permitido para {field}"},
        )


@router.post("/analyze")
async def analyze_incidents_file(
    file: UploadFile = File(...),
) -> dict[str, object]:
    global _last_analysis

    filename = file.filename or "incidents.csv"
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="El archivo debe tener extensión .csv")
    try:
        content = await file.read()
    finally:
        await file.close()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="El archivo supera el límite de 10 MB",
        )
    try:
        analysis = analyze_csv_bytes(content, source_file=filename)
    except IncidentAnalysisError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with _analysis_lock:
        _last_analysis = analysis
    return analysis.as_dict()


@router.get("/results/export")
def export_incident_analysis() -> Response:
    with _analysis_lock:
        analysis = _last_analysis
    if analysis is None:
        raise HTTPException(status_code=404, detail="Todavía no hay un análisis para exportar")
    return Response(
        content=analysis_to_csv(analysis),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="results.csv"'},
    )


@router.get("/results/latest")
def read_latest_incident_analysis() -> dict[str, object]:
    """Permite recuperar el último resumen agregado tras recargar el panel."""

    with _analysis_lock:
        analysis = _last_analysis
    if analysis is None:
        raise HTTPException(status_code=404, detail="Todavía no hay un análisis disponible")
    return analysis.as_dict()


def reset_last_analysis() -> None:
    """Aísla el estado en memoria entre pruebas."""
    global _last_analysis
    with _analysis_lock:
        _last_analysis = None


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
