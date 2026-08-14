"""Acceptance tests for the Nexova Supplier Directory rubric."""

from datetime import datetime

from fastapi.testclient import TestClient

import database
import seed
import routes.suppliers as supplier_routes
from seed import SUPPLIERS_SEED, main as run_seed


def supplier_payload(**overrides):
    payload = {
        "name": "Talent Lab",
        "country": "Spain",
        "categories": ["assessment_tools"],
        "monthly_rate": 125.5,
        "currency": "EUR",
        "status": "active",
        "contract_renewal_date": "2026-12-01",
        "contact_email": "account@talent-lab.example",
        "notes": "Proveedor de evaluación para procesos de selección.",
    }
    payload.update(overrides)
    return payload


def test_seed_loads_exact_context_and_is_idempotent(capsys):
    assert run_seed() == 0
    first_output = capsys.readouterr().out
    assert run_seed() == 0
    second_output = capsys.readouterr().out

    records = database.suppliers_table().all()
    assert len(records) == len(SUPPLIERS_SEED) == 15
    assert {record["name"] for record in records} == {
        supplier["name"] for supplier in SUPPLIERS_SEED
    }
    assert "Insertados: 15" in first_output
    assert "Omitidos (ya existían): 15" in second_output
    assert "Total en la base de datos: 15" in second_output


def test_supplier_seed_returns_nonzero_with_safe_stderr_on_database_failure(
    monkeypatch, capsys,
):
    monkeypatch.setattr(seed, "suppliers_table", lambda: (_ for _ in ()).throw(OSError("secret path")))

    exit_code = seed.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "No se pudo abrir la base local" in captured.err
    assert "secret path" not in captured.err
    assert "Traceback" not in captured.err


def test_create_returns_tinydb_id_and_system_timestamp(client: TestClient):
    response = client.post("/suppliers", json=supplier_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "Talent Lab"
    assert datetime.fromisoformat(body["rate_updated_at"]).tzinfo is not None


def test_system_fields_and_unknown_fields_are_rejected_before_tinydb(client: TestClient):
    response = client.post(
        "/suppliers",
        json=supplier_payload(rate_updated_at="2000-01-01T00:00:00Z", unexpected=True),
    )

    assert response.status_code == 422
    assert len(database.suppliers_table()) == 0


def test_context_validation_rejects_bad_rate_status_category_currency_and_date(
    client: TestClient,
):
    invalid_payloads = [
        supplier_payload(monthly_rate=0),
        supplier_payload(monthly_rate=-10),
        supplier_payload(status="pending"),
        supplier_payload(categories=["generic_services"]),
        supplier_payload(country="Spain", currency="USD"),
        supplier_payload(contract_renewal_date="2026-13-40"),
    ]

    for payload in invalid_payloads:
        assert client.post("/suppliers", json=payload).status_code == 422
    assert len(database.suppliers_table()) == 0


def test_non_finite_rate_produces_serializable_422(client: TestClient):
    response = client.post(
        "/suppliers",
        content='{"name":"Bad rate","country":"Spain","categories":["job_boards"],'
        '"monthly_rate":NaN,"currency":"EUR","status":"active"}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]
    assert len(database.suppliers_table()) == 0


def test_list_all_and_filter_by_country_category_or_both(client: TestClient):
    run_seed()

    assert len(client.get("/suppliers").json()) == 15
    assert len(client.get("/suppliers?country=Spain").json()) == 8
    assert len(client.get("/suppliers?category=job_boards").json()) == 3
    filtered = client.get("/suppliers?country=USA&category=ats_software").json()
    assert [supplier["name"] for supplier in filtered] == ["Greenhouse"]


def test_supplier_list_uses_ttl_cache_and_writes_invalidate_it(
    client: TestClient, monkeypatch
):
    original_table = supplier_routes.suppliers_table
    table_reads = 0

    def counting_table():
        nonlocal table_reads
        table_reads += 1
        return original_table()

    monkeypatch.setattr(supplier_routes, "suppliers_table", counting_table)
    client.post("/suppliers", json=supplier_payload())
    reads_after_write = table_reads

    assert len(client.get("/suppliers").json()) == 1
    reads_after_first_get = table_reads
    assert reads_after_first_get > reads_after_write
    assert len(client.get("/suppliers").json()) == 1
    assert table_reads == reads_after_first_get

    client.post("/suppliers", json=supplier_payload(name="People Analytics Lab"))
    assert len(client.get("/suppliers").json()) == 2
    assert table_reads > reads_after_first_get


def test_get_supplier_and_missing_404(client: TestClient):
    created = client.post("/suppliers", json=supplier_payload()).json()

    assert client.get(f"/suppliers/{created['id']}").json() == created
    missing = client.get("/suppliers/999")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Proveedor no encontrado"}


def test_rate_patch_updates_value_and_timestamp(client: TestClient, monkeypatch):
    monkeypatch.setattr(supplier_routes, "_now_iso", lambda: "2026-08-12T10:00:00+00:00")
    created = client.post("/suppliers", json=supplier_payload()).json()
    monkeypatch.setattr(supplier_routes, "_now_iso", lambda: "2026-08-12T11:00:00+00:00")

    response = client.patch(f"/suppliers/{created['id']}/rate", json={"monthly_rate": 180})

    assert response.status_code == 200
    assert response.json()["monthly_rate"] == 180
    assert response.json()["rate_updated_at"] == "2026-08-12T11:00:00Z"
    assert response.json()["rate_updated_at"] != created["rate_updated_at"]


def test_rate_patch_rejects_invalid_input_and_missing_supplier(client: TestClient):
    created = client.post("/suppliers", json=supplier_payload()).json()

    assert client.patch(f"/suppliers/{created['id']}/rate", json={"monthly_rate": 0}).status_code == 422
    assert client.patch(f"/suppliers/{created['id']}/rate", json={"monthly_rate": -1}).status_code == 422
    assert client.patch("/suppliers/999/rate", json={"monthly_rate": 1}).status_code == 404


def test_status_patch_toggles_and_rejects_disallowed_value(client: TestClient):
    created = client.post("/suppliers", json=supplier_payload()).json()

    updated = client.patch(
        f"/suppliers/{created['id']}/status", json={"status": "suspended"}
    )
    invalid = client.patch(
        f"/suppliers/{created['id']}/status", json={"status": "archived"}
    )

    assert updated.status_code == 200
    assert updated.json()["status"] == "suspended"
    assert invalid.status_code == 422
    assert client.patch("/suppliers/999/status", json={"status": "active"}).status_code == 404


def test_delete_removes_supplier_and_missing_returns_404(client: TestClient):
    created = client.post("/suppliers", json=supplier_payload()).json()

    assert client.delete(f"/suppliers/{created['id']}").status_code == 200
    assert client.get(f"/suppliers/{created['id']}").status_code == 404
    assert client.delete(f"/suppliers/{created['id']}").status_code == 404


def test_tinydb_data_survives_reopening_the_database(client: TestClient):
    created = client.post("/suppliers", json=supplier_payload()).json()
    database._db.close()
    database._db = None

    persisted = client.get(f"/suppliers/{created['id']}")

    assert persisted.status_code == 200
    assert persisted.json()["name"] == "Talent Lab"


def test_health_reports_persisted_supplier_count(client: TestClient):
    run_seed()
    assert client.get("/health").json() == {"status": "ok", "suppliers": 15}
