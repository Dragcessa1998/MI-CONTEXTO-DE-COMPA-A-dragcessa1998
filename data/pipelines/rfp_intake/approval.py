"""Ramas LangGraph con interrupt, checkpoint SQLite y arbitraje determinista."""

from __future__ import annotations

import operator
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Mapping, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from data.pipelines.rfp_intake.approval_models import (
    ApprovalBranchResult,
    ApprovalDecisionRequest,
    ArbitrationFinding,
    FinalDocument,
    TraceEvent,
)
from data.pipelines.rfp_intake.models import DepartmentId


MAX_APPROVAL_ITERATIONS = 3
APPROVERS: dict[DepartmentId, str] = {
    "seleccion": "Javier Almeida",
    "capacitacion": "Elena Vargas",
    "soporte": "Roberto Díaz",
}


class ApprovalState(TypedDict, total=False):
    ticket_id: str
    department_id: DepartmentId
    approver: str
    client_name: str
    currency: str
    draft_content: str
    sections_snapshot: list[dict[str, Any]]
    approval_status: str
    approval_iteration: int
    max_iterations: int
    decision: str
    feedback: str
    conflicts: list[dict[str, Any]]
    trace: Annotated[list[dict[str, Any]], operator.add]


def namespaced_thread_id(ticket_id: str, department_id: DepartmentId) -> str:
    return f"rfp-{ticket_id}:{department_id}"


def _trace(agent: str, input_data: dict[str, Any], output_data: dict[str, Any]) -> dict[str, Any]:
    return TraceEvent(
        agent=agent,
        input=input_data,
        output=output_data,
        timestamp=datetime.now(UTC),
    ).model_dump(mode="json")


def _selection_close_days(draft: str) -> int | None:
    match = re.search(r"(\d+)\s+d[ií]as\s+laborables", draft, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _training_start_day(draft: str) -> int | None:
    match = re.search(r"(?:inicia|comienza|start)\D{0,24}(?:d[ií]a|day)\s*(\d+)", draft, re.IGNORECASE)
    return int(match.group(1)) if match else None


def detect_conflicts(
    sections: list[Mapping[str, Any]],
    expected_currency: str,
) -> list[ArbitrationFinding]:
    """Detecta únicamente los tres triggers estructurables del CONTEXT Nexova."""

    findings: list[ArbitrationFinding] = []
    by_department = {str(item["department_id"]): str(item.get("draft_content") or "") for item in sections}
    wrong_currency = "USD" if expected_currency == "EUR" else "EUR"
    currency_departments = [
        department_id
        for department_id, draft in by_department.items()
        if expected_currency not in draft or wrong_currency in draft
    ]
    if currency_departments:
        findings.append(ArbitrationFinding(
            trigger_id="currency-mismatch",
            departments=currency_departments,
            arbiter="Marcos Ibáñez",
            resolution=f"Reescribir todas las secciones afectadas en {expected_currency}, según la sede del cliente.",
        ))

    support = by_department.get("soporte")
    if support is not None and not re.search(r"(?:sla.{0,30}24 horas|24 horas.{0,30}sla)", support, re.IGNORECASE):
        findings.append(ArbitrationFinding(
            trigger_id="support-sla-missing",
            departments=["soporte"],
            arbiter="Roberto Díaz",
            resolution="Bloquear la aprobación hasta explicitar el SLA de respuesta de 24 horas.",
        ))

    selection = by_department.get("seleccion")
    training = by_department.get("capacitacion")
    close_days = _selection_close_days(selection or "")
    start_day = _training_start_day(training or "")
    if selection is not None and training is not None and close_days and start_day and start_day < max(15, close_days):
        findings.append(ArbitrationFinding(
            trigger_id="ttc-vs-training-window",
            departments=["seleccion", "capacitacion"],
            arbiter="Marcos Ibáñez",
            resolution=(
                "Secuenciar las entregas y solicitar cambios: la capacitación no puede empezar "
                f"antes del día {max(15, close_days)}."
            ),
        ))
    return findings


def prepare_node(state: ApprovalState) -> dict[str, Any]:
    output = {"approval_status": "pending"}
    return {
        **output,
        "trace": [_trace(
            "approval-preparer",
            {"ticket_id": state["ticket_id"], "department_id": state["department_id"]},
            output,
        )],
    }


def arbitration_node(state: ApprovalState) -> dict[str, Any]:
    all_findings = detect_conflicts(state["sections_snapshot"], state["currency"])
    findings = [
        item for item in all_findings if state["department_id"] in item.departments
    ]
    output = {"conflicts": [item.model_dump(mode="json") for item in findings]}
    return {
        **output,
        "trace": [_trace(
            "fixed-arbitrator",
            {"department_id": state["department_id"], "trigger_ids": [item.trigger_id for item in all_findings]},
            {"conflicts": output["conflicts"]},
        )],
    }


def human_approval_node(state: ApprovalState) -> dict[str, Any]:
    payload = {
        "type": "department_approval",
        "ticket_id": state["ticket_id"],
        "department_id": state["department_id"],
        "approver": state["approver"],
        "draft_content": state["draft_content"],
        "conflicts": state.get("conflicts", []),
        "allowed_decisions": ["approve", "reject", "request_changes"],
    }
    response = ApprovalDecisionRequest.model_validate(interrupt(payload))
    output = {
        "decision": response.decision,
        "feedback": (response.feedback or "").strip(),
    }
    return {
        **output,
        "trace": [_trace(
            "human-approval",
            {"approver": state["approver"], "department_id": state["department_id"]},
            output,
        )],
    }


def _revise_draft(state: ApprovalState, feedback: str) -> str:
    draft = state["draft_content"]
    trigger_ids = {item["trigger_id"] for item in state.get("conflicts", [])}
    if "currency-mismatch" in trigger_ids:
        wrong_currency = "USD" if state["currency"] == "EUR" else "EUR"
        draft = draft.replace(wrong_currency, state["currency"])
        if state["currency"] not in draft:
            draft += f"\n\nLa cotización final se expresará en {state['currency']}."
    if "support-sla-missing" in trigger_ids:
        draft += "\n\nEl servicio incluye explícitamente un SLA de respuesta de 24 horas."
    if "ttc-vs-training-window" in trigger_ids:
        close_days = max(15, _selection_close_days(
            next(
                (str(item.get("draft_content") or "") for item in state["sections_snapshot"] if item["department_id"] == "seleccion"),
                "",
            )
        ) or 15)
        if state["department_id"] == "capacitacion":
            draft += f"\n\nLa capacitación comenzará después del día {close_days}, una vez finalizada la selección."
        else:
            draft += f"\n\nSelección confirmará un cierre realista no inferior a {close_days} días laborables."
    if feedback:
        draft += f"\n\n### Revisión humana\n{feedback}"
    return draft


def apply_decision_node(state: ApprovalState) -> dict[str, Any]:
    decision = state["decision"]
    feedback = state.get("feedback", "")
    if decision == "approve" and state.get("conflicts"):
        decision = "request_changes"
        feedback = " ".join(item["resolution"] for item in state["conflicts"])

    if decision == "approve":
        output: dict[str, Any] = {"approval_status": "approved"}
    elif decision == "reject":
        output = {"approval_status": "rejected"}
    else:
        next_iteration = state.get("approval_iteration", 0) + 1
        if next_iteration >= state["max_iterations"]:
            output = {
                "approval_status": "rejected",
                "approval_iteration": next_iteration,
                "feedback": "Límite de revisiones alcanzado. " + feedback,
            }
        else:
            revised = _revise_draft(state, feedback)
            snapshots = [
                ({**item, "draft_content": revised} if item["department_id"] == state["department_id"] else item)
                for item in state["sections_snapshot"]
            ]
            output = {
                "approval_status": "pending",
                "approval_iteration": next_iteration,
                "draft_content": revised,
                "sections_snapshot": snapshots,
                "feedback": feedback,
            }
    return {
        **output,
        "trace": [_trace(
            "approval-decision-router",
            {"decision": state["decision"], "conflict_count": len(state.get("conflicts", []))},
            output,
        )],
    }


def route_decision(state: ApprovalState) -> str:
    return "retry" if state["approval_status"] == "pending" else "complete"


def build_approval_graph(checkpointer: SqliteSaver) -> Any:
    builder = StateGraph(ApprovalState)
    builder.add_node("prepare", prepare_node)
    builder.add_node("arbitration", arbitration_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("apply_decision", apply_decision_node)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "arbitration")
    builder.add_edge("arbitration", "human_approval")
    builder.add_edge("human_approval", "apply_decision")
    builder.add_conditional_edges("apply_decision", route_decision, {"retry": "arbitration", "complete": END})
    builder.validate()
    return builder.compile(checkpointer=checkpointer, name="nexova-rfp-department-approval")


class ApprovalWorkflowRuntime:
    """Mantiene un grafo durable y una rama checkpointed por ticket/departamento."""

    def __init__(self, checkpoint_path: Path) -> None:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = checkpoint_path
        self.connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
        self.checkpointer = SqliteSaver(self.connection)
        self.graph = build_approval_graph(self.checkpointer)

    @staticmethod
    def _config(ticket_id: str, department_id: DepartmentId) -> dict[str, Any]:
        return {"configurable": {"thread_id": namespaced_thread_id(ticket_id, department_id)}}

    def start_branch(self, ticket: Mapping[str, Any], section: Mapping[str, Any]) -> ApprovalBranchResult:
        department_id: DepartmentId = section["department_id"]
        config = self._config(str(ticket["ticket_id"]), department_id)
        self.checkpointer.delete_thread(namespaced_thread_id(str(ticket["ticket_id"]), department_id))
        state = self.graph.invoke({
            "ticket_id": str(ticket["ticket_id"]),
            "department_id": department_id,
            "approver": APPROVERS[department_id],
            "client_name": ticket["metadata"]["client_name"],
            "currency": ticket["metadata"]["currency"],
            "draft_content": section["draft_content"],
            "sections_snapshot": [dict(item) for item in ticket["sections"]],
            "approval_status": "pending",
            "approval_iteration": int(section.get("approval_iteration") or 0),
            "max_iterations": MAX_APPROVAL_ITERATIONS,
            "trace": [],
        }, config=config)
        return self._result(state, department_id)

    def resume_branch(
        self,
        ticket_id: str,
        department_id: DepartmentId,
        decision: ApprovalDecisionRequest,
        *,
        ticket: Mapping[str, Any] | None = None,
    ) -> ApprovalBranchResult:
        config = self._config(ticket_id, department_id)
        snapshot = self.graph.get_state(config)
        if not snapshot.values:
            raise KeyError("No existe un checkpoint para esta aprobación")
        if not snapshot.next:
            raise ValueError("La rama de aprobación ya terminó")
        if ticket is not None:
            current_section = next(
                item for item in ticket["sections"] if item["department_id"] == department_id
            )
            self.graph.update_state(config, {
                "sections_snapshot": [dict(item) for item in ticket["sections"]],
                "draft_content": current_section["draft_content"],
                "currency": ticket["metadata"]["currency"],
            })
        state = self.graph.invoke(Command(resume=decision.model_dump(mode="json")), config=config)
        return self._result(state, department_id)

    def branch_state(self, ticket_id: str, department_id: DepartmentId) -> ApprovalBranchResult:
        snapshot = self.graph.get_state(self._config(ticket_id, department_id))
        if not snapshot.values:
            raise KeyError("No existe un checkpoint para esta aprobación")
        return self._result(dict(snapshot.values), department_id, interrupted=bool(snapshot.next))

    @staticmethod
    def _result(
        state: Mapping[str, Any],
        department_id: DepartmentId,
        *,
        interrupted: bool | None = None,
    ) -> ApprovalBranchResult:
        interrupt_items = state.get("__interrupt__", [])
        payload = interrupt_items[0].value if interrupt_items else None
        is_interrupted = bool(interrupt_items) if interrupted is None else interrupted
        return ApprovalBranchResult(
            ticket_id=str(state["ticket_id"]),
            department_id=department_id,
            thread_id=namespaced_thread_id(str(state["ticket_id"]), department_id),
            approval_status=state.get("approval_status", "pending"),
            approval_iteration=int(state.get("approval_iteration", 0)),
            feedback=str(state.get("feedback") or "") or None,
            draft_content=str(state["draft_content"]),
            interrupted=is_interrupted,
            interrupt=payload,
            conflicts=state.get("conflicts", []),
            trace=state.get("trace", []),
        )

    def close(self) -> None:
        self.connection.close()


def generate_final_document(ticket: Mapping[str, Any], output_dir: Path) -> FinalDocument:
    sections = [item for item in ticket.get("sections", []) if item.get("approval_status") == "approved"]
    if not sections or len(sections) != len(ticket.get("sections", [])):
        raise ValueError("El documento final requiere la aprobación de todos los departamentos activos")
    metadata = ticket["metadata"]
    currency = metadata["currency"]
    if currency not in {"EUR", "USD"}:
        raise ValueError("La moneda debe estar confirmada antes de generar el documento final")
    body = "\n\n".join(str(section["draft_content"]).strip() for section in sections)
    content = (
        f"# Propuesta Nexova para {metadata['client_name']}\n\n"
        f"**Ticket:** {ticket['ticket_id']}  \n"
        f"**Moneda:** {currency}  \n"
        f"**Estado:** Aprobada por todos los departamentos activos\n\n"
        f"{body}\n\n"
        "---\n\n"
        "Documento consolidado para Marcos Ibáñez, Director de Ventas."
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{ticket['ticket_id']}.md"
    target.write_text(content, encoding="utf-8")
    return FinalDocument(
        ticket_id=str(ticket["ticket_id"]),
        content=content,
        file_path=str(target),
        currency=currency,
        sections=[section["department_id"] for section in sections],
        generated_at=datetime.now(UTC),
    )
