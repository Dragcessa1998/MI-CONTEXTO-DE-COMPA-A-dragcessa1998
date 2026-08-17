"""Acceptance evidence for Nexova's proposal → decision → consolidation flow."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent.memory import (
    MemoryCoordinator,
    classify_memory_decision,
    evaluate_memory_candidate,
)
from agent.memory_store import SQLiteMemoryStore


def _answer(question: str) -> dict[str, object]:
    return {"run_id": "agent-run", "answer": f"Respuesta operativa: {question}"}


def _coordinator(tmp_path: Path) -> tuple[MemoryCoordinator, SQLiteMemoryStore]:
    store = SQLiteMemoryStore(tmp_path / "memory.sqlite3")
    return MemoryCoordinator(store), store


def test_approved_cycle_is_recalled_in_a_fresh_conversation(tmp_path: Path) -> None:
    coordinator, store = _coordinator(tmp_path)
    correction = (
        "Actually payroll tickets for retail clients now resolve in 24 hours, "
        "not 48 like the old SLA said."
    )

    proposed = coordinator.handle_turn(
        conversation_id="session-a",
        user_id=7,
        message=correction,
        answer_factory=_answer,
    )
    assert proposed.memory_proposal is not None
    assert proposed.memory_proposal.kind == "escalation_procedure"
    assert store.read_all() == []

    approved = coordinator.handle_turn(
        conversation_id="session-a",
        user_id=7,
        message="Sí, recuérdalo.",
        answer_factory=_answer,
    )
    assert approved.memory_decision == "approved"
    assert len(store.read_all()) == 1

    recalled = coordinator.handle_turn(
        conversation_id="fresh-session",
        user_id=7,
        message="¿Cuál es el SLA de tickets de payroll para clientes retail?",
        answer_factory=_answer,
    )
    assert recalled.recalled_memories[0].content == correction
    assert "24 hours" in recalled.answer
    audit = store.audit_log("session-a")
    assert audit[0].status == "approved"
    assert audit[0].source_message == correction
    assert audit[0].decision_label == "approve"
    assert audit[0].decided_at is not None


def test_rejected_cycle_keeps_memory_unchanged_but_preserves_audit(tmp_path: Path) -> None:
    coordinator, store = _coordinator(tmp_path)
    initial = len(store.read_all())
    proposed = coordinator.handle_turn(
        conversation_id="session-reject",
        user_id=9,
        message=(
            "That finance client always wants email confirmation before we close "
            "a support ticket."
        ),
        answer_factory=_answer,
    )
    assert proposed.memory_proposal is not None

    rejected = coordinator.handle_turn(
        conversation_id="session-reject",
        user_id=9,
        message="No lo recuerdes.",
        answer_factory=_answer,
    )
    assert rejected.memory_decision == "rejected"
    assert len(store.read_all()) == initial
    assert store.audit_log("session-reject")[0].status == "rejected"


def test_ambiguous_topic_change_rejects_by_default_and_continues(tmp_path: Path) -> None:
    coordinator, store = _coordinator(tmp_path)
    coordinator.handle_turn(
        conversation_id="session-ambiguous",
        user_id=4,
        message=(
            "Tickets flagged urgent from premium clients should now go straight "
            "to a senior support agent."
        ),
        answer_factory=_answer,
    )
    result = coordinator.handle_turn(
        conversation_id="session-ambiguous",
        user_id=4,
        message="¿Cuántos tickets abiertos hay ahora?",
        answer_factory=_answer,
    )
    assert result.memory_decision == "rejected_ambiguous"
    assert "Respuesta operativa" in result.answer
    assert store.read_all() == []
    assert store.audit_log("session-ambiguous")[0].status == "rejected_ambiguous"


def test_forbidden_and_one_off_data_never_generate_proposals(tmp_path: Path) -> None:
    coordinator, store = _coordinator(tmp_path)
    messages = (
        "Actually candidate Ana's interview rating should now be 9 out of 10.",
        "The active headhunting salary negotiation changed to 90,000 euros.",
        "Actually ticket 418 should now go to Laura, but only this time.",
    )
    for index, message in enumerate(messages):
        result = coordinator.handle_turn(
            conversation_id=f"forbidden-{index}",
            user_id=3,
            message=message,
            answer_factory=_answer,
        )
        assert result.memory_proposal is None
    assert store.read_all() == []
    assert store.audit_log() == []


def test_three_non_memorable_examples_are_dismissed() -> None:
    assert evaluate_memory_candidate("How many open tickets are there right now?") is None
    assert evaluate_memory_candidate("Perfect, thanks for the explanation.") is None
    assert evaluate_memory_candidate("Summarize this ticket in two lines for Laura's report.") is None


def test_decision_classifier_is_explicit_not_substring_based() -> None:
    assert classify_memory_decision("Sí, recuérdalo.").label == "approve"
    assert classify_memory_decision("No lo recuerdes.").label == "reject"
    edited = classify_memory_decision(
        "Cámbialo por: Actually payroll tickets now use a 24 hour support SLA."
    )
    assert edited.label == "edit"
    assert classify_memory_decision("Sí, quizá otro día").label == "ambiguous"
    assert classify_memory_decision("No sé, cuéntame más").label == "ambiguous"


def test_explicit_decision_and_new_question_continue_in_same_turn(tmp_path: Path) -> None:
    coordinator, store = _coordinator(tmp_path)
    coordinator.handle_turn(
        conversation_id="approve-and-continue",
        user_id=6,
        message=(
            "Actually payroll tickets for retail clients now resolve in 24 hours, "
            "not 48 like the old SLA said."
        ),
        answer_factory=_answer,
    )
    result = coordinator.handle_turn(
        conversation_id="approve-and-continue",
        user_id=6,
        message="Sí, recuérdalo. ¿Cuál es el SLA de payroll para retail?",
        answer_factory=_answer,
    )
    assert result.memory_decision == "approved"
    assert result.answer.startswith("Memoria aprobada")
    assert "Respuesta operativa" in result.answer
    assert "24 hours" in result.answer
    assert len(store.read_all()) == 1


def test_consolidation_expires_pending_and_bounds_audit(tmp_path: Path) -> None:
    current = ["2026-08-15T08:00:00+00:00"]
    store = SQLiteMemoryStore(tmp_path / "bounded.sqlite3", clock=lambda: current[0])
    first = store.propose(
        conversation_id="expired",
        proposed_by=1,
        memory_key="incident_pattern:general-general",
        kind="incident_pattern",
        content="Support tickets usually escalate to a senior agent after the SLA.",
        reason="Repeatable helpdesk pattern.",
        source_message="Support tickets usually escalate to a senior agent after the SLA.",
    )
    current[0] = "2026-08-17T10:00:00+00:00"
    result = store.consolidate(pending_ttl_hours=24)
    assert result["expired_proposals"] == 1
    assert store.audit_log("expired")[0].status == "expired"

    for index in range(3):
        proposal = store.propose(
            conversation_id=f"audit-{index}",
            proposed_by=1,
            memory_key=f"incident_pattern:general-{index}",
            kind="incident_pattern",
            content=f"Support tickets usually use repeatable queue {index}.",
            reason="Repeatable helpdesk pattern.",
            source_message=f"Support tickets usually use repeatable queue {index}.",
        )
        store.resolve(
            proposal.proposal_id,
            status="rejected",
            decision_label="reject",
            decision_message="No lo recuerdes.",
        )
    bounded = store.consolidate(max_audit_rows=2, audit_retention_days=730)
    assert bounded["removed_audits"] == 2
    assert len(store.audit_log()) == 2


def test_api_exposes_proposal_decision_recall_and_owner_audit(
    client: TestClient, monkeypatch,
) -> None:
    import routes.agent as agent_routes

    monkeypatch.setattr(
        agent_routes,
        "run_agent",
        lambda question: {"run_id": "api-run", "answer": f"Base: {question}"},
    )
    conversation = "api-memory-cycle"
    proposed = client.post(
        "/agent/query",
        json={
            "conversation_id": conversation,
            "question": (
                "Actually payroll tickets for retail clients now resolve in 24 hours, "
                "not 48 like the old SLA said."
            ),
        },
    )
    assert proposed.status_code == 200
    assert proposed.json()["memory_proposal"]["status"] == "pending"

    approved = client.post(
        "/agent/query",
        json={"conversation_id": conversation, "question": "Sí, recuérdalo."},
    )
    assert approved.json()["memory_decision"] == "approved"

    recalled = client.post(
        "/agent/query",
        json={
            "conversation_id": "api-future-session",
            "question": "¿Qué SLA aplica a payroll para retail?",
        },
    )
    assert "24 hours" in recalled.json()["recalled_memories"][0]
    audit = client.get(f"/agent/memory/audit?conversation_id={conversation}")
    assert audit.status_code == 200
    assert audit.json()[0]["status"] == "approved"
