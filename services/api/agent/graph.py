"""Grafo LangGraph explícito para preguntas sobre conocimiento Nexova."""

from __future__ import annotations

from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from data.pipelines.rag import NO_CONTEXT_ANSWER, generate_answer, retrieve
from agent.trace_store import trace_store


EMPTY_QUESTION_ANSWER = "Escribe una pregunta concreta para poder ayudarte."


class AgentState(TypedDict, total=False):
    run_id: str
    question: str
    context: list[dict[str, Any]]
    answer: str
    route: str


def _trace(state: AgentState, node: str, output: dict[str, Any]) -> dict[str, Any]:
    trace_store.append(state["run_id"], node, output)
    return output


def receive_question(state: AgentState) -> dict[str, Any]:
    question = state.get("question", "").strip()
    return _trace(
        state,
        "receive_question",
        {"question": question, "route": "retrieve" if question else "invalid"},
    )


def route_question(state: AgentState) -> Literal["retrieve_context", "invalid_question"]:
    return "retrieve_context" if state.get("route") == "retrieve" else "invalid_question"


def invalid_question(state: AgentState) -> dict[str, Any]:
    return _trace(state, "invalid_question", {"answer": EMPTY_QUESTION_ANSWER})


def retrieve_context(state: AgentState) -> dict[str, Any]:
    context = retrieve(state["question"])
    return _trace(
        state,
        "retrieve_context",
        {"context": context, "route": "generate" if context else "insufficient_context"},
    )


def route_context(state: AgentState) -> Literal["generate_response", "insufficient_context"]:
    return "generate_response" if state.get("route") == "generate" else "insufficient_context"


def insufficient_context(state: AgentState) -> dict[str, Any]:
    return _trace(state, "insufficient_context", {"answer": NO_CONTEXT_ANSWER})


def generate_response(state: AgentState) -> dict[str, Any]:
    answer = generate_answer(state["question"], state["context"])
    return _trace(state, "generate_response", {"answer": answer})


def build_graph() -> Any:
    builder = StateGraph(AgentState)
    builder.add_node("receive_question", receive_question)
    builder.add_node("invalid_question", invalid_question)
    builder.add_node("retrieve_context", retrieve_context)
    builder.add_node("insufficient_context", insufficient_context)
    builder.add_node("generate_response", generate_response)
    builder.add_edge(START, "receive_question")
    builder.add_conditional_edges(
        "receive_question",
        route_question,
        {"retrieve_context": "retrieve_context", "invalid_question": "invalid_question"},
    )
    builder.add_conditional_edges(
        "retrieve_context",
        route_context,
        {"generate_response": "generate_response", "insufficient_context": "insufficient_context"},
    )
    builder.add_edge("invalid_question", END)
    builder.add_edge("insufficient_context", END)
    builder.add_edge("generate_response", END)
    builder.validate()
    return builder.compile(checkpointer=InMemorySaver(), name="nexova-support-agent")


agent_graph = build_graph()


def run_agent(question: str, *, run_id: str | None = None) -> dict[str, Any]:
    current_run_id = run_id or str(uuid4())
    trace_store.start(current_run_id)
    try:
        result = agent_graph.invoke(
            {"run_id": current_run_id, "question": question},
            config={"configurable": {"thread_id": current_run_id}},
        )
        trace_store.complete(current_run_id)
        return {
            "run_id": current_run_id,
            "answer": result["answer"],
            "trace": trace_store.get(current_run_id)["events"],
        }
    except Exception:
        trace_store.complete(current_run_id)
        raise


__all__ = ["AgentState", "EMPTY_QUESTION_ANSWER", "agent_graph", "build_graph", "run_agent"]
