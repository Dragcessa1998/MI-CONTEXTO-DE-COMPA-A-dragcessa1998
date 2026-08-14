"""Persistencia y agregaciones de incidentes sobre TinyDB."""

from collections import Counter
from datetime import datetime, timezone

from nexova_shared.incidents import (
    INCIDENT_BRANCHES,
    INCIDENT_CATEGORIES,
    INCIDENT_ORIGINS,
    INCIDENT_STATUSES,
)
from tinydb.table import Document

from database import incidents_table
from incident_models import IncidentCreate, IncidentOut, IncidentSummary
from ttl_cache import TTLCache


# The aggregate contains operational totals only and is identical for every
# authorized user, so a single shared key cannot leak session-specific data.
incident_summary_cache: TTLCache[str, IncidentSummary] = TTLCache(ttl_seconds=15)


def clear_incident_summary_cache() -> None:
    incident_summary_cache.clear()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_out(record: Document | dict) -> IncidentOut:
    return IncidentOut.model_validate(dict(record))


def create_incident(payload: IncidentCreate) -> IncidentOut:
    now = _now_iso()
    record = payload.model_dump()
    record.update({"created_at": now, "updated_at": now})
    doc_id = incidents_table().insert(record)
    record["id"] = doc_id
    incidents_table().update({"id": doc_id}, doc_ids=[doc_id])
    clear_incident_summary_cache()
    return _to_out(record)


def list_incidents(filters: dict[str, str | None]) -> list[IncidentOut]:
    records = incidents_table().all()
    for field, expected in filters.items():
        if expected is not None:
            records = [record for record in records if record.get(field) == expected]
    return [_to_out(record) for record in records]


def get_incident(incident_id: int) -> IncidentOut | None:
    record = incidents_table().get(doc_id=incident_id)
    return _to_out(record) if record is not None else None


def set_incident_status(incident_id: int, status: str) -> IncidentOut | None:
    table = incidents_table()
    if table.get(doc_id=incident_id) is None:
        return None
    table.update({"status": status, "updated_at": _now_iso()}, doc_ids=[incident_id])
    clear_incident_summary_cache()
    return _to_out(table.get(doc_id=incident_id))


def incident_summary() -> IncidentSummary:
    def load() -> IncidentSummary:
        records = incidents_table().all()

        def complete_counts(field: str, allowed: tuple[str, ...]) -> dict[str, int]:
            counts = Counter(str(record.get(field)) for record in records)
            return {value: counts[value] for value in allowed}

        return IncidentSummary(
            total=len(records),
            by_status=complete_counts("status", INCIDENT_STATUSES),
            by_category=complete_counts("category", INCIDENT_CATEGORIES),
            by_origin=complete_counts("origin", INCIDENT_ORIGINS),
            by_branch=complete_counts("branch", INCIDENT_BRANCHES),
        )

    return incident_summary_cache.get_or_set("company-summary", load)
