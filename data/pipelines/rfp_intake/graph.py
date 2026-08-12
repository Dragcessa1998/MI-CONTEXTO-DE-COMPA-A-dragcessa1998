"""Grafo dedicado orchestrator-worker-synthesizer para recepción RFP."""

from __future__ import annotations

import operator
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from data.pipelines.rfp_intake.agents import (
    classify_document,
    department_worker,
    extract_metadata,
    orchestrate,
    synthesize,
)
from data.pipelines.rfp_intake.document import convert_pdf_to_markdown
from data.pipelines.rfp_intake.models import DepartmentSection, IntakeResult, RfpMetadata


class RfpIntakeState(TypedDict, total=False):
    pdf_path: str
    markdown: str
    markdown_path: str
    is_rfp: bool
    classification_reason: str
    metadata: dict[str, Any]
    departments: list[str]
    department_id: str
    sections: Annotated[list[dict[str, Any]], operator.add]
    sales_summary: str


def convert_document(state: RfpIntakeState) -> dict[str, Any]:
    markdown, markdown_path = convert_pdf_to_markdown(Path(state["pdf_path"]))
    return {"markdown": markdown, "markdown_path": str(markdown_path)}


def classify(state: RfpIntakeState) -> dict[str, Any]:
    result = classify_document(state["markdown"])
    return {"is_rfp": result.is_rfp, "classification_reason": result.reason}


def route_classification(state: RfpIntakeState) -> Literal["extract", "discard"]:
    return "extract" if state["is_rfp"] else "discard"


def discard(_state: RfpIntakeState) -> dict[str, Any]:
    return {"sections": [], "sales_summary": "Documento descartado por el clasificador."}


def extract(state: RfpIntakeState) -> dict[str, Any]:
    metadata = extract_metadata(state["markdown"])
    return {"metadata": metadata.model_dump(mode="json")}


def orchestrator(state: RfpIntakeState) -> dict[str, Any]:
    metadata = RfpMetadata.model_validate(state["metadata"])
    return {"departments": orchestrate(metadata)}


def fan_out_workers(state: RfpIntakeState) -> list[Send]:
    return [
        Send(
            "department_worker",
            {
                "pdf_path": state["pdf_path"],
                "markdown": state["markdown"],
                "markdown_path": state["markdown_path"],
                "metadata": state["metadata"],
                "department_id": department_id,
                "sections": [],
            },
        )
        for department_id in state["departments"]
    ]


def worker(state: RfpIntakeState) -> dict[str, Any]:
    section = department_worker(
        state["department_id"],  # type: ignore[arg-type]
        RfpMetadata.model_validate(state["metadata"]),
        state["markdown"],
    )
    return {"sections": [section.model_dump(mode="json")]}


def synthesizer(state: RfpIntakeState) -> dict[str, Any]:
    metadata = RfpMetadata.model_validate(state["metadata"])
    sections = [DepartmentSection.model_validate(item) for item in state["sections"]]
    return {"sales_summary": synthesize(metadata, sections)}


def build_graph() -> Any:
    builder = StateGraph(RfpIntakeState)
    builder.add_node("convert_pdf_to_markdown", convert_document)
    builder.add_node("classifier", classify)
    builder.add_node("discard", discard)
    builder.add_node("extract_metadata", extract)
    builder.add_node("orchestrator", orchestrator)
    builder.add_node("department_worker", worker)
    builder.add_node("synthesizer", synthesizer)
    builder.add_edge(START, "convert_pdf_to_markdown")
    builder.add_edge("convert_pdf_to_markdown", "classifier")
    builder.add_conditional_edges(
        "classifier",
        route_classification,
        {"extract": "extract_metadata", "discard": "discard"},
    )
    builder.add_edge("discard", END)
    builder.add_edge("extract_metadata", "orchestrator")
    builder.add_conditional_edges("orchestrator", fan_out_workers, ["department_worker"])
    builder.add_edge("department_worker", "synthesizer")
    builder.add_edge("synthesizer", END)
    builder.validate()
    return builder.compile(name="nexova-rfp-intake")


rfp_intake_graph = build_graph()


def run_rfp_intake(pdf_path: Path) -> IntakeResult:
    state = rfp_intake_graph.invoke({"pdf_path": str(pdf_path), "sections": []})
    metadata = RfpMetadata.model_validate(state["metadata"]) if state.get("metadata") else None
    return IntakeResult(
        classification={"is_rfp": state["is_rfp"], "reason": state["classification_reason"]},
        metadata=metadata,
        sections=[DepartmentSection.model_validate(item) for item in state.get("sections", [])],
        sales_summary=state.get("sales_summary"),
        markdown_path=state["markdown_path"],
    )
