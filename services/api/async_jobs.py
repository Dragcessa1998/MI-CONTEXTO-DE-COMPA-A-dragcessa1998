"""Background jobs executed by a dedicated Celery worker."""

from __future__ import annotations

import logging
from time import monotonic
from typing import Any

from nexova_pipelines.pipeline import start_weekly_office_program_performance_run

from celery_app import celery_app
from task_store import record_terminal_failure


logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="nexova.reporting.run_weekly_pipeline",
    max_retries=3,
)
def run_reporting_pipeline_task(
    self: Any,
    week_start: str,
    requested_by: str,
    run_id: str,
) -> dict[str, Any]:
    """Run the reporting pipeline with bounded exponential retries."""

    task_id = str(self.request.id or run_id)
    attempt = int(self.request.retries) + 1
    started_at = monotonic()
    logger.info(
        "task_id=%s attempt=%s status=started",
        task_id,
        attempt,
    )
    try:
        result = start_weekly_office_program_performance_run(
            week_start=week_start,
            requested_by=requested_by,
            run_id=run_id,
        )
    except Exception as exc:
        duration_ms = round((monotonic() - started_at) * 1000, 2)
        error_code = type(exc).__name__
        if int(self.request.retries) < int(self.max_retries):
            countdown = 2 ** int(self.request.retries)
            logger.warning(
                "task_id=%s attempt=%s status=retry duration_ms=%s error=%s countdown_s=%s",
                task_id,
                attempt,
                duration_ms,
                error_code,
                countdown,
            )
            raise self.retry(exc=exc, countdown=countdown) from exc

        logger.error(
            "task_id=%s attempt=%s status=failed duration_ms=%s error=%s",
            task_id,
            attempt,
            duration_ms,
            error_code,
        )
        record_terminal_failure(
            task_id=task_id,
            attempt=attempt,
            error=error_code,
        )
        raise

    duration_ms = round((monotonic() - started_at) * 1000, 2)
    logger.info(
        "task_id=%s attempt=%s status=success duration_ms=%s",
        task_id,
        attempt,
        duration_ms,
    )
    return result

