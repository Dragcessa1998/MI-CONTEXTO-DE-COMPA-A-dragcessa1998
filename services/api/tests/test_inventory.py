"""Acceptance suite for Nexova's dual-database inventory milestone."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from database import get_db
from inventory_models import Asset, AssetEntry, AssetExit
from inventory_seed import seed_inventory
from main import app


@pytest.fixture
def inventory_api(client: TestClient) -> Generator[tuple[TestClient, object], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield client, engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


def create_asset(client: TestClient, sku: str = "NXV-TEST-001") -> dict:
    response = client.post(
        "/inventory/products",
        json={
            "name": "Test laptop",
            "sku": sku,
            "category": "hardware",
            "office": "Valencia",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_inventory_tables_use_foreign_keys_and_never_store_current_stock(inventory_api):
    _, engine = inventory_api
    inspector = inspect(engine)
    asset_columns = {column["name"] for column in inspector.get_columns("assets")}
    assert asset_columns == {"id", "name", "sku", "category", "office"}
    assert "current_stock" not in asset_columns
    assert inspector.get_foreign_keys("asset_entries")[0]["referred_table"] == "assets"
    assert inspector.get_foreign_keys("asset_exits")[0]["referred_table"] == "assets"


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/inventory/products",
            {"name": "Mouse", "sku": "NXV-AUTH-1", "category": "peripherals", "office": "Miami"},
        ),
        (
            "/inventory/orders/inbound",
            {"asset_id": 1, "quantity": 1, "supplier": "Vendor", "office": "Miami"},
        ),
        (
            "/inventory/orders/outbound",
            {
                "asset_id": 1,
                "quantity": 1,
                "exit_type": "consumption",
                "assigned_to": None,
                "office": "Miami",
            },
        ),
    ],
)
def test_every_inventory_write_requires_tinydb_auth(
    anonymous_client: TestClient, path: str, payload: dict
):
    assert anonymous_client.post(path, json=payload).status_code == 401


def test_asset_starts_at_zero_and_duplicate_sku_is_rejected(inventory_api):
    client, _ = inventory_api
    asset = create_asset(client)
    assert asset["current_stock"] == 0
    assert "current_stock" not in {
        "name": "Test laptop",
        "sku": "NXV-TEST-001",
        "category": "hardware",
        "office": "Valencia",
    }
    duplicate = client.post(
        "/inventory/products",
        json={
            "name": "Other laptop",
            "sku": "NXV-TEST-001",
            "category": "hardware",
            "office": "Valencia",
        },
    )
    assert duplicate.status_code == 409


def test_inbound_and_outbound_orders_compute_stock_and_trace_user(inventory_api):
    client, engine = inventory_api
    asset = create_asset(client)

    inbound = client.post(
        "/inventory/orders/inbound",
        json={
            "asset_id": asset["id"],
            "quantity": 12,
            "supplier": "TechDistrib Valencia S.L.",
            "office": "Valencia",
        },
    )
    assert inbound.status_code == 201
    assert inbound.json()["user_uuid"]
    assert inbound.json()["asset"]["sku"] == "NXV-TEST-001"

    outbound = client.post(
        "/inventory/orders/outbound",
        json={
            "asset_id": asset["id"],
            "quantity": 4,
            "exit_type": "allocation",
            "assigned_to": "Ana Beltrán",
            "office": "Valencia",
        },
    )
    assert outbound.status_code == 201
    assert outbound.json()["user_uuid"] == inbound.json()["user_uuid"]

    product = client.get(f"/inventory/products/{asset['id']}")
    assert product.status_code == 200
    assert product.json()["current_stock"] == 8

    with Session(engine) as session:
        entry = session.exec(select(AssetEntry)).one()
        asset_exit = session.exec(select(AssetExit)).one()
        assert entry.user_uuid == asset_exit.user_uuid


def test_outbound_cannot_make_stock_negative_and_is_not_persisted(inventory_api):
    client, engine = inventory_api
    asset = create_asset(client)
    client.post(
        "/inventory/orders/inbound",
        json={
            "asset_id": asset["id"],
            "quantity": 3,
            "supplier": "TechDistrib Valencia S.L.",
            "office": "Valencia",
        },
    )
    rejected = client.post(
        "/inventory/orders/outbound",
        json={
            "asset_id": asset["id"],
            "quantity": 4,
            "exit_type": "allocation",
            "assigned_to": "Ana Beltrán",
            "office": "Valencia",
        },
    )
    assert rejected.status_code == 400
    assert rejected.json() == {
        "detail": "Insufficient stock for asset 'Test laptop'. Available: 3, requested: 4."
    }
    with Session(engine) as session:
        assert session.exec(select(AssetExit)).all() == []


@pytest.mark.parametrize(
    "payload",
    [
        {
            "asset_id": 1,
            "quantity": 1,
            "exit_type": "allocation",
            "assigned_to": None,
            "office": "Valencia",
        },
        {
            "asset_id": 1,
            "quantity": 1,
            "exit_type": "consumption",
            "assigned_to": "Ana Beltrán",
            "office": "Valencia",
        },
    ],
)
def test_exit_type_and_assignee_must_be_consistent(inventory_api, payload: dict):
    client, _ = inventory_api
    response = client.post("/inventory/orders/outbound", json=payload)
    assert response.status_code == 422


def test_order_office_must_match_asset_partition(inventory_api):
    client, _ = inventory_api
    asset = create_asset(client)
    response = client.post(
        "/inventory/orders/inbound",
        json={
            "asset_id": asset["id"],
            "quantity": 2,
            "supplier": "Office Depot Miami",
            "office": "Miami",
        },
    )
    assert response.status_code == 400
    assert "belongs to Valencia" in response.json()["detail"]


def test_orders_are_eager_loaded_with_asset_data(inventory_api):
    client, _ = inventory_api
    asset = create_asset(client)
    client.post(
        "/inventory/orders/inbound",
        json={
            "asset_id": asset["id"],
            "quantity": 5,
            "supplier": "Vendor",
            "office": "Valencia",
        },
    )
    client.post(
        "/inventory/orders/outbound",
        json={
            "asset_id": asset["id"],
            "quantity": 1,
            "exit_type": "consumption",
            "assigned_to": None,
            "office": "Valencia",
        },
    )
    orders = client.get("/inventory/orders")
    assert orders.status_code == 200
    assert {order["order_type"] for order in orders.json()} == {"inbound", "outbound"}
    assert {order["asset"]["sku"] for order in orders.json()} == {"NXV-TEST-001"}


def test_seed_is_idempotent_and_stock_matches_context(inventory_api):
    client, engine = inventory_api
    with Session(engine) as session:
        assert seed_inventory(session, "seed-user-uuid") == (6, 4, 3)
        assert seed_inventory(session, "seed-user-uuid") == (0, 0, 0)

    products = client.get("/inventory/products")
    assert products.status_code == 200
    by_sku = {product["sku"]: product for product in products.json()}
    assert len(by_sku) == 6
    assert by_sku["NXV-IT-001"]["current_stock"] == 13
    assert by_sku["NXV-PER-001"]["current_stock"] == 17
    assert by_sku["NXV-OFF-001"]["current_stock"] == 42
    assert by_sku["NXV-IT-002"]["current_stock"] == 0


def test_inventory_get_routes_are_public(inventory_api, anonymous_client: TestClient):
    _, _ = inventory_api
    assert anonymous_client.get("/inventory/products").status_code == 200
    assert anonymous_client.get("/inventory/orders").status_code == 200
