"""Generador y evaluadores del segundo tramo del workflow RFP de Nexova."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Mapping, TypedDict

from langgraph.graph import END, START, StateGraph

from data.pipelines.rfp_intake.models import DepartmentId, RfpMetadata
from data.pipelines.rfp_intake.proposal_models import (
    ComplianceEvaluation,
    EvaluationResult,
    GeneratedSection,
    ProposalGenerationResult,
    ReadabilityEvaluation,
    RelevanceEvaluation,
)


MAX_GENERATION_ITERATIONS = 3
RULE_IDS = ("G-90", "CUR-01", "SEL-15", "SUP-24", "REF-ANON")


class ProposalState(TypedDict, total=False):
    metadata: dict[str, Any]
    section: dict[str, Any]
    draft_content: str
    evaluations: list[dict[str, Any]]
    iteration: int
    max_iterations: int
    needs_human_review: bool


def _compact(value: str) -> str:
    return " ".join(value.split())


def generate_department_section(
    metadata: RfpMetadata,
    section: Mapping[str, Any],
    feedback: list[str] | None = None,
) -> str:
    """Genera sólo con el handoff persistido de Parte 1; nunca vuelve al PDF."""

    department_id = str(section["department_id"])
    client_name = metadata.client_name.rstrip(".")
    key_aspects = [str(item) for item in section.get("key_aspects", [])]
    open_questions = [str(item) for item in section.get("open_questions", [])]
    titles = {
        "seleccion": "Selección de talento",
        "capacitacion": "Capacitación corporativa",
        "soporte": "Soporte externalizado",
    }
    commitments = {
        "seleccion": "El plazo comprometido será de al menos 15 días laborables para cualquier búsqueda ejecutiva.",
        "capacitacion": "El calendario y el formato de impartición se cerrarán con el responsable del cliente.",
        "soporte": "El servicio incluirá explícitamente un SLA de respuesta de 24 horas y la cobertura de turnos acordada.",
    }
    aspects = "\n".join(f"- {item}" for item in key_aspects) or "- Alcance pendiente de confirmación."
    questions = "\n".join(f"- {item}" for item in open_questions) or "- No hay preguntas abiertas."
    revision = ""
    if feedback:
        revision = "\n\nAjustes aplicados en esta revisión:\n" + "\n".join(f"- {item}" for item in feedback)
    return (
        f"## {titles[department_id]}\n\n"
        f"Nexova propone este workstream para {client_name}. La cotización se expresará en {metadata.currency}. "
        "El alcance se validará antes de convertir preguntas abiertas en compromisos.\n\n"
        f"### Requisitos cubiertos\n{aspects}\n\n"
        f"### Compromisos del servicio\n{commitments[department_id]} "
        "La propuesta incluye la garantía estándar de satisfacción de 90 días de Nexova. "
        "Cualquier referencia se presentará de forma anónima, por ejemplo como «un cliente del mismo sector».\n\n"
        f"### Puntos por confirmar\n{questions}{revision}"
    )


def evaluate_readability(draft: str) -> ReadabilityEvaluation:
    sentences = [item.strip() for item in re.split(r"[.!?]+", draft) if item.strip()]
    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", draft)
    average = len(words) / max(1, len(sentences))
    score = max(0.0, min(100.0, 100.0 - max(0.0, average - 18.0) * 4.0))
    passed = score >= 60
    details = f"Promedio de {average:.1f} palabras por frase; objetivo operativo ≤28."
    return ReadabilityEvaluation.model_validate({"pass": passed, "score": round(score, 1), "details": details})


def _aspect_tokens(aspect: str) -> set[str]:
    ignored = {"para", "como", "este", "esta", "desde", "hasta", "cliente", "nexova", "with", "the", "and"}
    return {
        token
        for token in re.findall(r"[a-záéíóúüñ0-9]+", aspect.lower())
        if len(token) >= 4 and token not in ignored
    }


def evaluate_relevance(draft: str, key_aspects: list[str]) -> RelevanceEvaluation:
    lower = draft.lower()
    missing = [
        aspect
        for aspect in key_aspects
        if _aspect_tokens(aspect) and not (_aspect_tokens(aspect) & set(re.findall(r"[a-záéíóúüñ0-9]+", lower)))
    ]
    return RelevanceEvaluation.model_validate({"pass": not missing, "missing_aspects": missing})


def evaluate_compliance(
    draft: str,
    department_id: DepartmentId,
    metadata: RfpMetadata,
) -> ComplianceEvaluation:
    lower = _compact(draft.lower())
    violations: list[str] = []
    if "90 días" not in lower and "90 dias" not in lower:
        violations.append("G-90: falta la garantía estándar de satisfacción de 90 días.")
    if metadata.currency not in draft:
        violations.append(f"CUR-01: la propuesta debe cotizar en {metadata.currency} según la sede del cliente.")
    if department_id == "seleccion" and not re.search(r"(?:al menos|mínimo de) 15 días laborables", lower):
        violations.append("SEL-15: selección ejecutiva no puede prometer menos de 15 días laborables.")
    if department_id == "soporte" and not re.search(r"(?:sla.{0,30}24 horas|24 horas.{0,30}sla)", lower):
        violations.append("SUP-24: soporte debe mencionar explícitamente el SLA de respuesta de 24 horas.")
    named_reference = re.search(r"referencia(?: de cliente)?\s*:\s*(?!un cliente|una empresa)[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÜÑáéíóúüñ-]+", draft)
    if named_reference:
        violations.append("REF-ANON: las referencias de clientes actuales deben anonimizarse.")
    applicable = ["G-90", "CUR-01", "REF-ANON"]
    if department_id == "seleccion":
        applicable.append("SEL-15")
    if department_id == "soporte":
        applicable.append("SUP-24")
    return ComplianceEvaluation.model_validate({"pass": not violations, "rule_ids": applicable, "violations": violations})


def evaluate_section_parallel(
    draft: str,
    department_id: DepartmentId,
    metadata: RfpMetadata,
    key_aspects: list[str],
    iteration: int,
) -> EvaluationResult:
    """Ejecuta legibilidad, relevancia y cumplimiento como evaluadores independientes."""

    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="rfp-evaluator") as pool:
        readability_future = pool.submit(evaluate_readability, draft)
        relevance_future = pool.submit(evaluate_relevance, draft, key_aspects)
        compliance_future = pool.submit(evaluate_compliance, draft, department_id, metadata)
        readability = readability_future.result()
        relevance = relevance_future.result()
        compliance = compliance_future.result()
    feedback: list[str] = []
    if not readability.passed:
        feedback.append("Acortar frases y separar los compromisos en párrafos más directos.")
    feedback.extend(f"Incluir el aspecto omitido: {item}" for item in relevance.missing_aspects)
    feedback.extend(compliance.violations)
    overall_pass = readability.passed and relevance.passed and compliance.passed
    return EvaluationResult(
        section_id=department_id,
        readability=readability,
        relevance=relevance,
        compliance=compliance,
        overall_pass=overall_pass,
        actionable_feedback=feedback,
        iteration=iteration,
    )


def generator_node(state: ProposalState) -> dict[str, Any]:
    metadata = RfpMetadata.model_validate(state["metadata"])
    prior = state.get("evaluations", [])
    feedback = prior[-1].get("actionable_feedback", []) if prior else []
    return {
        "draft_content": generate_department_section(metadata, state["section"], feedback),
        "iteration": state.get("iteration", 0) + 1,
    }


def evaluator_node(state: ProposalState) -> dict[str, Any]:
    metadata = RfpMetadata.model_validate(state["metadata"])
    evaluation = evaluate_section_parallel(
        state["draft_content"],
        state["section"]["department_id"],
        metadata,
        [str(item) for item in state["section"].get("key_aspects", [])],
        state["iteration"],
    )
    return {"evaluations": [*state.get("evaluations", []), evaluation.model_dump(by_alias=True, mode="json")]}


def route_evaluation(state: ProposalState) -> str:
    if state["evaluations"][-1]["overall_pass"]:
        return "complete"
    if state["iteration"] >= state["max_iterations"]:
        return "exhausted"
    return "retry"


def complete_node(_state: ProposalState) -> dict[str, bool]:
    return {"needs_human_review": False}


def exhausted_node(_state: ProposalState) -> dict[str, bool]:
    return {"needs_human_review": True}


def build_proposal_graph() -> Any:
    builder = StateGraph(ProposalState)
    builder.add_node("generator", generator_node)
    builder.add_node("parallel_evaluators", evaluator_node)
    builder.add_node("complete", complete_node)
    builder.add_node("iteration_limit_exhausted", exhausted_node)
    builder.add_edge(START, "generator")
    builder.add_edge("generator", "parallel_evaluators")
    builder.add_conditional_edges(
        "parallel_evaluators",
        route_evaluation,
        {"complete": "complete", "exhausted": "iteration_limit_exhausted", "retry": "generator"},
    )
    builder.add_edge("complete", END)
    builder.add_edge("iteration_limit_exhausted", END)
    builder.validate()
    return builder.compile(name="nexova-rfp-proposal-generation")


proposal_generation_graph = build_proposal_graph()


def run_proposal_generation(
    ticket: Mapping[str, Any],
    *,
    max_iterations: int = MAX_GENERATION_ITERATIONS,
    graph: Any = proposal_generation_graph,
) -> ProposalGenerationResult:
    """Consume exclusivamente el ticket persistido que entrega Parte 1."""

    if max_iterations < 1:
        raise ValueError("max_iterations debe ser al menos 1")
    metadata = RfpMetadata.model_validate(ticket.get("metadata"))
    source_sections = ticket.get("sections") or []
    if not source_sections:
        raise ValueError("El ticket no contiene secciones departamentales de Parte 1")
    generated: list[GeneratedSection] = []
    for section in source_sections:
        state = graph.invoke({
            "metadata": metadata.model_dump(mode="json"),
            "section": dict(section),
            "evaluations": [],
            "iteration": 0,
            "max_iterations": max_iterations,
        })
        generated.append(GeneratedSection(
            department_id=section["department_id"],
            draft_content=state["draft_content"],
            evaluation_results=state["evaluations"],
            generation_iteration=state["iteration"],
            needs_human_review=state["needs_human_review"],
        ))
    status = "needs_human_review" if any(item.needs_human_review for item in generated) else "under_evaluation"
    return ProposalGenerationResult(ticket_id=str(ticket["ticket_id"]), status=status, sections=generated)
