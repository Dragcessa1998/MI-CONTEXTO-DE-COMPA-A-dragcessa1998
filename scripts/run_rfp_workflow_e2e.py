#!/usr/bin/env python3
"""Recorrido reproducible RFP Partes 1→3 con aprobaciones simuladas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_intake import run_proposal_generation, run_rfp_intake  # noqa: E402
from data.pipelines.rfp_intake.approval import ApprovalWorkflowRuntime, generate_final_document  # noqa: E402
from data.pipelines.rfp_intake.approval_models import ApprovalDecisionRequest  # noqa: E402


def write_synthetic_rfp(path: Path) -> None:
    """Crea un PDF de una página sin depender de una librería generadora."""

    lines = [
        "Request for Proposal.",
        "Issuing Organization: Vantex Retail Group, S.A.",
        "Headquarters: Madrid, Spain.",
        "We request executive search for 5 roles.",
        "We request leadership training for 40 participantes.",
        "Proposal deadline August 18, 2026.",
    ]
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    text_commands = " 0 -18 Td ".join(f"({line}) Tj" for line in escaped)
    stream = f"BT /F1 11 Tf 54 720 Td {text_commands} ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(body)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    path.write_bytes(pdf)


def run_e2e(workdir: Path) -> dict[str, Any]:
    workdir.mkdir(parents=True, exist_ok=True)
    pdf_path = workdir / "vantex-synthetic-rfp.pdf"
    write_synthetic_rfp(pdf_path)

    intake = run_rfp_intake(pdf_path)
    if not intake.classification.is_rfp or intake.metadata is None:
        raise RuntimeError("La Parte 1 no aceptó la RFP sintética")
    ticket: dict[str, Any] = {
        "ticket_id": "e2e-vantex",
        "status": "intake_complete",
        "metadata": intake.metadata.model_dump(mode="json"),
        "sections": [section.model_dump(mode="json") for section in intake.sections],
    }

    generation = run_proposal_generation(ticket)
    generated = {item.department_id: item for item in generation.sections}
    for section in ticket["sections"]:
        output = generated[section["department_id"]]
        section.update({
            "draft_content": output.draft_content,
            "evaluation_results": [
                item.model_dump(by_alias=True, mode="json") for item in output.evaluation_results
            ],
            "generation_iteration": output.generation_iteration,
            "approval_status": "pending",
            "approval_iteration": 0,
        })
    ticket["status"] = "waiting_for_approval"

    runtime = ApprovalWorkflowRuntime(workdir / "approval-checkpoints.sqlite3")
    started = [runtime.start_branch(ticket, section) for section in ticket["sections"]]
    approval_order = ["capacitacion", "seleccion"]
    completed = []
    for department_id in approval_order:
        branch = runtime.resume_branch(
            ticket["ticket_id"],
            department_id,
            ApprovalDecisionRequest(decision="approve"),
        )
        completed.append(branch)
        next(item for item in ticket["sections"] if item["department_id"] == department_id).update({
            "approval_status": branch.approval_status,
            "draft_content": branch.draft_content,
        })
    runtime.close()

    document = generate_final_document(ticket, workdir / "final")
    return {
        "ticket_id": ticket["ticket_id"],
        "states": ["intake_complete", generation.status, "waiting_for_approval", "done"],
        "departments": [section["department_id"] for section in ticket["sections"]],
        "approval_order": approval_order,
        "thread_ids": [item.thread_id for item in started],
        "all_approved": all(item.approval_status == "approved" for item in completed),
        "final_document": document.model_dump(mode="json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", type=Path, default=REPO_ROOT / "data" / "e2e" / "rfp")
    args = parser.parse_args()
    print(json.dumps(run_e2e(args.workdir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
