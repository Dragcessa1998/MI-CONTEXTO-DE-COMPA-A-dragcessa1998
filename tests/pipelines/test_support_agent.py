from __future__ import annotations

from agent import graph as support_graph
from agent.trace_store import trace_store


def setup_function() -> None:
    trace_store.clear()


def test_empty_question_routes_without_retrieval(monkeypatch) -> None:
    monkeypatch.setattr(
        support_graph,
        "retrieve",
        lambda _question: (_ for _ in ()).throw(AssertionError("retrieve must not run")),
    )

    result = support_graph.run_agent("   ", run_id="empty-question")

    assert result["answer"] == support_graph.EMPTY_QUESTION_ANSWER
    assert [event["node"] for event in result["trace"]] == [
        "receive_question",
        "invalid_question",
    ]


def test_insufficient_context_routes_to_honest_answer(monkeypatch) -> None:
    monkeypatch.setattr(support_graph, "retrieve", lambda _question: [])
    monkeypatch.setattr(
        support_graph,
        "generate_answer",
        lambda *_args: (_ for _ in ()).throw(AssertionError("generation must not run")),
    )

    result = support_graph.run_agent("¿Tenéis oficina en Tokio?", run_id="no-context")

    assert result["answer"] == support_graph.NO_CONTEXT_ANSWER
    assert [event["node"] for event in result["trace"]] == [
        "receive_question",
        "retrieve_context",
        "insufficient_context",
    ]


def test_grounded_answer_uses_retrieved_context_once(monkeypatch) -> None:
    context = [{
        "source_document": "hiring-process-sla",
        "section": "Garantía",
        "text": "La garantía contractual de reemplazo es de seis meses.",
    }]
    calls: list[tuple[str, object]] = []

    def fake_retrieve(question: str):
        calls.append(("retrieve", question))
        return context

    def fake_generate(question: str, supplied_context: list[dict]):
        calls.append(("generate", supplied_context))
        return "Nexova ofrece una garantía contractual de reemplazo de seis meses."

    monkeypatch.setattr(support_graph, "retrieve", fake_retrieve)
    monkeypatch.setattr(support_graph, "generate_answer", fake_generate)

    result = support_graph.run_agent("¿Qué garantía ofrece Nexova?", run_id="grounded")

    assert "seis meses" in result["answer"]
    assert calls == [
        ("retrieve", "¿Qué garantía ofrece Nexova?"),
        ("generate", context),
    ]
    assert [event["node"] for event in result["trace"]] == [
        "receive_question",
        "retrieve_context",
        "generate_response",
    ]
    assert support_graph.agent_graph.get_state(
        {"configurable": {"thread_id": "grounded"}}
    ).values["answer"].endswith("seis meses.")
