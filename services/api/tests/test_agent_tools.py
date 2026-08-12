from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from agent import tools
from agent.tools import INCIDENT_TOOL_TIMEOUT_SECONDS, IncidentLookupInput
from incident_models import IncidentCreate
from incident_service import create_incident


def test_lookup_contract_reads_existing_incident_service(monkeypatch) -> None:
    incident = SimpleNamespace(
        id=9,
        status="open",
        category="technical_failure",
        origin="internal",
        branch="central",
        title="Error de integración",
        created_at=datetime(2026, 8, 12, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 8, 12, 8, 5, tzinfo=UTC),
    )
    monkeypatch.setattr(tools, "get_incident", lambda incident_id: incident if incident_id == 9 else None)

    result = tools.lookup_incident(IncidentLookupInput(ticket_id=9))

    assert result.found is True
    assert result.status == "open"
    assert result.model_dump()["ticket_id"] == 9
    assert INCIDENT_TOOL_TIMEOUT_SECONDS == 4.0


def test_lookup_reports_missing_without_mutating(monkeypatch) -> None:
    monkeypatch.setattr(tools, "get_incident", lambda _incident_id: None)
    result = tools.lookup_incident(IncidentLookupInput(ticket_id=404))
    assert result.found is False and result.error == "not_found"


def test_lookup_reads_ticket_created_by_real_incident_service() -> None:
    created = create_incident(
        IncidentCreate(
            title="Demora en respuesta de soporte",
            description="El cliente reporta que el SLA de respuesta fue superado.",
            category="sla_breach",
            status="open",
            origin="customer",
            branch="miami_office",
        )
    )

    result = tools.lookup_incident(IncidentLookupInput(ticket_id=created.id))

    assert result.found is True
    assert result.status == "open"
    assert result.category == "sla_breach"
    assert result.branch == "miami_office"
