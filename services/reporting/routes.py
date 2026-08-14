"""Authenticated HTTP boundary for the weekly business pipeline."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from nexova_pipelines.pipeline import (
    PipelineConflict,
    PipelineStoreError,
    get_latest_pipeline_run,
    get_weekly_office_program_performance,
    reserve_manual_run,
    start_weekly_office_program_performance_run,
)
from pydantic import BaseModel, ConfigDict


logger = logging.getLogger(__name__)

# ``security`` belongs to the host API. Keeping this import at the HTTP boundary
# avoids coupling the reusable pipeline package to authentication concerns.
from security import get_current_user  # noqa: E402
from auth_models import UserRecord  # noqa: E402


router = APIRouter(
    prefix="/reporting",
    tags=["reporting"],
    dependencies=[Depends(get_current_user)],
)


class ManualRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: date | None = None


def _run_in_background(week_start: str, requested_by: str, run_id: str) -> None:
    try:
        start_weekly_office_program_performance_run(
            week_start=week_start,
            requested_by=requested_by,
            run_id=run_id,
        )
    except Exception:
        # The flow has already written safe FAILED metadata. Do not leak its
        # payload or credentials through the ASGI background-task boundary.
        logger.exception("reporting_pipeline_background_run_failed run_id=%s", run_id)


@router.get("/pipeline-runs/latest")
def latest_pipeline_run() -> dict[str, Any]:
    try:
        run = get_latest_pipeline_run()
    except PipelineStoreError as exc:
        raise HTTPException(status_code=503, detail="Reporting data is unavailable") from exc
    if run is None:
        raise HTTPException(status_code=404, detail="No pipeline run is available")
    return run


@router.post("/pipeline-runs", status_code=status.HTTP_202_ACCEPTED)
def create_pipeline_run(
    payload: ManualRunRequest,
    background_tasks: BackgroundTasks,
    current_user: UserRecord = Depends(get_current_user),
) -> dict[str, str]:
    try:
        run_id, week_start = reserve_manual_run(
            payload.week_start.isoformat() if payload.week_start else None,
            requested_by=str(current_user.id),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PipelineConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={"message": "A run for this week is already active", "run_id": str(exc)},
        ) from exc
    except PipelineStoreError as exc:
        raise HTTPException(status_code=503, detail="Reporting data is unavailable") from exc

    background_tasks.add_task(
        _run_in_background,
        week_start,
        str(current_user.id),
        run_id,
    )
    return {"run_id": run_id, "week_start": week_start, "status": "PENDING"}


@router.get("/weekly-office-program-performance")
def weekly_office_program_performance(
    week_start: date | None = None,
) -> dict[str, Any]:
    if week_start is not None and week_start.weekday() != 0:
        raise HTTPException(status_code=422, detail="week_start must be an ISO Monday")
    try:
        return get_weekly_office_program_performance(
            week_start.isoformat() if week_start else None
        )
    except PipelineStoreError as exc:
        raise HTTPException(status_code=503, detail="Reporting data is unavailable") from exc
