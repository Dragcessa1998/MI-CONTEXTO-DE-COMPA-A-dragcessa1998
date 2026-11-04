"""Perfil uno-a-uno del usuario autenticado."""

from fastapi import APIRouter, Depends, HTTPException

from auth_models import ProfileOut, ProfileUpdate, UserRecord
from auth_service import get_profile_by_user_id, update_profile
from security import get_current_user


router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileOut)
def read_my_profile(current_user: UserRecord = Depends(get_current_user)) -> ProfileOut:
    profile = get_profile_by_user_id(current_user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return profile


@router.put("/me", response_model=ProfileOut)
def replace_my_profile(
    payload: ProfileUpdate,
    current_user: UserRecord = Depends(get_current_user),
) -> ProfileOut:
    profile = update_profile(
        current_user.id,
        name=payload.name,
        phone=payload.phone,
        address=payload.address,
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    return profile
