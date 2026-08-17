"""Acceptance coverage for the Redis/Celery task boundary."""

from __future__ import annotations

from time import monotonic

import routes.tasks as task_routes
from async_jobs import run_reporting_pipeline_task
from task_store import get_terminal_failure, record_terminal_failure


class _QueuedTask:
    def __init__(self, task_id: str) -> None:
        self.id = task_id


def test_reporting_request_queues_lightweight_identifiers_under_200ms(
    client, monkeypatch
) -> None:
    observed: dict[str, object] = {}

    def fake_apply_async(*, args, task_id):
        observed.update(args=args, task_id=task_id)
        return _QueuedTask(task_id)

    monkeypatch.setattr(run_reporting_pipeline_task, "apply_async", fake_apply_async)

    started_at = monotonic()
    response = client.post(
        "/reporting/pipeline-runs",
        json={"week_start": "2026-08-03"},
    )
    elapsed = monotonic() - started_at

    assert response.status_code == 202
    assert elapsed < 0.2
    assert response.json()["task_id"] == response.json()["run_id"]
    assert observed["task_id"] == response.json()["task_id"]
    assert observed["args"][0] == "2026-08-03"
    assert len(observed["args"]) == 3


def test_task_status_contract_for_started_and_success(client, monkeypatch) -> None:
    class FakeResult:
        state = "STARTED"
        result = None

        def successful(self):
            return False

        def failed(self):
            return False

    monkeypatch.setattr(task_routes, "AsyncResult", lambda *_args, **_kwargs: FakeResult())
    started = client.get("/tasks/task-123")
    assert started.status_code == 200
    assert started.json() == {"task_id": "task-123", "status": "started"}

    FakeResult.state = "SUCCESS"
    FakeResult.result = {"records_loaded": 2}
    FakeResult.successful = lambda self: True
    completed = client.get("/tasks/task-123")
    assert completed.json() == {
        "task_id": "task-123",
        "status": "success",
        "result": {"records_loaded": 2},
    }


def test_terminal_failure_is_persisted_in_sqlite(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "dlq.sqlite3"
    monkeypatch.setenv("TASK_DLQ_DB", str(database_path))

    record_terminal_failure(task_id="failed-task", attempt=4, error="TimeoutError")
    failure = get_terminal_failure("failed-task")

    assert failure is not None
    assert failure["task_id"] == "failed-task"
    assert failure["attempt"] == 4
    assert failure["error"] == "TimeoutError"
    assert failure["failed_at"].endswith("Z")
    assert run_reporting_pipeline_task.max_retries == 3
