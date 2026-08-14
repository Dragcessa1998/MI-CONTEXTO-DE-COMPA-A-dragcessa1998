"""Resilient weekly business-performance pipeline for Nexova.

Run from the monorepo root after syncing the API environment:

    services/api/.venv/bin/python data/pipelines/pipeline.py

Production reads ``public.telemetry_events`` and publishes into
``reporting.weekly_office_program_performance``. Without Supabase credentials,
the same flow uses the synthetic export in ``data/raw`` and a local reporting
mirror in ``data/eval`` so the complete CLI remains reproducible offline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid4, uuid5

import pandas as pd
from prefect import flow, task
from prefect.tasks import task_input_hash


PIPELINE_NAME = "weekly_office_program_performance"
EVENT_TYPES = (
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "kit_cost_variance_detected",
)
OFFICE_CURRENCIES = {"valencia": "EUR", "miami": "USD"}
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_PATH = REPO_ROOT / "data" / "raw" / "telemetry_events.sample.json"
DEFAULT_STATE_DIR = REPO_ROOT / "data" / "eval"
_local_file_lock = Lock()


class PipelineConflict(RuntimeError):
    """A run for the requested ISO week is already pending or running."""


class PipelineStoreError(RuntimeError):
    """A storage dependency failed without exposing credentials or payloads."""


class PipelineStore(Protocol):
    def extract_events(
        self, window_start: datetime, window_end: datetime
    ) -> list[dict[str, Any]]: ...

    def write_run(self, run: dict[str, Any]) -> None: ...

    def reserve_run(self, run: dict[str, Any]) -> None: ...

    def write_inputs(self, run_id: str, inputs: list[dict[str, Any]]) -> None: ...

    def publish_rows(self, week_start: str, rows: list[dict[str, Any]]) -> int: ...

    def latest_run(self) -> dict[str, Any] | None: ...

    def read_rows(self, week_start: str | None) -> tuple[str | None, list[dict[str, Any]]]: ...


def _iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_week_start(value: str | date | None) -> date:
    """Return an ISO Monday; the default is the last completed UTC week."""

    if value is None:
        today = _utc_now().date()
        return today - timedelta(days=today.weekday() + 7)
    resolved = date.fromisoformat(value) if isinstance(value, str) else value
    if resolved.weekday() != 0:
        raise ValueError("week_start must be an ISO Monday")
    return resolved


def _week_window(week_start: str | date | None) -> tuple[date, datetime, datetime]:
    resolved = resolve_week_start(week_start)
    start = datetime.combine(resolved, datetime.min.time(), tzinfo=timezone.utc)
    return resolved, start, start + timedelta(days=7)


def _stable_checksum(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _safe_error_code(exc: BaseException) -> str:
    name = type(exc).__name__.lower()
    return "".join(character for character in name if character.isalnum() or character == "_")[:80]


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise PipelineStoreError("local_json_must_be_an_array_of_objects")
    return value


def _atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class LocalPipelineStore:
    """Offline mirror of the source and reporting tables for deterministic CLI runs."""

    def __init__(self) -> None:
        self.source_path = Path(os.getenv("PIPELINE_LOCAL_SOURCE", str(DEFAULT_SOURCE_PATH)))
        self.state_dir = Path(os.getenv("PIPELINE_STATE_DIR", str(DEFAULT_STATE_DIR)))
        self.runs_path = self.state_dir / "pipeline_runs.local.json"
        self.inputs_path = self.state_dir / "pipeline_run_inputs.local.json"
        self.rows_path = self.state_dir / "weekly_office_program_performance.local.json"

    def extract_events(self, window_start: datetime, window_end: datetime) -> list[dict[str, Any]]:
        events = _read_json_list(self.source_path)
        selected: list[dict[str, Any]] = []
        for event in events:
            raw_timestamp = event.get("timestamp")
            if not isinstance(raw_timestamp, str):
                selected.append(event)
                continue
            try:
                parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
            except ValueError:
                selected.append(event)
                continue
            if parsed.tzinfo is None:
                selected.append(event)
                continue
            if window_start <= parsed.astimezone(timezone.utc) < window_end:
                selected.append(event)
        return selected

    def _runs(self) -> list[dict[str, Any]]:
        return _read_json_list(self.runs_path)

    def write_run(self, run: dict[str, Any]) -> None:
        with _local_file_lock:
            runs = self._runs()
            replaced = False
            for index, existing in enumerate(runs):
                if existing.get("run_id") == run["run_id"]:
                    runs[index] = dict(run)
                    replaced = True
                    break
            if not replaced:
                active = next(
                    (
                        item
                        for item in runs
                        if item.get("pipeline_name") == PIPELINE_NAME
                        and item.get("week_start") == run["week_start"]
                        and item.get("status") in {"PENDING", "RUNNING"}
                    ),
                    None,
                )
                if active is not None and run.get("status") in {"PENDING", "RUNNING"}:
                    raise PipelineConflict(str(active.get("run_id", "active")))
                runs.append(dict(run))
            _atomic_write_json(self.runs_path, runs)

    def reserve_run(self, run: dict[str, Any]) -> None:
        with _local_file_lock:
            runs = self._runs()
            active = next(
                (
                    item
                    for item in runs
                    if item.get("pipeline_name") == PIPELINE_NAME
                    and item.get("week_start") == run["week_start"]
                    and item.get("status") in {"PENDING", "RUNNING"}
                ),
                None,
            )
            if active is not None:
                raise PipelineConflict(str(active.get("run_id", "active")))
            runs.append(dict(run))
            _atomic_write_json(self.runs_path, runs)

    def write_inputs(self, run_id: str, inputs: list[dict[str, Any]]) -> None:
        with _local_file_lock:
            existing = _read_json_list(self.inputs_path)
            retained = [item for item in existing if item.get("run_id") != run_id]
            _atomic_write_json(
                self.inputs_path,
                retained + [{"run_id": run_id, **item} for item in inputs],
            )

    def publish_rows(self, week_start: str, rows: list[dict[str, Any]]) -> int:
        with _local_file_lock:
            existing = _read_json_list(self.rows_path)
            retained = [item for item in existing if item.get("week_start") != week_start]
            computed_at = _iso_z(_utc_now())
            published = [
                {
                    "id": str(
                        uuid5(
                            NAMESPACE_URL,
                            f"nexova:{row['office']}:{row['programme_id']}:{week_start}",
                        )
                    ),
                    **row,
                    "computed_at": computed_at,
                }
                for row in rows
            ]
            _atomic_write_json(
                self.rows_path,
                sorted(
                    retained + published,
                    key=lambda item: (
                        str(item.get("week_start", "")),
                        str(item.get("office", "")),
                        str(item.get("programme_id", "")),
                    ),
                ),
            )
            return len(published)

    def latest_run(self) -> dict[str, Any] | None:
        runs = [item for item in self._runs() if item.get("pipeline_name") == PIPELINE_NAME]
        if not runs:
            return None
        return max(runs, key=lambda item: str(item.get("started_at", "")))

    def read_rows(self, week_start: str | None) -> tuple[str | None, list[dict[str, Any]]]:
        rows = _read_json_list(self.rows_path)
        if week_start is None:
            completed = [str(item.get("week_start")) for item in rows if item.get("week_start")]
            week_start = max(completed) if completed else None
        selected = [item for item in rows if item.get("week_start") == week_start]
        public_fields = {
            "office",
            "programme_id",
            "total_material_cost",
            "kits_delivered_count",
            "shortage_events_count",
            "cost_variance_events_count",
            "currency",
        }
        return week_start, [
            {key: value for key, value in item.items() if key in public_fields}
            for item in selected
        ]


class SupabasePipelineStore:
    """PostgREST adapter; credentials remain server-side and out of logs."""

    def __init__(self) -> None:
        self.base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.base_url or not self.service_key:
            raise PipelineStoreError("supabase_reporting_is_not_configured")

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: object | None = None,
        schema: str | None = None,
        prefer: str | None = None,
    ) -> Any:
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }
        if schema:
            headers["Accept-Profile"] = schema
            headers["Content-Profile"] = schema
        if prefer:
            headers["Prefer"] = prefer
        request = Request(
            f"{self.base_url}/rest/v1/{path}",
            data=None if body is None else json.dumps(body).encode("utf-8"),
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=20) as response:
                payload = response.read()
        except HTTPError as exc:
            raise PipelineStoreError(f"supabase_http_{exc.code}") from exc
        except URLError as exc:
            raise PipelineStoreError("supabase_unavailable") from exc
        if not payload:
            return None
        return json.loads(payload.decode("utf-8"))

    def extract_events(self, window_start: datetime, window_end: datetime) -> list[dict[str, Any]]:
        page_size = 1000
        offset = 0
        events: list[dict[str, Any]] = []
        while True:
            query = urlencode(
                {
                    "select": "id,timestamp,event_type,tags",
                    "timestamp": f"gte.{_iso_z(window_start)}",
                    "event_type": f"in.({','.join(EVENT_TYPES)})",
                    "order": "timestamp.asc,id.asc",
                    "limit": str(page_size),
                    "offset": str(offset),
                }
            )
            # PostgREST accepts a second filter for the same column in the URL.
            query += "&" + urlencode({"timestamp": f"lt.{_iso_z(window_end)}"})
            page = self._request(f"telemetry_events?{query}")
            if not isinstance(page, list):
                raise PipelineStoreError("invalid_telemetry_response")
            events.extend(item for item in page if isinstance(item, dict))
            if len(page) < page_size:
                return events
            offset += page_size

    def write_run(self, run: dict[str, Any]) -> None:
        query = urlencode({"on_conflict": "run_id"})
        self._request(
            f"pipeline_runs?{query}",
            method="POST",
            body=[run],
            schema="reporting",
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def reserve_run(self, run: dict[str, Any]) -> None:
        try:
            self._request(
                "pipeline_runs",
                method="POST",
                body=[run],
                schema="reporting",
                prefer="return=minimal",
            )
        except PipelineStoreError as exc:
            if str(exc) == "supabase_http_409":
                raise PipelineConflict("active") from exc
            raise

    def write_inputs(self, run_id: str, inputs: list[dict[str, Any]]) -> None:
        if not inputs:
            return
        rows = [{"run_id": run_id, **item} for item in inputs]
        query = urlencode({"on_conflict": "run_id,event_id"})
        self._request(
            f"pipeline_run_inputs?{query}",
            method="POST",
            body=rows,
            schema="reporting",
            prefer="resolution=merge-duplicates,return=minimal",
        )

    def publish_rows(self, week_start: str, rows: list[dict[str, Any]]) -> int:
        result = self._request(
            "rpc/publish_weekly_office_program_performance",
            method="POST",
            body={"p_week_start": week_start, "p_rows": rows},
            schema="reporting",
        )
        return int(result or 0)

    def latest_run(self) -> dict[str, Any] | None:
        query = urlencode(
            {
                "select": "*",
                "pipeline_name": f"eq.{PIPELINE_NAME}",
                "order": "started_at.desc",
                "limit": "1",
            }
        )
        rows = self._request(f"pipeline_runs?{query}", schema="reporting")
        return rows[0] if isinstance(rows, list) and rows else None

    def read_rows(self, week_start: str | None) -> tuple[str | None, list[dict[str, Any]]]:
        if week_start is None:
            latest_query = urlencode(
                {"select": "week_start", "order": "week_start.desc", "limit": "1"}
            )
            latest = self._request(
                f"weekly_office_program_performance?{latest_query}", schema="reporting"
            )
            week_start = (
                str(latest[0]["week_start"])
                if isinstance(latest, list) and latest
                else None
            )
        if week_start is None:
            return None, []
        fields = (
            "office,programme_id,total_material_cost,kits_delivered_count,"
            "shortage_events_count,cost_variance_events_count,currency"
        )
        query = urlencode(
            {
                "select": fields,
                "week_start": f"eq.{week_start}",
                "order": "office.asc,programme_id.asc",
            }
        )
        rows = self._request(
            f"weekly_office_program_performance?{query}", schema="reporting"
        )
        return week_start, rows if isinstance(rows, list) else []


def get_store() -> PipelineStore:
    backend = os.getenv("PIPELINE_BACKEND", "").strip().lower()
    if backend == "local":
        return LocalPipelineStore()
    if backend == "supabase" or (
        os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    ):
        return SupabasePipelineStore()
    return LocalPipelineStore()


def transform_events(events: list[dict[str, Any]], week_start: str) -> dict[str, Any]:
    """Validate, deduplicate and aggregate the exact four Nexova KPIs."""

    resolved, window_start, window_end = _week_window(week_start)
    accepted: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    duplicates = 0
    rejected = 0

    for event in events:
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            rejected += 1
            continue
        if event_id in seen_ids:
            duplicates += 1
            continue
        seen_ids.add(event_id)

        event_type = event.get("event_type")
        tags = event.get("tags")
        raw_timestamp = event.get("timestamp")
        if (
            event_type not in EVENT_TYPES
            or not isinstance(tags, dict)
            or not isinstance(raw_timestamp, str)
        ):
            rejected += 1
            continue
        try:
            parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        except ValueError:
            rejected += 1
            continue
        if parsed.tzinfo is None:
            rejected += 1
            continue
        occurred_at = parsed.astimezone(timezone.utc)
        if not window_start <= occurred_at < window_end:
            rejected += 1
            continue

        office = tags.get("office")
        programme_id = tags.get("programme_id")
        currency = tags.get("currency")
        if (
            not isinstance(office, str)
            or not isinstance(programme_id, str)
            or not programme_id
            or currency != OFFICE_CURRENCIES.get(office)
        ):
            rejected += 1
            continue

        material_cost = 0.0
        if event_type == "inbound_order_created":
            quantity = tags.get("quantity")
            unit_cost = tags.get("unit_cost")
            if (
                not isinstance(quantity, int)
                or isinstance(quantity, bool)
                or quantity <= 0
                or not isinstance(unit_cost, (int, float))
                or isinstance(unit_cost, bool)
                or float(unit_cost) < 0
            ):
                rejected += 1
                continue
            material_cost = float(quantity) * float(unit_cost)

        accepted.append(
            {
                "id": event_id,
                "request_id": (
                    tags.get("request_id")
                    if isinstance(tags.get("request_id"), str)
                    else None
                ),
                "timestamp": _iso_z(occurred_at),
                "event_type": event_type,
                "office": office,
                "programme_id": programme_id,
                "week_start": resolved.isoformat(),
                "currency": currency,
                "material_cost": material_cost,
                "kits_delivered_count": int(event_type == "outbound_order_created"),
                "shortage_events_count": int(event_type == "stock_threshold_triggered"),
                "cost_variance_events_count": int(
                    event_type == "kit_cost_variance_detected"
                ),
            }
        )

    if not accepted:
        rows: list[dict[str, Any]] = []
    else:
        frame = pd.DataFrame.from_records(accepted)
        rows = (
            frame.groupby(
                ["office", "programme_id", "week_start", "currency"],
                as_index=False,
                sort=True,
            )
            .agg(
                total_material_cost=("material_cost", "sum"),
                kits_delivered_count=("kits_delivered_count", "sum"),
                shortage_events_count=("shortage_events_count", "sum"),
                cost_variance_events_count=("cost_variance_events_count", "sum"),
            )
            .sort_values(["office", "programme_id"], kind="stable")
            .to_dict(orient="records")
        )
        for row in rows:
            row["total_material_cost"] = round(float(row["total_material_cost"]), 2)
            for field in (
                "kits_delivered_count",
                "shortage_events_count",
                "cost_variance_events_count",
            ):
                row[field] = int(row[field])

    source_evidence = [
        {key: item[key] for key in ("id", "timestamp", "event_type")}
        for item in sorted(accepted, key=lambda item: (item["timestamp"], item["id"]))
    ]
    return {
        "rows": rows,
        "inputs": [
            {
                "event_id": item["id"],
                "request_id": item["request_id"],
                "event_timestamp": item["timestamp"],
            }
            for item in accepted
        ],
        "records_extracted": len(events),
        "records_deduplicated": duplicates,
        "records_rejected": rejected,
        "source_checksum": _stable_checksum(source_evidence),
        "output_checksum": _stable_checksum(rows),
    }


# External storage calls get three attempts: the first normal call plus enough
# retries to absorb two short transient outages without hiding a sustained one.
@task(retries=3, retry_delay_seconds=2)
def persist_pipeline_run_task(run: dict[str, Any]) -> None:
    get_store().write_run(run)


@task(retries=3, retry_delay_seconds=2)
def extract_telemetry_events_task(window_start: str, window_end: str) -> list[dict[str, Any]]:
    start = datetime.fromisoformat(window_start.replace("Z", "+00:00"))
    end = datetime.fromisoformat(window_end.replace("Z", "+00:00"))
    return get_store().extract_events(start, end)


# The full input list and ISO week define the cache key. Identical inputs may be
# reused for one hour; changed or late events produce a different hash.
@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=1))
def transform_weekly_office_program_performance_task(
    events: list[dict[str, Any]], week_start: str
) -> dict[str, Any]:
    return transform_events(events, week_start)


@task(retries=3, retry_delay_seconds=2)
def persist_pipeline_inputs_task(run_id: str, inputs: list[dict[str, Any]]) -> None:
    get_store().write_inputs(run_id, inputs)


@task(retries=3, retry_delay_seconds=2)
def load_weekly_office_program_performance_task(
    week_start: str, rows: list[dict[str, Any]]
) -> int:
    return get_store().publish_rows(week_start, rows)


@task
def write_eval_snapshot_task(
    week_start: str, run_id: str, rows: list[dict[str, Any]]
) -> str:
    """Optional secondary artifact; its failure must not block publication."""

    if os.getenv("PIPELINE_FAIL_EVAL_SNAPSHOT") == "1":
        raise RuntimeError("optional_snapshot_failed")
    state_dir = Path(os.getenv("PIPELINE_STATE_DIR", str(DEFAULT_STATE_DIR)))
    destination = state_dir / f"weekly_performance.{week_start}.{run_id}.json"
    _atomic_write_json(destination, rows)
    return str(destination)


def _base_run(
    *,
    run_id: str,
    week_start: date,
    window_start: datetime,
    window_end: datetime,
    trigger_source: str,
    requested_by: str | None,
    status: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "pipeline_name": PIPELINE_NAME,
        "trigger_source": trigger_source,
        "requested_by": requested_by,
        "week_start": week_start.isoformat(),
        "window_start": _iso_z(window_start),
        "window_end": _iso_z(window_end),
        "started_at": _iso_z(_utc_now()),
        "finished_at": None,
        "status": status,
        "phase": "start",
        "source_cursor": None,
        "records_extracted": 0,
        "records_deduplicated": 0,
        "records_rejected": 0,
        "records_loaded": 0,
        "source_checksum": None,
        "output_checksum": None,
        "error_code": None,
        "invalidates_run_id": None,
    }


@flow(name="build-weekly-office-program-performance", log_prints=True)
def build_weekly_office_program_performance(
    week_start: str | None = None,
    trigger_source: str = "schedule",
    requested_by: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Extract, transform and atomically publish one Nexova reporting week."""

    resolved, window_start, window_end = _week_window(week_start)
    resolved_run_id = run_id or str(uuid4())
    run = _base_run(
        run_id=resolved_run_id,
        week_start=resolved,
        window_start=window_start,
        window_end=window_end,
        trigger_source=trigger_source,
        requested_by=requested_by,
        status="RUNNING",
    )
    persist_pipeline_run_task(run)

    try:
        events = extract_telemetry_events_task(run["window_start"], run["window_end"])
        run = {**run, "phase": "extract", "records_extracted": len(events)}
        persist_pipeline_run_task(run)

        transformed = transform_weekly_office_program_performance_task(
            events, resolved.isoformat()
        )
        persist_pipeline_inputs_task(resolved_run_id, transformed["inputs"])
        run = {
            **run,
            "phase": "transform",
            "records_extracted": transformed["records_extracted"],
            "records_deduplicated": transformed["records_deduplicated"],
            "records_rejected": transformed["records_rejected"],
            "source_checksum": transformed["source_checksum"],
            "output_checksum": transformed["output_checksum"],
        }
        persist_pipeline_run_task(run)

        loaded = load_weekly_office_program_performance_task(
            resolved.isoformat(), transformed["rows"]
        )
        run = {**run, "phase": "load", "records_loaded": loaded}
        persist_pipeline_run_task(run)

        snapshot_state = write_eval_snapshot_task(
            resolved.isoformat(), resolved_run_id, transformed["rows"], return_state=True
        )
        optional_snapshot_status = (
            "failed" if snapshot_state.is_failed() else "completed"
        )

        run = {
            **run,
            "status": "COMPLETED",
            "phase": "complete",
            "finished_at": _iso_z(_utc_now()),
        }
        persist_pipeline_run_task(run)
        return {**run, "optional_snapshot_status": optional_snapshot_status}
    except Exception as exc:
        failed = {
            **run,
            "status": "FAILED",
            "finished_at": _iso_z(_utc_now()),
            "error_code": _safe_error_code(exc),
        }
        try:
            persist_pipeline_run_task(failed)
        except Exception:
            pass
        raise


def reserve_manual_run(
    week_start: str | None = None, requested_by: str | None = None
) -> tuple[str, str]:
    resolved, window_start, window_end = _week_window(week_start)
    run_id = str(uuid4())
    run = _base_run(
        run_id=run_id,
        week_start=resolved,
        window_start=window_start,
        window_end=window_end,
        trigger_source="manual",
        requested_by=requested_by,
        status="PENDING",
    )
    get_store().reserve_run(run)
    return run_id, resolved.isoformat()


def start_weekly_office_program_performance_run(
    *, week_start: str, requested_by: str | None, run_id: str
) -> dict[str, Any]:
    return build_weekly_office_program_performance(
        week_start=week_start,
        trigger_source="manual",
        requested_by=requested_by,
        run_id=run_id,
    )


def get_latest_pipeline_run() -> dict[str, Any] | None:
    return get_store().latest_run()


def get_weekly_office_program_performance(
    week_start: str | None = None,
) -> dict[str, Any]:
    resolved = resolve_week_start(week_start).isoformat() if week_start else None
    selected_week, rows = get_store().read_rows(resolved)
    return {"week_start": selected_week, "entries": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Nexova's weekly business pipeline")
    parser.add_argument("--week-start", help="ISO Monday (YYYY-MM-DD)")
    parser.add_argument(
        "--trigger-source",
        choices=("schedule", "manual", "backfill"),
        default="schedule",
    )
    arguments = parser.parse_args()
    result = build_weekly_office_program_performance(
        week_start=arguments.week_start,
        trigger_source=arguments.trigger_source,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
