"""Authenticated reporting endpoints delegate to the pipeline package."""

from nexova_pipelines.pipeline import reserve_manual_run


def test_reporting_endpoints_require_authentication(anonymous_client) -> None:
    assert anonymous_client.get("/reporting/pipeline-runs/latest").status_code == 401
    assert (
        anonymous_client.get("/reporting/weekly-office-program-performance").status_code
        == 401
    )
    assert anonymous_client.post("/reporting/pipeline-runs", json={}).status_code == 401


def test_manual_run_status_contract(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "reporting.routes.run_reporting_pipeline_task.apply_async",
        lambda **_kwargs: None,
    )
    response = client.post(
        "/reporting/pipeline-runs",
        json={"week_start": "2026-08-03"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"
    assert response.json()["task_id"] == response.json()["run_id"]

    latest = client.get("/reporting/pipeline-runs/latest")
    assert latest.status_code == 200
    assert latest.json()["status"] == "PENDING"


def test_manual_run_validates_monday_and_rejects_active_week(client) -> None:
    invalid = client.post(
        "/reporting/pipeline-runs",
        json={"week_start": "2026-08-04"},
    )
    assert invalid.status_code == 422

    reserve_manual_run("2026-08-03", requested_by="test")
    conflict = client.post(
        "/reporting/pipeline-runs",
        json={"week_start": "2026-08-03"},
    )
    assert conflict.status_code == 409
