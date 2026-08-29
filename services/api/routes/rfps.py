"""Recepción asíncrona y consulta de tickets RFP en el backend existente."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from data.pipelines.rfp_intake import (
    ApprovalWorkflowRuntime,
    generate_final_document,
    run_proposal_generation,
    run_rfp_intake,
)
from data.pipelines.rfp_intake.approval_models import ApprovalDecisionRequest
from data.pipelines.rfp_intake.models import DepartmentId
from rfp_repository import RfpRepository, get_rfp_repository
from routes.rfp_events import rfp_event_broker, stream_rfp_events
from security import get_current_user


REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = Path(os.getenv("RFP_RAW_DIR", str(REPO_ROOT / "data" / "raw" / "rfps"))).resolve()
MAX_PDF_BYTES = 10 * 1024 * 1024
CHECKPOINT_PATH = Path(os.getenv(
    "RFP_CHECKPOINT_DB",
    str(REPO_ROOT / "data" / "checkpoints" / "rfp-approvals.sqlite3"),
)).resolve()
FINAL_DIR = Path(os.getenv("RFP_FINAL_DIR", str(REPO_ROOT / "data" / "final" / "rfps"))).resolve()

router = APIRouter(
    prefix="/api/rfps",
    tags=["rfp-intake"],
    dependencies=[Depends(get_current_user)],
)


def repository_dependency() -> RfpRepository:
    return get_rfp_repository()


@lru_cache(maxsize=1)
def get_approval_runtime() -> ApprovalWorkflowRuntime:
    return ApprovalWorkflowRuntime(CHECKPOINT_PATH)


def approval_runtime_dependency() -> ApprovalWorkflowRuntime:
    return get_approval_runtime()


def _run_background(ticket_id: str, raw_pdf_path: str, repository: RfpRepository) -> None:
    try:
        repository.save_result(ticket_id, run_rfp_intake(Path(raw_pdf_path)))
    except Exception:
        repository.mark_failed(ticket_id)


def _run_drafting(ticket_id: str, repository: RfpRepository) -> None:
    try:
        ticket = repository.get_ticket(ticket_id)
        if ticket is None:
            raise KeyError("ticket inexistente")
        repository.mark_under_evaluation(ticket_id)
        repository.save_generation(ticket_id, run_proposal_generation(ticket))
    except Exception:
        repository.mark_failed(ticket_id)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_rfp(
    background_tasks: BackgroundTasks,
    repository: Annotated[RfpRepository, Depends(repository_dependency)],
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    if file.content_type != "application/pdf" or not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sólo se aceptan documentos PDF.")
    content = await file.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="El PDF supera el límite de 10 MB.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="El archivo no contiene un PDF válido.")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / f"{uuid4()}.pdf"
    target.write_bytes(content)
    try:
        ticket = repository.create_ticket(str(target))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    rfp_event_broker.publish({
        "ticket_id": ticket["ticket_id"],
        "rfp_id": ticket["rfp_id"],
        "status": "analyzing",
        "created_at": ticket["created_at"],
    })
    background_tasks.add_task(_run_background, ticket["ticket_id"], str(target), repository)
    return {
        "ticket_id": ticket["ticket_id"],
        "status": "analyzing",
        "status_url": f"/api/rfps/{ticket['ticket_id']}",
    }


@router.get("")
def list_rfps(
    repository: Annotated[RfpRepository, Depends(repository_dependency)],
) -> list[dict[str, Any]]:
    return repository.list_tickets()


@router.get("/events", response_class=StreamingResponse)
async def get_rfp_events(
    request: Request,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    try:
        cursor = max(0, int(last_event_id or "0"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Last-Event-ID no es válido.") from exc
    return StreamingResponse(
        stream_rfp_events(request, cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{ticket_id}/draft", status_code=status.HTTP_202_ACCEPTED)
def draft_rfp_response(
    ticket_id: str,
    background_tasks: BackgroundTasks,
    repository: Annotated[RfpRepository, Depends(repository_dependency)],
) -> dict[str, str]:
    if repository.get_ticket(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket RFP no encontrado.")
    try:
        repository.start_drafting(ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(_run_drafting, ticket_id, repository)
    return {
        "ticket_id": ticket_id,
        "status": "drafting",
        "status_url": f"/api/rfps/{ticket_id}",
    }


@router.post("/{ticket_id}/approvals/start")
def start_rfp_approvals(
    ticket_id: str,
    repository: Annotated[RfpRepository, Depends(repository_dependency)],
    runtime: Annotated[ApprovalWorkflowRuntime, Depends(approval_runtime_dependency)],
) -> dict[str, Any]:
    if repository.get_ticket(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket RFP no encontrado.")
    try:
        ticket = repository.start_approvals(ticket_id)
        branches = [runtime.start_branch(ticket, section) for section in ticket["sections"]]
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "ticket_id": ticket_id,
        "status": "waiting_for_approval",
        "branches": [item.model_dump(mode="json") for item in branches],
    }


@router.post("/{ticket_id}/approvals/{department_id}/resume")
def resume_rfp_approval(
    ticket_id: str,
    department_id: DepartmentId,
    decision: ApprovalDecisionRequest,
    repository: Annotated[RfpRepository, Depends(repository_dependency)],
    runtime: Annotated[ApprovalWorkflowRuntime, Depends(approval_runtime_dependency)],
) -> dict[str, Any]:
    ticket = repository.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket RFP no encontrado.")
    if not any(section["department_id"] == department_id for section in ticket["sections"]):
        raise HTTPException(status_code=404, detail="Departamento no activo en este ticket.")
    try:
        branch = runtime.resume_branch(ticket_id, department_id, decision, ticket=ticket)
        repository.save_approval_branch(branch)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    refreshed = repository.get_ticket(ticket_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Ticket RFP no encontrado.")
    document = None
    if refreshed["sections"] and all(
        section.get("approval_status") == "approved" for section in refreshed["sections"]
    ):
        final_document = generate_final_document(refreshed, FINAL_DIR)
        repository.save_final_document(final_document)
        document = final_document.model_dump(mode="json")
        ticket_status = "done"
    else:
        ticket_status = "waiting_for_approval"
    return {
        "ticket_id": ticket_id,
        "status": ticket_status,
        "branch": branch.model_dump(mode="json"),
        "final_document": document,
    }


@router.get("/{ticket_id}/approvals/trace")
def get_rfp_approval_trace(
    ticket_id: str,
    repository: Annotated[RfpRepository, Depends(repository_dependency)],
    runtime: Annotated[ApprovalWorkflowRuntime, Depends(approval_runtime_dependency)],
) -> dict[str, Any]:
    ticket = repository.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket RFP no encontrado.")
    branches: list[dict[str, Any]] = []
    for section in ticket["sections"]:
        try:
            branches.append(runtime.branch_state(ticket_id, section["department_id"]).model_dump(mode="json"))
        except KeyError:
            continue
    return {"ticket_id": ticket_id, "branches": branches}


@router.get("/{ticket_id}/final")
def get_rfp_final_document(
    ticket_id: str,
    repository: Annotated[RfpRepository, Depends(repository_dependency)],
) -> dict[str, Any]:
    if repository.get_ticket(ticket_id) is None:
        raise HTTPException(status_code=404, detail="Ticket RFP no encontrado.")
    document = repository.get_final_document(ticket_id)
    if document is None:
        raise HTTPException(status_code=409, detail="El documento final todavía no está disponible.")
    return document


@router.get("/{ticket_id}")
def get_rfp(
    ticket_id: str,
    repository: Annotated[RfpRepository, Depends(repository_dependency)],
) -> dict[str, Any]:
    ticket = repository.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket RFP no encontrado.")
    return ticket
