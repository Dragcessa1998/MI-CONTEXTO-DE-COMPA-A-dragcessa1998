from __future__ import annotations

import csv
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.job_runner import ClaimOutcome, JobRunRepository
from scripts.nightly_export import resolve_target_date


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "nightly_export.py"


def create_telemetry_db(path: Path, target_date: date, *, with_events: bool = True) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE telemetry_events (
          event_id TEXT NOT NULL,
          event_timestamp TEXT NOT NULL,
          session_id TEXT,
          user_id TEXT,
          event_type TEXT NOT NULL,
          schema_version TEXT NOT NULL,
          request_id TEXT NOT NULL,
          properties TEXT NOT NULL,
          ingested_at TEXT NOT NULL
        )
        """
    )
    if not with_events:
        connection.commit()
        connection.close()
        return

    timestamp = f"{target_date.isoformat()}T12:00:00Z"
    base = {
        "office": "valencia",
        "programme_id": "ventas-b2b",
        "currency": "EUR",
        "product_id": "kit-1",
        "product_category": "training_kit",
        "quantity": 10,
    }
    rows = [
        ("event-in", "inbound_order_created", {**base, "unit_cost": 12.5}),
        # Reentrega exacta: el CSV la conserva para auditoría; el ETL deduplica.
        ("event-in", "inbound_order_created", {**base, "unit_cost": 12.5}),
        ("event-out", "outbound_order_created", {**base, "quantity": 3}),
        ("event-low", "stock_threshold_triggered", {**base, "quantity": 2}),
        ("event-cost", "kit_cost_variance_detected", {**base, "quantity": 4}),
    ]
    for index, (event_id, event_type, properties) in enumerate(rows):
        connection.execute(
            "INSERT INTO telemetry_events VALUES (?,?,?,?,?,?,?,?,?)",
            (
                event_id,
                timestamp,
                "session-test",
                "user-test",
                event_type,
                "1.0.0",
                f"request-{index}",
                json.dumps(properties),
                f"{target_date.isoformat()}T12:00:{index:02d}Z",
            ),
        )
    connection.commit()
    connection.close()


def environment(database: Path, raw: Path, target_date: date) -> dict[str, str]:
    return {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database}",
        "RAW_DATA_DIR": str(raw),
        "TARGET_DATE": target_date.isoformat(),
        "PYTHONPATH": str(ROOT),
    }


def run_script(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_target_date_override_and_utc_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET_DATE", "2026-08-10")
    assert resolve_target_date() == date(2026, 8, 10)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        resolve_target_date("10/08/2026")
    monkeypatch.delenv("TARGET_DATE")
    assert resolve_target_date() == datetime.now(timezone.utc).date() - timedelta(days=1)


def test_successful_run_exports_csv_triggers_pipeline_and_is_idempotent(tmp_path: Path) -> None:
    target = date(2026, 8, 10)
    database = tmp_path / "nexova.sqlite3"
    raw = tmp_path / "raw"
    create_telemetry_db(database, target)
    env = environment(database, raw, target)

    first = run_script(env)
    assert first.returncode == 0, first.stderr
    assert "status=completed" in first.stderr
    csv_path = raw / "telemetry_2026-08-10.csv"
    assert csv_path.is_file()
    with csv_path.open(encoding="utf-8", newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    assert len(csv_rows) == 5

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    job = connection.execute("SELECT * FROM job_runs").fetchone()
    assert job["status"] == "completed"
    assert job["target_date"] == target.isoformat()
    assert job["finished_at"] is not None
    assert connection.execute("SELECT COUNT(*) FROM reporting_pipeline_runs").fetchone()[0] == 1
    report = connection.execute(
        "SELECT * FROM reporting_weekly_office_program_performance"
    ).fetchone()
    assert report["office"] == "valencia"
    assert report["programme_id"] == "ventas-b2b"
    assert report["total_material_cost"] == "125.0"
    assert report["kits_delivered_count"] == 1
    assert report["shortage_events_count"] == 1
    assert report["cost_variance_events_count"] == 1
    connection.close()

    original_bytes = csv_path.read_bytes()
    second = run_script(env)
    assert second.returncode == 0
    assert "skipped reason=duplicate" in second.stderr
    assert csv_path.read_bytes() == original_bytes
    connection = sqlite3.connect(database)
    assert connection.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM reporting_pipeline_runs").fetchone()[0] == 1
    connection.close()


def test_pipeline_failure_marks_job_failed_and_leaves_no_processing(tmp_path: Path) -> None:
    target = date(2026, 8, 11)
    database = tmp_path / "failure.sqlite3"
    create_telemetry_db(database, target, with_events=False)
    env = environment(database, tmp_path / "raw", target)
    env["PIPELINE_COMMAND_JSON"] = json.dumps(
        [sys.executable, "-c", "import sys; sys.exit(7)"]
    )

    result = run_script(env)
    assert result.returncode == 1
    assert "status=failed" in result.stderr
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM job_runs").fetchone()
    assert row["status"] == "failed"
    assert row["finished_at"] is not None
    assert "exit status 7" in row["error_message"]
    assert connection.execute(
        "SELECT COUNT(*) FROM job_runs WHERE status='processing'"
    ).fetchone()[0] == 0
    connection.close()


def test_processing_status_is_the_only_concurrency_lock(tmp_path: Path) -> None:
    target = date(2026, 8, 12)
    database = tmp_path / "concurrent.sqlite3"
    create_telemetry_db(database, target, with_events=False)
    env = environment(database, tmp_path / "raw", target)
    env["PIPELINE_COMMAND_JSON"] = json.dumps(
        [sys.executable, "-c", "import time; time.sleep(1)"]
    )

    first = subprocess.Popen(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        connection = sqlite3.connect(database)
        try:
            processing = connection.execute(
                "SELECT COUNT(*) FROM job_runs WHERE status='processing'"
            ).fetchone()[0]
        except sqlite3.OperationalError as error:
            if "no such table" not in str(error):
                raise
            processing = 0
        connection.close()
        if processing == 1:
            break
        time.sleep(0.02)
    else:
        first.kill()
        pytest.fail("La primera instancia no adquirió processing")

    second = run_script(env)
    first_stdout, first_stderr = first.communicate(timeout=10)
    assert first.returncode == 0, first_stdout + first_stderr
    assert second.returncode == 0
    assert "skipped reason=already_running" in second.stderr
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    rows = connection.execute("SELECT * FROM job_runs").fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
    connection.close()


def test_stale_processing_run_is_failed_before_next_claim(tmp_path: Path) -> None:
    database = tmp_path / "stale.sqlite3"
    repository = JobRunRepository(f"sqlite:///{database}")
    first = repository.claim("nightly_export", date(2026, 8, 9))
    assert first.outcome is ClaimOutcome.ACQUIRED
    old = (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat()
    connection = sqlite3.connect(database)
    connection.execute("UPDATE job_runs SET started_at=? WHERE id=?", (old, first.run_id))
    connection.commit()
    connection.close()

    second = repository.claim(
        "nightly_export",
        date(2026, 8, 10),
        stale_after=timedelta(hours=6),
    )
    assert second.outcome is ClaimOutcome.ACQUIRED
    assert first.run_id is not None and repository.get(first.run_id).status == "failed"
    assert second.run_id is not None
    repository.update_status(second.run_id, "completed")
