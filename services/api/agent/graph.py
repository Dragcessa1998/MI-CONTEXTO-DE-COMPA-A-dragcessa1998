"""Grafo LangGraph que enruta entre RAG y tickets operativos reales."""

from __future__ import annotations

import re
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from data.pipelines.rag import NO_CONTEXT_ANSWER, generate_answer, retrieve
from agent.tools import IncidentLookupInput, lookup_incident
from agent.trace_store import trace_store


EMPTY_QUESTION_ANSWER = "Escribe una pregunta concreta para poder ayudarte."
INCIDENT_FALLBACK = (
    "No pude confirmar el estado de ese ticket ahora mismo. "
    "Inténtalo de nuevo o consúltalo en el gestor de incidentes."
)
_TICKET_TERMS = re.compile(r"\b(?:ticket|incidente|incidencia)\b", re.IGNORECASE)
_TICKET_ID = re.compile(r"\b(?:ticket|incidente|incidencia)\s*(?:#|n[úu]mero|id)?\s*(\d+)\b", re.IGNORECASE)
_KNOWLEDGE_TERMS = re.compile(
    r"\b(?:sla|pol[ií]tica|procedimiento|garant[ií]a|precio|tarifa|servicio|headhunting)\b",
    re.IGNORECASE,
)


class AgentState(TypedDict, total=False):
    run_id: str
    question: str
    context: list[dict[str, Any]]
    rag_answer: str
    answer: str
    route: str
    ticket_id: int
    incident: dict[str, Any]
    tool_error: str


def _trace(state: AgentState, node: str, output: dict[str, Any]) -> dict[str, Any]:
    trace_store.append(state["run_id"], node, output)
    return output


def select_route(question: str) -> str:
    if not question:
        return "invalid"
    uses_ticket = bool(_TICKET_TERMS.search(question))
    uses_knowledge = bool(_KNOWLEDGE_TERMS.search(question))
    if uses_ticket and uses_knowledge:
        return "both"
    if uses_ticket:
        return "tool"
    return "rag"


def receive_question(state: AgentState) -> dict[str, Any]:
    question = state.get("question", "").strip()
    match = _TICKET_ID.search(question)
    output: dict[str, Any] = {"question": question, "route": select_route(question)}
    if match:
        output["ticket_id"] = int(match.group(1))
    return _trace(state, "receive_question", output)


def route_question(
    state: AgentState,
) -> Literal["invalid_question", "retrieve_context", "lookup_incident", "missing_ticket_id"]:
    route = state.get("route")
    if route == "invalid":
        return "invalid_question"
    if route in {"tool", "both"} and "ticket_id" not in state:
        return "missing_ticket_id"
    if route == "tool":
        return "lookup_incident"
    return "retrieve_context"


def invalid_question(state: AgentState) -> dict[str, Any]:
    return _trace(state, "invalid_question", {"answer": EMPTY_QUESTION_ANSWER})


def missing_ticket_id(state: AgentState) -> dict[str, Any]:
    return _trace(
        state,
        "missing_ticket_id",
        {"answer": "Indica el número del ticket que quieres consultar."},
    )


def retrieve_context(state: AgentState) -> dict[str, Any]:
    context = retrieve(state["question"])
    if context:
        next_route = "generate"
    elif state.get("route") == "both":
        next_route = "tool"
    else:
        next_route = "insufficient_context"
    return _trace(state, "retrieve_context", {"context": context, "route": next_route})


def route_context(
    state: AgentState,
) -> Literal["generate_response", "lookup_incident", "insufficient_context"]:
    return {
        "generate": "generate_response",
        "tool": "lookup_incident",
    }.get(state.get("route"), "insufficient_context")


def insufficient_context(state: AgentState) -> dict[str, Any]:
    return _trace(state, "insufficient_context", {"answer": NO_CONTEXT_ANSWER})


def generate_response(state: AgentState) -> dict[str, Any]:
    answer = generate_answer(state["question"], state["context"])
    if state.get("ticket_id") is not None:
        return _trace(state, "generate_response", {"rag_answer": answer, "route": "tool"})
    return _trace(state, "generate_response", {"answer": answer, "route": "complete"})


def route_after_generation(state: AgentState) -> Literal["lookup_incident", "complete"]:
    return "lookup_incident" if state.get("route") == "tool" else "complete"


def lookup_incident_node(state: AgentState) -> dict[str, Any]:
    result = lookup_incident(IncidentLookupInput(ticket_id=state["ticket_id"]))
    output: dict[str, Any] = {
        "incident": result.model_dump(mode="json"),
        "route": "combine" if state.get("rag_answer") else "tool_answer",
    }
    if not result.found:
        output.update({"tool_error": result.error or "unavailable", "route": "tool_fallback"})
    return _trace(state, "lookup_incident", output)


def route_tool(state: AgentState) -> Literal["tool_answer", "combine_answer", "tool_fallback"]:
    return {
        "tool_answer": "tool_answer",
        "combine": "combine_answer",
    }.get(state.get("route"), "tool_fallback")


def tool_answer(state: AgentState) -> dict[str, Any]:
    incident = state["incident"]
    answer = format_incident_answer(incident)
    return _trace(state, "tool_answer", {"answer": answer})


def format_incident_answer(incident: dict[str, Any]) -> str:
    return (
        f"El ticket {incident['ticket_id']} está {incident['status']}. "
        f"Categoría: {incident['category']}; origen: {incident['origin']}; "
        f"sede: {incident['branch']}. Última actualización: {incident['updated_at']}."
    )


def combine_answer(state: AgentState) -> dict[str, Any]:
    incident = state["incident"]
    answer = f"{state['rag_answer']}{format_incident_suffix(incident)}"
    return _trace(state, "combine_answer", {"answer": answer})


def format_incident_suffix(incident: dict[str, Any]) -> str:
    return (
        "\n\nDato operativo confirmado: el ticket "
        f"{incident['ticket_id']} está {incident['status']} y fue actualizado "
        f"el {incident['updated_at']}."
    )


def tool_fallback(state: AgentState) -> dict[str, Any]:
    prefix = f"{state['rag_answer']}\n\n" if state.get("rag_answer") else ""
    return _trace(state, "tool_fallback", {"answer": prefix + INCIDENT_FALLBACK})


def build_graph() -> Any:
    builder = StateGraph(AgentState)
    for name, node in {
        "receive_question": receive_question,
        "invalid_question": invalid_question,
        "missing_ticket_id": missing_ticket_id,
        "retrieve_context": retrieve_context,
        "insufficient_context": insufficient_context,
        "generate_response": generate_response,
        "lookup_incident": lookup_incident_node,
        "tool_answer": tool_answer,
        "combine_answer": combine_answer,
        "tool_fallback": tool_fallback,
    }.items():
        builder.add_node(name, node)
    builder.add_edge(START, "receive_question")
    builder.add_conditional_edges("receive_question", route_question)
    builder.add_conditional_edges("retrieve_context", route_context)
    builder.add_conditional_edges(
        "generate_response",
        route_after_generation,
        {"lookup_incident": "lookup_incident", "complete": END},
    )
    builder.add_conditional_edges("lookup_incident", route_tool)
    for terminal in (
        "invalid_question",
        "missing_ticket_id",
        "insufficient_context",
        "tool_answer",
        "combine_answer",
        "tool_fallback",
    ):
        builder.add_edge(terminal, END)
    builder.validate()
    return builder.compile(checkpointer=InMemorySaver(), name="nexova-support-agent-tools")


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


__all__ = [
    "AgentState",
    "EMPTY_QUESTION_ANSWER",
    "INCIDENT_FALLBACK",
    "agent_graph",
    "build_graph",
    "format_incident_answer",
    "format_incident_suffix",
    "run_agent",
    "select_route",
]
