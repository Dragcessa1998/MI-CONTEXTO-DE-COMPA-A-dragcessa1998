"""Almacén local consultable de trazas estructuradas del agente."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from typing import Any


@dataclass
class TraceRun:
    run_id: str
    started_at: str
    events: list[dict[str, Any]] = field(default_factory=list)
    completed_at: str | None = None


class TraceStore:
    def __init__(self, max_runs: int = 200) -> None:
        self._max_runs = max_runs
        self._runs: dict[str, TraceRun] = {}
        self._lock = Lock()

    def start(self, run_id: str) -> None:
        with self._lock:
            self._runs[run_id] = TraceRun(
                run_id=run_id,
                started_at=datetime.now(UTC).isoformat(),
            )
            while len(self._runs) > self._max_runs:
                self._runs.pop(next(iter(self._runs)))

    def append(self, run_id: str, node: str, output: dict[str, Any]) -> None:
        event = {
            "sequence": 0,
            "node": node,
            "output": deepcopy(output),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            run = self._runs[run_id]
            event["sequence"] = len(run.events) + 1
            run.events.append(event)

    def complete(self, run_id: str) -> None:
        with self._lock:
            self._runs[run_id].completed_at = datetime.now(UTC).isoformat()

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            return deepcopy(run.__dict__) if run else None

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()


trace_store = TraceStore()
