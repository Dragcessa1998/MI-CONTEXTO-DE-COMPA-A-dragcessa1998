"""Authenticated reporting endpoints delegate to the pipeline package."""

from nexova_pipelines.pipeline import reserve_manual_run


def test_reporting_endpoints_require_authentication(anonymous_client) -> None:
    assert anonymous_client.get("/reporting/pipeline-runs/latest").status_code == 401
    assert (
        anonymous_client.get("/reporting/weekly-office-program-performance").status_code
        == 401
    )
    assert anonymous_client.post("/reporting/pipeline-runs", json={}).status_code == 401


def test_manual_run_status_and_kpi_contract(client) -> None:
    response = client.post(
        "/reporting/pipeline-runs",
        json={"week_start": "2026-08-03"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"

    latest = client.get("/reporting/pipeline-runs/latest")
    assert latest.status_code == 200
    assert latest.json()["status"] == "COMPLETED"
    assert latest.json()["records_extracted"] == 7
    assert latest.json()["records_loaded"] == 2

    report = client.get(
        "/reporting/weekly-office-program-performance",
        params={"week_start": "2026-08-03"},
    )
    assert report.status_code == 200
    assert report.json() == {
        "week_start": "2026-08-03",
        "entries": [
            {
                "office": "miami",
                "programme_id": "b2b-sales",
                "total_material_cost": 300.0,
                "kits_delivered_count": 1,
                "shortage_events_count": 0,
                "cost_variance_events_count": 0,
                "currency": "USD",
            },
            {
                "office": "valencia",
                "programme_id": "leadership-foundations",
                "total_material_cost": 500.0,
                "kits_delivered_count": 2,
                "shortage_events_count": 1,
                "cost_variance_events_count": 1,
                "currency": "EUR",
            },
        ],
    }


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
