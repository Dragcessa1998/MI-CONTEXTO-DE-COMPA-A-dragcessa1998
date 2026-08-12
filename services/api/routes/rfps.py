"""Recepción asíncrona y consulta de tickets RFP en el backend existente."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status

from data.pipelines.rfp_intake import run_rfp_intake
from rfp_repository import RfpRepository, get_rfp_repository
from security import get_current_user


REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = Path(os.getenv("RFP_RAW_DIR", str(REPO_ROOT / "data" / "raw" / "rfps"))).resolve()
MAX_PDF_BYTES = 10 * 1024 * 1024

router = APIRouter(
    prefix="/api/rfps",
    tags=["rfp-intake"],
    dependencies=[Depends(get_current_user)],
)


def repository_dependency() -> RfpRepository:
    return get_rfp_repository()


def _run_background(ticket_id: str, raw_pdf_path: str, repository: RfpRepository) -> None:
    try:
        repository.save_result(ticket_id, run_rfp_intake(Path(raw_pdf_path)))
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
    background_tasks.add_task(_run_background, ticket["ticket_id"], str(target), repository)
    return {
        "ticket_id": ticket["ticket_id"],
        "status": "analizando",
        "status_url": f"/api/rfps/{ticket['ticket_id']}",
    }


@router.get("")
def list_rfps(
    repository: Annotated[RfpRepository, Depends(repository_dependency)],
) -> list[dict[str, Any]]:
    return repository.list_tickets()


@router.get("/{ticket_id}")
def get_rfp(
    ticket_id: str,
    repository: Annotated[RfpRepository, Depends(repository_dependency)],
) -> dict[str, Any]:
    ticket = repository.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket RFP no encontrado.")
    return ticket
