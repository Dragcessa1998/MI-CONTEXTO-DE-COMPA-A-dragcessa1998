"""Acceptance tests for Nexova's centralized incident manager."""

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

import routes.incidents as incident_routes
import database
from main import app
from scripts.seed_incidents import DEFAULT_CSV, print_report, seed


def incident_payload(**overrides) -> dict:
    payload = {
        "title": "Fallo de acceso al ATS",
        "description": "El equipo de selección no puede iniciar sesión en Greenhouse.",
        "category": "technical_failure",
        "status": "open",
        "origin": "branch",
        "branch": "valencia_operations",
    }
    payload.update(overrides)
    return payload


def test_empty_database_returns_empty_list_and_zeroed_summary(client: TestClient):
    assert client.get("/api/incidents").json() == []
    summary = client.get("/api/incidents/summary").json()
    assert summary["total"] == 0
    assert set(summary["by_status"]) == {"open", "in_progress", "resolved", "discarded"}
    assert all(count == 0 for group in summary.values() if isinstance(group, dict) for count in group.values())


def test_create_generates_id_and_timezone_aware_timestamps(client: TestClient):
    response = client.post("/api/incidents", json=incident_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["created_at"] == body["updated_at"]
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None


def test_validation_errors_are_400_and_identify_fields_in_plain_language(
    client: TestClient,
):
    response = client.post(
        "/api/incidents",
        json={"title": "", "description": "x", "category": "generic", "origin": "email"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "Datos del incidente no válidos"
    assert {"title", "description", "category", "origin", "branch"}.issubset(body["fields"])
    assert "traceback" not in response.text.lower()


def test_list_filters_by_all_supported_dimensions(client: TestClient):
    first = client.post("/api/incidents", json=incident_payload()).json()
    client.post(
        "/api/incidents",
        json=incident_payload(
            title="Queja de cliente",
            category="client_complaint",
            origin="customer",
            branch="central",
        ),
    )

    assert len(client.get("/api/incidents").json()) == 2
    assert [item["id"] for item in client.get("/api/incidents?status=open").json()] == [1, 2]
    assert [item["id"] for item in client.get("/api/incidents?origin=branch").json()] == [first["id"]]
    assert [item["id"] for item in client.get("/api/incidents?branch=central").json()] == [2]
    assert [item["id"] for item in client.get("/api/incidents?category=technical_failure").json()] == [1]
    assert client.get("/api/incidents?origin=unknown").status_code == 400


def test_get_detail_and_missing_404(client: TestClient):
    created = client.post("/api/incidents", json=incident_payload()).json()

    assert client.get(f"/api/incidents/{created['id']}").json() == created
    assert client.get("/api/incidents/999").status_code == 404


def test_status_lifecycle_accepts_only_forward_transitions(client: TestClient):
    created = client.post("/api/incidents", json=incident_payload()).json()

    in_progress = client.patch(
        f"/api/incidents/{created['id']}/status", json={"status": "in_progress"}
    )
    resolved = client.patch(
        f"/api/incidents/{created['id']}/status", json={"status": "resolved"}
    )
    final_state = client.patch(
        f"/api/incidents/{created['id']}/status", json={"status": "discarded"}
    )

    assert in_progress.status_code == 200
    assert in_progress.json()["status"] == "in_progress"
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert final_state.status_code == 400
    assert final_state.json()["detail"]["field"] == "status"


def test_invalid_initial_transition_and_unknown_incident_are_rejected(client: TestClient):
    created = client.post("/api/incidents", json=incident_payload()).json()

    invalid = client.patch(
        f"/api/incidents/{created['id']}/status", json={"status": "resolved"}
    )
    missing = client.patch("/api/incidents/999/status", json={"status": "in_progress"})

    assert invalid.status_code == 400
    assert missing.status_code == 404


def test_all_incident_routes_require_authentication(anonymous_client: TestClient):
    assert anonymous_client.get("/api/incidents").status_code == 401
    assert anonymous_client.get("/api/incidents/summary").status_code == 401
    assert anonymous_client.post("/api/incidents", json=incident_payload()).status_code == 401


def test_tinydb_tables_are_safe_for_parallel_fastapi_reads(client: TestClient):
    client.post("/api/incidents", json=incident_payload())

    def read_tables(_index: int) -> tuple[int, int]:
        return len(database.users_table().all()), len(database.incidents_table().all())

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(read_tables, range(100)))

    assert results == [(1, 1)] * 100


def test_unhandled_exception_returns_generic_500_without_trace(
    client: TestClient, monkeypatch,
):
    def fail(_payload):
        raise RuntimeError("database-password-should-never-leak")

    monkeypatch.setattr(incident_routes, "create_incident", fail)
    with TestClient(app, raise_server_exceptions=False, headers=dict(client.headers)) as safe_client:
        response = safe_client.post("/api/incidents", json=incident_payload())

    assert response.status_code == 500
    assert response.json() == {"detail": "No se pudo completar la operación. Inténtalo de nuevo."}
    assert "database-password" not in response.text


def test_seed_transforms_96_valid_rows_reports_four_invalid_and_is_idempotent(
    client: TestClient, capsys,
):
    first = seed(DEFAULT_CSV)
    print_report(first, DEFAULT_CSV)
    output = capsys.readouterr().out
    second = seed(DEFAULT_CSV)

    assert first["total"] == 100
    assert first["valid"] == first["inserted"] == first["stored"] == 96
    assert first["invalid"] == 4
    assert first["errors"] == {
        "missing_client_company": 1,
        "invalid_category": 1,
        "invalid_email": 1,
        "closed_without_score": 1,
    }
    assert second["inserted"] == 0
    assert second["skipped"] == 96
    assert second["stored"] == 96
    assert "@" not in output

    summary = client.get("/api/incidents/summary").json()
    assert summary["total"] == 96
    assert summary["by_status"] == {
        "open": 27,
        "in_progress": 0,
        "resolved": 56,
        "discarded": 13,
    }
    assert summary["by_category"] == {
        "technical_failure": 49,
        "process_error": 35,
        "client_complaint": 12,
        "candidate_issue": 0,
        "staff_issue": 0,
        "sla_breach": 0,
        "data_quality": 0,
        "other": 0,
    }
    assert summary["by_origin"]["customer"] == 96
    assert summary["by_branch"]["central"] == 96
