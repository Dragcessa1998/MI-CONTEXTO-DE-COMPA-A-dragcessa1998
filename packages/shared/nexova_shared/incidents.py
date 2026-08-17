"""Reglas de incidentes Nexova compartidas por el seeder y la API.

El validador histórico nunca conserva ni devuelve el email de cliente: solo
comunica códigos de error agregables para no filtrar datos sensibles.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone


INCIDENT_STATUSES = ("open", "in_progress", "resolved", "discarded")
INCIDENT_ORIGINS = ("customer", "branch", "internal")
INCIDENT_BRANCHES = ("central", "valencia_operations", "miami_office", "remote")
INCIDENT_CATEGORIES = (
    "technical_failure",
    "process_error",
    "client_complaint",
    "candidate_issue",
    "staff_issue",
    "sla_breach",
    "data_quality",
    "other",
)

STATUS_MAP = {"OPEN": "open", "CLOSED": "resolved", "DISCARDED": "discarded"}
CATEGORY_MAP = {
    "TECHNICAL": "technical_failure",
    "BILLING": "process_error",
    "ACCESS": "technical_failure",
    "HR_QUERY": "process_error",
    "COMPLAINT": "client_complaint",
}

VALID_TRANSITIONS = {
    "open": frozenset(("in_progress", "discarded")),
    "in_progress": frozenset(("resolved", "discarded")),
    "resolved": frozenset(),
    "discarded": frozenset(),
}

ERROR_LABELS = {
    "invalid_ticket_id": "ticket_id ausente o inválido",
    "invalid_date": "fecha ausente o inválida",
    "missing_client_company": "client_company ausente",
    "invalid_category": "categoría ausente o inválida",
    "invalid_description": "descripción ausente o menor de 5 caracteres",
    "invalid_agent_id": "agent_id ausente o inválido",
    "invalid_status": "estado ausente o inválido",
    "invalid_email": "email ausente o inválido",
    "closed_without_score": "ticket cerrado sin satisfaction_score",
    "invalid_score": "satisfaction_score fuera de 1–5",
}

_TICKET_RE = re.compile(r"^NXV-\d{6}$")
_AGENT_RE = re.compile(r"^AGT-\d{2}$")


@dataclass(frozen=True)
class HistoricalValidation:
    valid: bool
    errors: tuple[str, ...]


def validate_historical_row(row: Mapping[str, str | None]) -> HistoricalValidation:
    """Valida el CSV del analizador sin devolver PII ni texto del registro."""
    errors: list[str] = []
    ticket_id = (row.get("ticket_id") or "").strip()
    raw_date = (row.get("date") or "").strip()
    client_company = (row.get("client_company") or "").strip()
    category = (row.get("category") or "").strip()
    description = (row.get("description") or "").strip()
    agent_id = (row.get("agent_id") or "").strip()
    status = (row.get("status") or "").strip()
    customer_email = (row.get("customer_email") or "").strip()
    score_text = (row.get("satisfaction_score") or "").strip()

    if not _TICKET_RE.fullmatch(ticket_id):
        errors.append("invalid_ticket_id")
    try:
        datetime.strptime(raw_date, "%Y-%m-%d")
    except ValueError:
        errors.append("invalid_date")
    if not client_company:
        errors.append("missing_client_company")
    if category not in CATEGORY_MAP:
        errors.append("invalid_category")
    if len(description) < 5:
        errors.append("invalid_description")
    if not _AGENT_RE.fullmatch(agent_id):
        errors.append("invalid_agent_id")
    if status not in STATUS_MAP:
        errors.append("invalid_status")
    if "@" not in customer_email:
        errors.append("invalid_email")

    if status == "CLOSED" and not score_text:
        errors.append("closed_without_score")
    if score_text:
        try:
            score = int(score_text)
            if not 1 <= score <= 5:
                errors.append("invalid_score")
        except ValueError:
            errors.append("invalid_score")

    return HistoricalValidation(valid=not errors, errors=tuple(errors))


def transform_historical_row(row: Mapping[str, str | None]) -> dict[str, str]:
    """Transforma una fila ya validada al modelo del gestor, sin PII ni ticket_id."""
    validation = validate_historical_row(row)
    if not validation.valid:
        raise ValueError(", ".join(validation.errors))

    description = (row.get("description") or "").strip()
    created_at = datetime.strptime((row.get("date") or "").strip(), "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    ).isoformat()
    return {
        "title": description[:120].strip(),
        "description": description,
        "category": CATEGORY_MAP[(row.get("category") or "").strip()],
        "status": STATUS_MAP[(row.get("status") or "").strip()],
        "origin": "customer",
        "branch": "central",
        "created_at": created_at,
        "updated_at": created_at,
    }


def is_valid_transition(current_status: str, next_status: str) -> bool:
    return next_status in VALID_TRANSITIONS.get(current_status, frozenset())
