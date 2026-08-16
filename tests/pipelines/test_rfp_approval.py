from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from data.pipelines.rfp_intake.approval import (
    ApprovalWorkflowRuntime,
    detect_conflicts,
    generate_final_document,
)
from data.pipelines.rfp_intake.approval_models import ApprovalDecisionRequest


def _ticket(*, conflict: str | None = None) -> dict[str, Any]:
    selection = (
        "Selección para 5 roles. Cotización EUR. Garantía de satisfacción de 90 días. "
        "El plazo será de al menos 15 días laborables."
    )
    training = (
        "Capacitación para 40 participantes. Cotización EUR. "
        "Garantía de satisfacción de 90 días."
    )
    if conflict == "currency":
        selection = selection.replace("EUR", "USD")
    if conflict == "schedule":
        training += " La capacitación comienza el día 5."
    return {
        "ticket_id": "ticket-vantex",
        "status": "waiting_for_approval",
        "metadata": {"client_name": "Vantex Retail Group, S.A.", "currency": "EUR"},
        "sections": [
            {
                "department_id": "seleccion",
                "department_name": "Talent Selection Operations",
                "contact": "Javier Almeida",
                "draft_content": selection,
                "approval_status": "pending",
                "approval_iteration": 0,
            },
            {
                "department_id": "capacitacion",
                "department_name": "Corporate Training",
                "contact": "Elena Vargas",
                "draft_content": training,
                "approval_status": "pending",
                "approval_iteration": 0,
            },
        ],
    }


@pytest.fixture
def runtime(tmp_path: Path):
    value = ApprovalWorkflowRuntime(tmp_path / "approval-checkpoints.sqlite3")
    yield value
    value.close()


def test_interrupt_is_persistent_and_resume_does_not_restart(tmp_path: Path) -> None:
    checkpoint = tmp_path / "durable.sqlite3"
    ticket = _ticket()
    first_runtime = ApprovalWorkflowRuntime(checkpoint)
    started = first_runtime.start_branch(ticket, ticket["sections"][0])
    first_runtime.close()

    assert started.interrupted is True
    assert started.interrupt is not None
    assert started.interrupt["approver"] == "Javier Almeida"

    resumed_runtime = ApprovalWorkflowRuntime(checkpoint)
    resumed = resumed_runtime.resume_branch(
        ticket["ticket_id"],
        "seleccion",
        ApprovalDecisionRequest(decision="approve"),
    )
    resumed_runtime.close()

    assert resumed.interrupted is False
    assert resumed.approval_status == "approved"
    assert [event.agent for event in resumed.trace].count("approval-preparer") == 1
    assert resumed.thread_id == "rfp-ticket-vantex:seleccion"


def test_department_b_can_finish_while_department_a_is_interrupted(
    runtime: ApprovalWorkflowRuntime,
) -> None:
    ticket = _ticket()
    selection = runtime.start_branch(ticket, ticket["sections"][0])
    runtime.start_branch(ticket, ticket["sections"][1])

    training = runtime.resume_branch(
        ticket["ticket_id"],
        "capacitacion",
        ApprovalDecisionRequest(decision="approve"),
    )
    still_waiting = runtime.branch_state(ticket["ticket_id"], "seleccion")

    assert training.approval_status == "approved"
    assert training.interrupted is False
    assert selection.thread_id != training.thread_id
    assert still_waiting.interrupted is True
    assert still_waiting.approval_status == "pending"


def test_iteration_limit_rejects_an_unresolved_branch(runtime: ApprovalWorkflowRuntime) -> None:
    ticket = _ticket()
    runtime.start_branch(ticket, ticket["sections"][0])

    result = None
    for iteration in range(1, 4):
        result = runtime.resume_branch(
            ticket["ticket_id"],
            "seleccion",
            ApprovalDecisionRequest(decision="request_changes", feedback=f"Revisión humana {iteration}."),
        )

    assert result is not None
    assert result.approval_status == "rejected"
    assert result.approval_iteration == 3
    assert result.interrupted is False
    assert "Límite de revisiones" in (result.feedback or "")


def test_fixed_arbitrator_overrides_approval_until_currency_is_repaired(
    runtime: ApprovalWorkflowRuntime,
) -> None:
    ticket = _ticket(conflict="currency")
    started = runtime.start_branch(ticket, ticket["sections"][0])

    assert [item.trigger_id for item in started.conflicts] == ["currency-mismatch"]
    assert started.conflicts[0].arbiter == "Marcos Ibáñez"

    overridden = runtime.resume_branch(
        ticket["ticket_id"],
        "seleccion",
        ApprovalDecisionRequest(decision="approve"),
    )
    assert overridden.approval_status == "pending"
    assert overridden.interrupted is True
    assert "EUR" in overridden.draft_content
    assert "USD" not in overridden.draft_content

    approved = runtime.resume_branch(
        ticket["ticket_id"],
        "seleccion",
        ApprovalDecisionRequest(decision="approve"),
    )
    assert approved.approval_status == "approved"


def test_context_schedule_trigger_is_structured_and_uses_fixed_arbiter() -> None:
    ticket = _ticket(conflict="schedule")

    findings = detect_conflicts(ticket["sections"], "EUR")

    schedule = next(item for item in findings if item.trigger_id == "ttc-vs-training-window")
    assert schedule.departments == ["seleccion", "capacitacion"]
    assert schedule.arbiter == "Marcos Ibáñez"
    assert "día 15" in schedule.resolution


def test_final_document_requires_every_approval(tmp_path: Path) -> None:
    ticket = _ticket()
    ticket["sections"][0]["approval_status"] = "approved"

    with pytest.raises(ValueError, match="todos los departamentos"):
        generate_final_document(ticket, tmp_path)

    ticket["sections"][1]["approval_status"] = "approved"
    document = generate_final_document(ticket, tmp_path)

    assert document.sections == ["seleccion", "capacitacion"]
    assert document.currency == "EUR"
    assert Path(document.file_path).read_text(encoding="utf-8") == document.content
