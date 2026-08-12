from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from shutil import copy2
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from data.pipelines.rfp_intake.models import IntakeResult
from main import app
from routes import rfps as rfp_routes


SAMPLES = Path(
    "/Users/franchescostabile/Desktop/tareas pendientes/course-syllabus/content/contexts/09-agentic-workflows/rfp-requests/nexova"
)


class MemoryRfpRepository:
    def __init__(self) -> None:
        self.tickets: dict[str, dict[str, Any]] = {}

    def create_ticket(self, raw_pdf_path: str) -> dict[str, Any]:
        ticket_id = str(uuid4())
        ticket = {
            "ticket_id": ticket_id,
            "rfp_id": str(uuid4()),
            "status": "analizando",
            "raw_pdf_path": raw_pdf_path,
            "markdown_path": None,
            "classification_reason": None,
            "sales_summary": None,
            "processing_error": None,
            "created_at": "2026-08-12T10:00:00+00:00",
            "updated_at": "2026-08-12T10:00:00+00:00",
            "metadata": None,
            "sections": [],
        }
        self.tickets[ticket_id] = ticket
        return deepcopy(ticket)

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        ticket = self.tickets.get(ticket_id)
        return deepcopy(ticket) if ticket else None

    def list_tickets(self) -> list[dict[str, Any]]:
        return [deepcopy(ticket) for ticket in self.tickets.values()]

    def save_result(self, ticket_id: str, result: IntakeResult) -> None:
        ticket = self.tickets[ticket_id]
        ticket.update({
            "status": "analisis_completo" if result.classification.is_rfp else "descartado",
            "markdown_path": result.markdown_path,
            "classification_reason": result.classification.reason,
            "sales_summary": result.sales_summary,
            "metadata": result.metadata.model_dump(mode="json") if result.metadata else None,
            "sections": [section.model_dump(mode="json") for section in result.sections],
        })

    def mark_failed(self, ticket_id: str) -> None:
        self.tickets[ticket_id]["processing_error"] = "processing_failed"


@pytest.fixture
def rfp_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository = MemoryRfpRepository()
    app.dependency_overrides[rfp_routes.repository_dependency] = lambda: repository
    monkeypatch.setattr(rfp_routes, "RAW_DIR", tmp_path / "raw")
    yield repository
    app.dependency_overrides.pop(rfp_routes.repository_dependency, None)


def _sample(name: str) -> bytes:
    source = SAMPLES / name
    if not source.is_file():
        pytest.skip("Los PDF oficiales de Nexova no están disponibles")
    return source.read_bytes()


def test_upload_returns_ticket_and_persists_full_analysis(
    client: TestClient,
    rfp_repository: MemoryRfpRepository,
) -> None:
    response = client.post(
        "/api/rfps",
        files={"file": ("vantex.pdf", _sample("CONTEXT-nexova-request-1.pdf"), "application/pdf")},
    )
    assert response.status_code == 202
    ticket_id = response.json()["ticket_id"]
    assert response.json()["status_url"] == f"/api/rfps/{ticket_id}"

    detail = client.get(f"/api/rfps/{ticket_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "analisis_completo"
    assert body["metadata"]["departments_needed"] == ["seleccion", "capacitacion"]
    assert {section["contact"] for section in body["sections"]} == {"Javier Almeida", "Elena Vargas"}
    assert Path(body["raw_pdf_path"]).is_file()


def test_invalid_pdf_is_rejected_before_ticket_creation(
    client: TestClient,
    rfp_repository: MemoryRfpRepository,
) -> None:
    response = client.post(
        "/api/rfps",
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert rfp_repository.tickets == {}


def test_invalid_business_document_becomes_discarded(
    client: TestClient,
    rfp_repository: MemoryRfpRepository,
) -> None:
    response = client.post(
        "/api/rfps",
        files={"file": ("vendor.pdf", _sample("CONTEXT-nexova-request-3.pdf"), "application/pdf")},
    )
    ticket = client.get(f"/api/rfps/{response.json()['ticket_id']}").json()
    assert ticket["status"] == "descartado"
    assert ticket["sections"] == []
    assert "pitch de proveedor" in ticket["classification_reason"]
