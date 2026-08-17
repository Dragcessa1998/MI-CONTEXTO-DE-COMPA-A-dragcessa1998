"""Servicio de usuarios y perfiles sobre TinyDB, independiente de HTTP."""

import hashlib
import secrets
from datetime import datetime, timezone

from tinydb import Query

from auth_models import ProfileOut, UserCreate, UserOut, UserRecord, UserUpdate
from database import password_reset_tokens_table, profiles_table, users_table
from security import create_password_reset_token, decode_password_reset_token, hash_password


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_record(record: dict) -> UserRecord:
    return UserRecord.model_validate(record)


def _user_out(record: dict) -> UserOut:
    return UserOut.model_validate(record)


def get_user_by_id(user_id: int) -> UserRecord | None:
    record = users_table().get(Query().id == user_id)
    return _user_record(record) if record is not None else None


def get_user_by_email(email: str) -> UserRecord | None:
    record = users_table().get(Query().email == email.strip().lower())
    return _user_record(record) if record is not None else None


def get_profile_by_user_id(user_id: int) -> ProfileOut | None:
    record = profiles_table().get(Query().user_id == user_id)
    return ProfileOut.model_validate(record) if record is not None else None


def create_user(payload: UserCreate) -> tuple[UserOut, ProfileOut]:
    """Crea credenciales y perfil uno-a-uno; revierte el usuario si falla el perfil."""
    table = users_table()
    record = {
        "email": str(payload.email),
        "hashed_password": hash_password(payload.password),
        "is_active": True,
        "role": "user",
        "created_at": _now_iso(),
    }
    user_doc_id = table.insert(record)
    record["id"] = user_doc_id
    table.update({"id": user_doc_id}, doc_ids=[user_doc_id])

    try:
        profile_record = {
            "user_id": user_doc_id,
            "name": payload.name,
            "phone": payload.phone,
            "address": payload.address,
        }
        profile_doc_id = profiles_table().insert(profile_record)
        profile_record["id"] = profile_doc_id
        profiles_table().update({"id": profile_doc_id}, doc_ids=[profile_doc_id])
    except Exception:
        table.remove(doc_ids=[user_doc_id])
        raise

    return _user_out(record), ProfileOut.model_validate(profile_record)


def list_users() -> list[UserOut]:
    return [_user_out(dict(record)) for record in users_table().all()]


def update_user(user_id: int, payload: UserUpdate) -> UserOut | None:
    current = get_user_by_id(user_id)
    if current is None:
        return None

    changes = payload.model_dump(exclude_none=True)
    if "email" in changes:
        changes["email"] = str(changes["email"])
    if "password" in changes:
        changes["hashed_password"] = hash_password(changes.pop("password"))
    if "role" in changes:
        changes["role"] = changes["role"].value
    if changes:
        users_table().update(changes, Query().id == user_id)
    updated = get_user_by_id(user_id)
    return UserOut.model_validate(updated.model_dump())


def update_profile(user_id: int, name: str, phone: str, address: str) -> ProfileOut | None:
    query = Query()
    if profiles_table().get(query.user_id == user_id) is None:
        return None
    profiles_table().update(
        {"name": name, "phone": phone, "address": address},
        query.user_id == user_id,
    )
    return get_profile_by_user_id(user_id)


def delete_user(user_id: int) -> bool:
    query = Query()
    if users_table().get(query.id == user_id) is None:
        return False
    profiles_table().remove(query.user_id == user_id)
    users_table().remove(query.id == user_id)
    return True


class PasswordResetTokenError(ValueError):
    pass


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_password_reset_token(user_id: int) -> str:
    token_id = secrets.token_urlsafe(24)
    token, expires_at = create_password_reset_token(user_id, token_id)
    record = {
        "user_id": user_id,
        "token_id": token_id,
        "token_hash": _token_hash(token),
        "created_at": _now_iso(),
        "expires_at": expires_at.isoformat(),
        "used_at": None,
    }
    doc_id = password_reset_tokens_table().insert(record)
    password_reset_tokens_table().update({"id": doc_id}, doc_ids=[doc_id])
    return token


def invalidate_password_reset_tokens(user_id: int) -> None:
    used_at = _now_iso()
    table = password_reset_tokens_table()
    for record in table.search(Query().user_id == user_id):
        if record.get("used_at") is None:
            table.update({"used_at": used_at}, doc_ids=[record.doc_id])


def set_user_password(user_id: int, new_password: str) -> bool:
    if get_user_by_id(user_id) is None:
        return False
    users_table().update(
        {"hashed_password": hash_password(new_password)},
        Query().id == user_id,
    )
    return True


def consume_password_reset_token(token: str, new_password: str) -> None:
    try:
        user_id, token_id = decode_password_reset_token(token)
    except ValueError as exc:
        raise PasswordResetTokenError(str(exc)) from exc

    table = password_reset_tokens_table()
    record = table.get(
        (Query().token_id == token_id)
        & (Query().token_hash == _token_hash(token))
        & (Query().user_id == user_id)
    )
    if record is None or record.get("used_at") is not None:
        raise PasswordResetTokenError("Token de recuperación inválido, expirado o ya utilizado")
    expires_at = datetime.fromisoformat(str(record["expires_at"]))
    if expires_at <= datetime.now(timezone.utc):
        raise PasswordResetTokenError("Token de recuperación inválido, expirado o ya utilizado")
    if get_user_by_id(user_id) is None:
        raise PasswordResetTokenError("Token de recuperación inválido, expirado o ya utilizado")
    claimed = table.update(
        {"used_at": _now_iso()},
        (Query().id == record["id"]) & (Query().used_at == None),  # noqa: E711
    )
    if not claimed:
        raise PasswordResetTokenError("Token de recuperación inválido, expirado o ya utilizado")
    set_user_password(user_id, new_password)
    invalidate_password_reset_tokens(user_id)
