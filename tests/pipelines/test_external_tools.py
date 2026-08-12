from __future__ import annotations

from datetime import UTC, datetime

from agent import graph as support_graph
from agent.tools import IncidentLookupResult
from agent.trace_store import trace_store


def setup_function() -> None:
    trace_store.clear()


def _ticket_result(ticket_id: int = 42) -> IncidentLookupResult:
    return IncidentLookupResult(
        ticket_id=ticket_id,
        found=True,
        status="in_progress",
        category="sla_breach",
        origin="customer",
        branch="miami_office",
        title="Respuesta fuera del SLA",
        created_at=datetime(2026, 8, 11, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 8, 12, 9, 30, tzinfo=UTC),
    )


def test_ticket_question_routes_only_to_real_incident_tool(monkeypatch) -> None:
    monkeypatch.setattr(
        support_graph,
        "retrieve",
        lambda _question: (_ for _ in ()).throw(AssertionError("RAG must not run")),
    )
    monkeypatch.setattr(support_graph, "lookup_incident", lambda request: _ticket_result(request.ticket_id))

    result = support_graph.run_agent("¿En qué estado está el ticket 42?", run_id="tool-only")

    assert "in_progress" in result["answer"]
    assert [event["node"] for event in result["trace"]] == [
        "receive_question",
        "lookup_incident",
        "tool_answer",
    ]


def test_policy_question_routes_only_to_rag(monkeypatch) -> None:
    context = [{"source_document": "hiring-process-sla", "section": "SLA", "text": "Promedio."}]
    monkeypatch.setattr(support_graph, "retrieve", lambda _question: context)
    monkeypatch.setattr(support_graph, "generate_answer", lambda _question, _context: "El plazo se presenta como promedio.")
    monkeypatch.setattr(
        support_graph,
        "lookup_incident",
        lambda _request: (_ for _ in ()).throw(AssertionError("tool must not run")),
    )

    result = support_graph.run_agent("¿Cuál es el SLA de headhunting?", run_id="rag-only")

    assert result["answer"] == "El plazo se presenta como promedio."
    assert [event["node"] for event in result["trace"]] == [
        "receive_question",
        "retrieve_context",
        "generate_response",
    ]


def test_tool_failure_has_honest_fallback(monkeypatch) -> None:
    monkeypatch.setattr(
        support_graph,
        "lookup_incident",
        lambda request: IncidentLookupResult(
            ticket_id=request.ticket_id,
            found=False,
            error="timeout",
        ),
    )

    result = support_graph.run_agent("Estado del incidente 77", run_id="tool-timeout")

    assert "No pude confirmar" in result["answer"]
    assert result["trace"][-2]["output"]["tool_error"] == "timeout"
    assert result["trace"][-1]["node"] == "tool_fallback"


def test_combined_question_traces_rag_then_tool(monkeypatch) -> None:
    monkeypatch.setattr(support_graph, "retrieve", lambda _question: [{"text": "SLA de 24 horas"}])
    monkeypatch.setattr(support_graph, "generate_answer", lambda *_args: "El SLA aplicable es de 24 horas.")
    monkeypatch.setattr(support_graph, "lookup_incident", lambda request: _ticket_result(request.ticket_id))

    result = support_graph.run_agent(
        "¿Cuál es el SLA y en qué estado está el ticket 42?",
        run_id="rag-and-tool",
    )

    assert "24 horas" in result["answer"] and "in_progress" in result["answer"]
    assert [event["node"] for event in result["trace"]] == [
        "receive_question",
        "retrieve_context",
        "generate_response",
        "lookup_incident",
        "combine_answer",
    ]
