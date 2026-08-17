"""Durable dead-letter storage for exhausted background jobs."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DLQ_PATH = Path(__file__).resolve().parent / "task_failures.sqlite3"


def _database_path() -> Path:
    return Path(os.getenv("TASK_DLQ_DB", str(DEFAULT_DLQ_PATH)))


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS task_failures (
            task_id TEXT PRIMARY KEY,
            attempt INTEGER NOT NULL,
            error TEXT NOT NULL,
            failed_at TEXT NOT NULL
        )
        """
    )
    return connection


def record_terminal_failure(*, task_id: str, attempt: int, error: str) -> None:
    """Insert or update the terminal failure without storing task payloads."""

    safe_error = error.strip()[:500] or "unknown_error"
    failed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO task_failures (task_id, attempt, error, failed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                attempt = excluded.attempt,
                error = excluded.error,
                failed_at = excluded.failed_at
            """,
            (task_id, attempt, safe_error, failed_at),
        )


def get_terminal_failure(task_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT task_id, attempt, error, failed_at
            FROM task_failures
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()
    return dict(row) if row is not None else None

