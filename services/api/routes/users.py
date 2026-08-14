"""CRUD protegido de credenciales; perfiles y contraseñas nunca se serializan aquí."""

from fastapi import APIRouter, Depends, HTTPException, status

from auth_models import (
    RegistrationResponse,
    ProfileOut,
    UserCreate,
    UserOut,
    UserRecord,
    UserRole,
    UserUpdate,
    UserWithProfile,
)
from auth_service import (
    create_user,
    delete_user,
    get_profile_by_user_id,
    get_user_by_email,
    get_user_by_id,
    list_users,
    update_user,
)
from security import get_current_user


router = APIRouter(prefix="/users", tags=["users"])


def _is_admin(user: UserRecord) -> bool:
    return user.role == UserRole.ADMIN


def _require_owner_or_admin(target_user_id: int, current_user: UserRecord) -> None:
    if current_user.id != target_user_id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="No puedes acceder a otro usuario")


@router.post("", status_code=201, response_model=RegistrationResponse)
def register_user(payload: UserCreate) -> RegistrationResponse:
    if get_user_by_email(str(payload.email)) is not None:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")
    user, profile = create_user(payload)
    return RegistrationResponse(
        id=user.id,
        is_active=user.is_active,
        role=user.role,
        created_at=user.created_at,
        profile=ProfileOut.model_validate(profile.model_dump(exclude={"user_id"})),
    )


@router.get("", response_model=list[UserOut])
def read_users(current_user: UserRecord = Depends(get_current_user)) -> list[UserOut]:
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Solo un administrador puede listar usuarios")
    return list_users()


@router.get("/{user_id}", response_model=UserWithProfile)
def read_user(
    user_id: int, current_user: UserRecord = Depends(get_current_user)
) -> UserWithProfile:
    _require_owner_or_admin(user_id, current_user)
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    profile = get_profile_by_user_id(user_id)
    if profile is None:
        raise HTTPException(status_code=500, detail="El usuario no tiene un perfil vinculado")
    safe_user = UserOut.model_validate(user.model_dump())
    return UserWithProfile(
        **safe_user.model_dump(),
        profile=ProfileOut.model_validate(profile.model_dump(exclude={"user_id"})),
    )


@router.put("/{user_id}", response_model=UserOut)
def replace_user(
    user_id: int,
    payload: UserUpdate,
    current_user: UserRecord = Depends(get_current_user),
) -> UserOut:
    _require_owner_or_admin(user_id, current_user)
    if not _is_admin(current_user) and (payload.role is not None or payload.is_active is not None):
        raise HTTPException(status_code=403, detail="Solo un administrador puede cambiar rol o estado")
    if payload.email is not None:
        existing = get_user_by_email(str(payload.email))
        if existing is not None and existing.id != user_id:
            raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")
    updated = update_user(user_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return updated


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def remove_user(
    user_id: int, current_user: UserRecord = Depends(get_current_user)
) -> None:
    _require_owner_or_admin(user_id, current_user)
    if not delete_user(user_id):
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
