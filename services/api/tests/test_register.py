"""Unit tests for registration business rules (POST /users)."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from tinydb import Query

import database
from auth_models import UserCreate
from routes.users import register_user
from security import verify_password


def registration_payload(**overrides) -> dict:
    payload = {
        "email": "  Owner@NEXOVA.example ",
        "password": "ReliablePassword-2026!",
        "name": "  Owner Test  ",
        "phone": " +34 600 000 010 ",
        "address": " Valencia ",
    }
    payload.update(overrides)
    return payload


def test_register_creates_safe_user_and_separate_profile() -> None:
    """Happy path: credentials are hashed and profile data is kept separate."""
    result = register_user(UserCreate(**registration_payload()))

    stored_user = database.users_table().get(Query().id == result.id)
    stored_profile = database.profiles_table().get(Query().user_id == result.id)

    assert result.email == "owner@nexova.example"
    assert result.profile.name == "Owner Test"
    assert verify_password("ReliablePassword-2026!", stored_user["hashed_password"])
    assert "password" not in result.model_dump()
    assert "hashed_password" not in result.model_dump()
    assert not {"name", "phone", "address"}.intersection(stored_user)
    assert stored_profile["phone"] == "+34 600 000 010"


def test_register_accepts_empty_optional_profile_fields() -> None:
    """Edge case: the profile fields are optional but a linked profile still exists."""
    result = register_user(
        UserCreate(
            **registration_payload(
                email="minimal@nexova.example", name="", phone="", address=""
            )
        )
    )

    assert result.profile.user_id == result.id
    assert result.profile.name == result.profile.phone == result.profile.address == ""


def test_register_rejects_duplicate_email_after_normalization() -> None:
    """Failure mode: email uniqueness is case-insensitive and whitespace-safe."""
    register_user(UserCreate(**registration_payload()))

    with pytest.raises(HTTPException) as error:
        register_user(
            UserCreate(**registration_payload(email="owner@nexova.example"))
        )

    assert error.value.status_code == 409
    assert len(database.users_table()) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"password": "short"},
        {"password": "á" * 40},  # 80 UTF-8 bytes: bcrypt's hard boundary is 72.
    ],
)
def test_register_rejects_malformed_or_unsafe_credentials(overrides: dict) -> None:
    """Failure modes are rejected before any database mutation."""
    with pytest.raises(ValidationError):
        UserCreate(**registration_payload(**overrides))

    assert len(database.users_table()) == 0
    assert len(database.profiles_table()) == 0
