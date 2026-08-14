"""Acceptance tests for the Prefect business-performance pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from nexova_pipelines.pipeline import (
    build_weekly_office_program_performance,
    transform_events,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_PATH = REPO_ROOT / "data" / "raw" / "telemetry_events.sample.json"


def sample_events() -> list[dict]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def test_transform_produces_exact_nexova_kpis_and_deduplicates() -> None:
    events = sample_events()
    events.append(dict(events[0]))

    result = transform_events(events, "2026-08-03")

    assert result["records_extracted"] == 8
    assert result["records_deduplicated"] == 1
    assert result["records_rejected"] == 0
    assert result["rows"] == [
        {
            "office": "miami",
            "programme_id": "b2b-sales",
            "week_start": "2026-08-03",
            "currency": "USD",
            "total_material_cost": 300.0,
            "kits_delivered_count": 1,
            "shortage_events_count": 0,
            "cost_variance_events_count": 0,
        },
        {
            "office": "valencia",
            "programme_id": "leadership-foundations",
            "week_start": "2026-08-03",
            "currency": "EUR",
            "total_material_cost": 500.0,
            "kits_delivered_count": 2,
            "shortage_events_count": 1,
            "cost_variance_events_count": 1,
        },
    ]


def test_transform_rejects_currency_mismatch_and_exclusive_end() -> None:
    events = sample_events()[:1]
    wrong_currency = json.loads(json.dumps(events[0]))
    wrong_currency["id"] = "20000000-0000-4000-8000-000000000001"
    wrong_currency["tags"]["currency"] = "USD"
    next_week = json.loads(json.dumps(events[0]))
    next_week["id"] = "20000000-0000-4000-8000-000000000002"
    next_week["timestamp"] = "2026-08-10T00:00:00Z"

    result = transform_events(events + [wrong_currency, next_week], "2026-08-03")

    assert result["records_rejected"] == 2
    assert len(result["rows"]) == 1
    assert result["rows"][0]["total_material_cost"] == 500.0


def test_flow_is_idempotent_and_optional_failure_is_non_critical(
    tmp_path: Path, monkeypatch
) -> None:
    state_dir = tmp_path / "state"
    monkeypatch.setenv("PIPELINE_STATE_DIR", str(state_dir))

    first = build_weekly_office_program_performance(
        week_start="2026-08-03", trigger_source="backfill"
    )
    table_path = state_dir / "weekly_office_program_performance.local.json"
    first_rows = json.loads(table_path.read_text(encoding="utf-8"))

    second = build_weekly_office_program_performance(
        week_start="2026-08-03", trigger_source="backfill"
    )
    second_rows = json.loads(table_path.read_text(encoding="utf-8"))
    input_rows = json.loads(
        (state_dir / "pipeline_run_inputs.local.json").read_text(encoding="utf-8")
    )

    assert first["status"] == second["status"] == "COMPLETED"
    assert first["records_loaded"] == second["records_loaded"] == 2
    assert len(first_rows) == len(second_rows) == 2
    assert len(input_rows) == 14
    assert all(item["event_id"] and item["request_id"] is None for item in input_rows)
    assert [
        {key: value for key, value in row.items() if key != "computed_at"}
        for row in first_rows
    ] == [
        {key: value for key, value in row.items() if key != "computed_at"}
        for row in second_rows
    ]

    monkeypatch.setenv("PIPELINE_FAIL_EVAL_SNAPSHOT", "1")
    optional_failure = build_weekly_office_program_performance(
        week_start="2026-08-10", trigger_source="backfill"
    )
    assert optional_failure["status"] == "COMPLETED"
    assert optional_failure["optional_snapshot_status"] == "failed"
