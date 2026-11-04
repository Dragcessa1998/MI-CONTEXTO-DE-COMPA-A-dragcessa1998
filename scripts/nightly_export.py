#!/usr/bin/env python3
"""Exporta telemetría UTC diaria y dispara el pipeline como proceso independiente."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.job_runner import ClaimOutcome, JobRunRepository
from services.job_runner.exporter import export_telemetry_csv


JOB_NAME = "nightly_export"
DEFAULT_RAW_DIRECTORY = ROOT / "data" / "raw"


def configure_logger() -> logging.Logger:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)sZ level=%(levelname)s job=%(job_name)s status=%(status)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logger = logging.getLogger(JOB_NAME)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log(logger: logging.Logger, level: int, status: str, message: str) -> None:
    logger.log(level, message, extra={"job_name": JOB_NAME, "status": status})


def resolve_target_date(raw: str | None = None) -> date:
    value = raw if raw is not None else os.getenv("TARGET_DATE")
    if value is None:
        return datetime.now(timezone.utc).date() - timedelta(days=1)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("TARGET_DATE debe usar YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("TARGET_DATE debe usar YYYY-MM-DD")
    return parsed


def _safe_error(error: BaseException) -> str:
    message = " ".join(str(error).split())
    message = re.sub(r"(?i)(password|token|secret)=([^\s&]+)", r"\1=[REDACTED]", message)
    message = re.sub(r"(postgres(?:ql)?://)[^@\s]+@", r"\1[REDACTED]@", message)
    return (message or error.__class__.__name__)[:1000]


def pipeline_command() -> list[str]:
    raw = os.getenv("PIPELINE_COMMAND_JSON")
    if raw is None:
        return [sys.executable, "-m", "services.reporting.weekly_pipeline"]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("PIPELINE_COMMAND_JSON debe ser un array JSON") from exc
    if not isinstance(parsed, list) or not parsed or not all(isinstance(item, str) and item for item in parsed):
        raise ValueError("PIPELINE_COMMAND_JSON debe ser un array JSON de strings")
    return parsed


def run() -> int:
    logger = configure_logger()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        log(logger, logging.ERROR, "failed", "DATABASE_URL no está configurado")
        return 1

    try:
        target_date = resolve_target_date()
        stale_minutes = int(os.getenv("JOB_STALE_AFTER_MINUTES", "360"))
        if stale_minutes <= 0:
            raise ValueError("JOB_STALE_AFTER_MINUTES debe ser positivo")
        repository = JobRunRepository(database_url)
        log(logger, logging.INFO, "pending", f"target_date={target_date.isoformat()} acquiring")
        claim = repository.claim(
            JOB_NAME,
            target_date,
            stale_after=timedelta(minutes=stale_minutes),
        )
    except BaseException as error:
        log(logger, logging.ERROR, "failed", _safe_error(error))
        return 1

    if claim.outcome is ClaimOutcome.ALREADY_PROCESSING:
        log(logger, logging.INFO, "processing", "skipped reason=already_running")
        return 0
    if claim.outcome is ClaimOutcome.ALREADY_COMPLETED:
        log(
            logger,
            logging.INFO,
            "completed",
            f"skipped reason=duplicate target_date={target_date.isoformat()}",
        )
        return 0

    assert claim.run_id is not None
    run_id = claim.run_id
    log(logger, logging.INFO, "processing", f"run_id={run_id} started")
    try:
        raw_directory = Path(os.getenv("RAW_DATA_DIR", str(DEFAULT_RAW_DIRECTORY))).resolve()
        csv_path, row_count, created = export_telemetry_csv(
            database_url,
            target_date,
            raw_directory,
        )
        log(
            logger,
            logging.INFO,
            "processing",
            f"csv={csv_path.name} rows={row_count} action={'created' if created else 'reused'}",
        )
        environment = os.environ.copy()
        environment["TARGET_DATE"] = target_date.isoformat()
        completed = subprocess.run(
            pipeline_command(),
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        if completed.stdout.strip():
            log(
                logger,
                logging.INFO,
                "processing",
                f"pipeline={_safe_error(RuntimeError(completed.stdout.strip()))}",
            )
        repository.update_status(run_id, "completed")
        log(logger, logging.INFO, "completed", f"run_id={run_id} finished")
        return 0
    except BaseException as error:
        message = _safe_error(error)
        try:
            repository.update_status(run_id, "failed", error_message=message)
        except BaseException as transition_error:
            transition_message = _safe_error(transition_error)
            log(
                logger,
                logging.ERROR,
                "failed",
                f"run_id={run_id} error={message} status_update_error={transition_message}",
            )
            return 1
        log(logger, logging.ERROR, "failed", f"run_id={run_id} error={message}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
