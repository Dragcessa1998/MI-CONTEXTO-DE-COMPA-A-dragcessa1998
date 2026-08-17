"""Authenticated task-status API backed by Celery's Redis result store."""

from __future__ import annotations

from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends

from celery_app import celery_app
from security import get_current_user
from task_store import get_terminal_failure


router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/{task_id}")
def task_status(task_id: str) -> dict[str, Any]:
    """Return a stable status contract without exposing exception payloads."""

    task = AsyncResult(task_id, app=celery_app)
    state = task.state.lower()
    response: dict[str, Any] = {"task_id": task_id, "status": state}
    if task.successful():
        response["result"] = task.result
    elif task.failed():
        failure = get_terminal_failure(task_id)
        response["error"] = failure["error"] if failure else "task_failed"
    return response

