from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from data.pipelines.rfp_intake.models import IntakeResult
from data.pipelines.rfp_intake.approval import ApprovalWorkflowRuntime
from data.pipelines.rfp_intake.approval_models import ApprovalBranchResult, FinalDocument
from data.pipelines.rfp_intake.proposal_models import ProposalGenerationResult
from main import app
from routes import rfps as rfp_routes
from routes.rfp_events import rfp_event_broker


DEFAULT_SAMPLES = (
    Path(__file__).resolve().parents[4]
    / "course-syllabus/content/contexts/09-agentic-workflows/rfp-requests/nexova"
)
SAMPLES = Path(os.getenv("RFP_TEST_SAMPLES_DIR", DEFAULT_SAMPLES))


class MemoryRfpRepository:
    def __init__(self) -> None:
        self.tickets: dict[str, dict[str, Any]] = {}
        self.final_documents: dict[str, dict[str, Any]] = {}

    def create_ticket(self, raw_pdf_path: str) -> dict[str, Any]:
        ticket_id = str(uuid4())
        ticket = {
            "ticket_id": ticket_id,
            "rfp_id": str(uuid4()),
            "status": "analyzing",
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
            "status": "intake_complete" if result.classification.is_rfp else "discarded",
            "markdown_path": result.markdown_path,
            "classification_reason": result.classification.reason,
            "sales_summary": result.sales_summary,
            "metadata": result.metadata.model_dump(mode="json") if result.metadata else None,
            "sections": [section.model_dump(mode="json") for section in result.sections],
        })

    def start_drafting(self, ticket_id: str) -> dict[str, Any]:
        ticket = self.tickets[ticket_id]
        rejected = any(section.get("approval_status") == "rejected" for section in ticket["sections"])
        if ticket["status"] not in {"intake_complete", "under_evaluation", "needs_human_review"} and not (
            ticket["status"] == "waiting_for_approval" and rejected
        ):
            raise ValueError("El ticket no está listo para generar una propuesta")
        ticket["status"] = "drafting"
        ticket["processing_error"] = None
        return deepcopy(ticket)

    def mark_under_evaluation(self, ticket_id: str) -> None:
        self.tickets[ticket_id]["status"] = "under_evaluation"

    def save_generation(self, ticket_id: str, result: ProposalGenerationResult) -> None:
        ticket = self.tickets[ticket_id]
        generated = {section.department_id: section for section in result.sections}
        for section in ticket["sections"]:
            output = generated[section["department_id"]]
            section.update({
                "draft_content": output.draft_content,
                "evaluation_results": [
                    item.model_dump(by_alias=True, mode="json") for item in output.evaluation_results
                ],
                "generation_iteration": output.generation_iteration,
                "approval_status": None,
                "approval_iteration": 0,
                "approval_feedback": None,
                "approver": None,
                "approved_at": None,
            })
        ticket["status"] = result.status
        ticket["processing_error"] = None

    def start_approvals(self, ticket_id: str) -> dict[str, Any]:
        ticket = self.tickets[ticket_id]
        if ticket["status"] not in {"under_evaluation", "needs_human_review"}:
            raise ValueError("El ticket no está listo para aprobación")
        if not ticket["sections"] or any(not section.get("draft_content") for section in ticket["sections"]):
            raise ValueError("Todas las secciones deben conservar un borrador antes de la aprobación")
        ticket["status"] = "waiting_for_approval"
        for section in ticket["sections"]:
            section.update({
                "approval_status": "pending",
                "approval_iteration": 0,
                "approval_feedback": None,
                "approver": section["contact"],
                "approved_at": None,
            })
        return deepcopy(ticket)

    def save_approval_branch(self, result: ApprovalBranchResult) -> None:
        ticket = self.tickets[result.ticket_id]
        section = next(item for item in ticket["sections"] if item["department_id"] == result.department_id)
        section.update({
            "draft_content": result.draft_content,
            "approval_status": result.approval_status,
            "approval_iteration": result.approval_iteration,
            "approval_feedback": result.feedback,
            "approver": section["contact"],
            "approved_at": "2026-08-17T10:00:00+00:00" if result.approval_status == "approved" else None,
        })

    def save_final_document(self, document: FinalDocument) -> None:
        self.final_documents[document.ticket_id] = document.model_dump(mode="json")
        self.tickets[document.ticket_id]["status"] = "done"

    def get_final_document(self, ticket_id: str) -> dict[str, Any] | None:
        document = self.final_documents.get(ticket_id)
        return deepcopy(document) if document else None

    def mark_failed(self, ticket_id: str) -> None:
        self.tickets[ticket_id]["processing_error"] = "processing_failed"


@pytest.fixture
def rfp_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repository = MemoryRfpRepository()
    runtime = ApprovalWorkflowRuntime(tmp_path / "checkpoints.sqlite3")
    app.dependency_overrides[rfp_routes.repository_dependency] = lambda: repository
    app.dependency_overrides[rfp_routes.approval_runtime_dependency] = lambda: runtime
    monkeypatch.setattr(rfp_routes, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(rfp_routes, "FINAL_DIR", tmp_path / "final")
    yield repository
    app.dependency_overrides.pop(rfp_routes.repository_dependency, None)
    app.dependency_overrides.pop(rfp_routes.approval_runtime_dependency, None)
    runtime.close()


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
    subscription = rfp_event_broker.subscribe(0)
    try:
        assert len(subscription.replay) == 1
        assert subscription.replay[0].data == {
            "ticket_id": ticket_id,
            "rfp_id": rfp_repository.tickets[ticket_id]["rfp_id"],
            "status": "analyzing",
            "created_at": "2026-08-12T10:00:00+00:00",
        }
    finally:
        rfp_event_broker.unsubscribe(subscription)

    detail = client.get(f"/api/rfps/{ticket_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "intake_complete"
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
    assert ticket["status"] == "discarded"
    assert ticket["sections"] == []
    assert "pitch de proveedor" in ticket["classification_reason"]


def test_intake_ticket_generates_and_evaluates_department_sections(
    client: TestClient,
    rfp_repository: MemoryRfpRepository,
) -> None:
    upload = client.post(
        "/api/rfps",
        files={"file": ("vantex.pdf", _sample("CONTEXT-nexova-request-1.pdf"), "application/pdf")},
    )
    ticket_id = upload.json()["ticket_id"]

    response = client.post(f"/api/rfps/{ticket_id}/draft")

    assert response.status_code == 202
    assert response.json()["status"] == "drafting"
    ticket = client.get(f"/api/rfps/{ticket_id}").json()
    assert ticket["status"] == "under_evaluation"
    assert len(ticket["sections"]) == 2
    for section in ticket["sections"]:
        assert section["draft_content"]
        assert section["generation_iteration"] == 1
        assert section["evaluation_results"][-1]["overall_pass"] is True
        assert set(section["evaluation_results"][-1]) >= {
            "readability", "relevance", "compliance", "actionable_feedback"
        }


def test_drafting_requires_completed_intake(
    client: TestClient,
    rfp_repository: MemoryRfpRepository,
) -> None:
    ticket = rfp_repository.create_ticket("/tmp/still-analyzing.pdf")

    response = client.post(f"/api/rfps/{ticket['ticket_id']}/draft")

    assert response.status_code == 409


def test_departments_approve_independently_and_final_document_is_automatic(
    client: TestClient,
    rfp_repository: MemoryRfpRepository,
) -> None:
    upload = client.post(
        "/api/rfps",
        files={"file": ("vantex.pdf", _sample("CONTEXT-nexova-request-1.pdf"), "application/pdf")},
    )
    ticket_id = upload.json()["ticket_id"]
    assert client.post(f"/api/rfps/{ticket_id}/draft").status_code == 202

    started = client.post(f"/api/rfps/{ticket_id}/approvals/start")

    assert started.status_code == 200
    assert started.json()["status"] == "waiting_for_approval"
    assert {item["thread_id"] for item in started.json()["branches"]} == {
        f"rfp-{ticket_id}:seleccion",
        f"rfp-{ticket_id}:capacitacion",
    }
    assert all(item["interrupted"] for item in started.json()["branches"])

    training = client.post(
        f"/api/rfps/{ticket_id}/approvals/capacitacion/resume",
        json={"decision": "approve"},
    )
    assert training.status_code == 200
    assert training.json()["status"] == "waiting_for_approval"
    ticket = client.get(f"/api/rfps/{ticket_id}").json()
    statuses = {item["department_id"]: item["approval_status"] for item in ticket["sections"]}
    assert statuses == {"seleccion": "pending", "capacitacion": "approved"}
    assert client.get(f"/api/rfps/{ticket_id}/final").status_code == 409

    selection = client.post(
        f"/api/rfps/{ticket_id}/approvals/seleccion/resume",
        json={"decision": "approve"},
    )
    assert selection.status_code == 200
    assert selection.json()["status"] == "done"
    assert selection.json()["final_document"]["currency"] == "EUR"
    final = client.get(f"/api/rfps/{ticket_id}/final")
    assert final.status_code == 200
    assert "Vantex Retail Group" in final.json()["content"]
    assert Path(final.json()["file_path"]).is_file()

    trace = client.get(f"/api/rfps/{ticket_id}/approvals/trace").json()
    assert len(trace["branches"]) == 2
    assert all(
        set(event) == {"agent", "input", "output", "timestamp"}
        for branch in trace["branches"]
        for event in branch["trace"]
    )


def test_human_decision_schema_requires_feedback_for_changes(
    client: TestClient,
    rfp_repository: MemoryRfpRepository,
) -> None:
    response = client.post(
        "/api/rfps/nonexistent/approvals/seleccion/resume",
        json={"decision": "request_changes"},
    )

    assert response.status_code == 422


def test_rejected_branch_can_reenter_part_two_generation(
    client: TestClient,
    rfp_repository: MemoryRfpRepository,
) -> None:
    upload = client.post(
        "/api/rfps",
        files={"file": ("vantex.pdf", _sample("CONTEXT-nexova-request-1.pdf"), "application/pdf")},
    )
    ticket_id = upload.json()["ticket_id"]
    client.post(f"/api/rfps/{ticket_id}/draft")
    client.post(f"/api/rfps/{ticket_id}/approvals/start")
    rejected = client.post(
        f"/api/rfps/{ticket_id}/approvals/seleccion/resume",
        json={"decision": "reject", "feedback": "Rehacer el enfoque comercial."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["branch"]["approval_status"] == "rejected"

    regenerated = client.post(f"/api/rfps/{ticket_id}/draft")

    assert regenerated.status_code == 202
    detail = client.get(f"/api/rfps/{ticket_id}").json()
    assert detail["status"] == "under_evaluation"
    assert all(section["approval_status"] is None for section in detail["sections"])
