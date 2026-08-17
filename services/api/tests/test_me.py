"""Unit tests for the authenticated user projection (GET /auth/me)."""

import pytest
from fastapi import HTTPException
from tinydb import Query

import database
from auth_models import UserCreate
from auth_service import create_user, get_user_by_id
from routes.auth import read_auth_me


def create_account():
    user, profile = create_user(
        UserCreate(
            email="me@nexova.example",
            password="ReliablePassword-2026!",
            name="Current User",
            phone="+34 600 000 011",
        )
    )
    return user, profile


def test_me_returns_only_the_safe_user_projection_and_profile() -> None:
    """Happy path: internal hashes are excluded from the response model."""
    user, profile = create_account()
    current_user = get_user_by_id(user.id)

    result = read_auth_me(current_user)
    serialized = result.model_dump(mode="json")

    assert result.id == user.id
    assert result.profile == profile
    assert "hashed_password" not in serialized
    assert "password" not in serialized


def test_me_preserves_empty_optional_profile_fields() -> None:
    """Edge case: a minimal profile remains a valid authenticated identity."""
    user, _profile = create_user(
        UserCreate(
            email="minimal-me@nexova.example",
            password="ReliablePassword-2026!",
        )
    )

    result = read_auth_me(get_user_by_id(user.id))

    assert result.profile.name == result.profile.phone == result.profile.address == ""


def test_me_rejects_user_with_missing_linked_profile() -> None:
    """Failure mode: inconsistent storage is never returned as partial identity data."""
    user, _profile = create_account()
    database.profiles_table().remove(Query().user_id == user.id)

    with pytest.raises(HTTPException) as error:
        read_auth_me(get_user_by_id(user.id))

    assert error.value.status_code == 401
