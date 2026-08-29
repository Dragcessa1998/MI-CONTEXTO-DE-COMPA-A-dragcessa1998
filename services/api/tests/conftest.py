"""Shared fixtures for the Supplier Directory API."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(REPO_ROOT))

import database  # noqa: E402
from main import app  # noqa: E402
from routes.rfp_events import rfp_event_broker  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Give each test a real, isolated TinyDB file and close it afterwards."""
    if database._db is not None:
        database._db.close()
    database._db = None
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "suppliers.db.json")
    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-longer-than-thirty-two-characters")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

    yield

    if database._db is not None:
        database._db.close()
    database._db = None


@pytest.fixture(autouse=True)
def isolated_rfp_event_broker():
    rfp_event_broker.reset()
    yield
    rfp_event_broker.reset()


@pytest.fixture
def anonymous_client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(anonymous_client: TestClient) -> TestClient:
    """Authenticated client used by the Supplier Directory acceptance suite."""
    registration = anonymous_client.post(
        "/users",
        json={
            "email": "supplier-tests@nexova.example",
            "password": "SupplierTests-2026!",
            "name": "Supplier Test Operator",
        },
    )
    assert registration.status_code == 201
    login = anonymous_client.post(
        "/auth/login",
        json={
            "email": "supplier-tests@nexova.example",
            "password": "SupplierTests-2026!",
        },
    )
    assert login.status_code == 200
    anonymous_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return anonymous_client
