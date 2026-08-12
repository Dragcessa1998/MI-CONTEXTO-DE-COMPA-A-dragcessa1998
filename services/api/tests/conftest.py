"""Shared fixtures for the Supplier Directory API."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))

import database  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Give each test a real, isolated TinyDB file and close it afterwards."""
    if database._db is not None:
        database._db.close()
    database._db = None
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "suppliers.db.json")

    yield

    if database._db is not None:
        database._db.close()
    database._db = None


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client

