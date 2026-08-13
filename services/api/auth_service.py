"""Servicio de usuarios y perfiles sobre TinyDB, independiente de HTTP."""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from tinydb import Query

from auth_models import ProfileOut, UserCreate, UserOut, UserRecord, UserUpdate
from database import profiles_table, users_table
from security import hash_password


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_with_uuid(record: dict) -> dict:
    """Migra de forma estable usuarios TinyDB creados antes del hito de inventario."""
    normalized = dict(record)
    if not normalized.get("uuid"):
        normalized["uuid"] = str(uuid5(NAMESPACE_URL, f"nexova-user:{normalized['id']}"))
        users_table().update({"uuid": normalized["uuid"]}, Query().id == normalized["id"])
    return normalized


def _user_record(record: dict) -> UserRecord:
    return UserRecord.model_validate(_record_with_uuid(record))


def _user_out(record: dict) -> UserOut:
    return UserOut.model_validate(_record_with_uuid(record))


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
        "uuid": str(uuid4()),
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
