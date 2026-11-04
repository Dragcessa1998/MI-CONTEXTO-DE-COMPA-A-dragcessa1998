"""Contratos Pydantic seguros para usuarios, perfiles y autenticación."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"


def validate_bcrypt_password(value: str) -> str:
    """bcrypt solo procesa de forma segura contraseñas de hasta 72 bytes."""
    if len(value.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar 72 bytes UTF-8")
    return value


class ProfileFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=240)

    @field_validator("name", "phone", "address")
    @classmethod
    def strip_profile_fields(cls, value: str) -> str:
        return value.strip()


class UserCreate(ProfileFields):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password_size(cls, value: str) -> str:
        return validate_bcrypt_password(value)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def normalize_optional_email(cls, value: EmailStr | None) -> str | None:
        return str(value).strip().lower() if value is not None else None

    @field_validator("password")
    @classmethod
    def validate_optional_password_size(cls, value: str | None) -> str | None:
        return validate_bcrypt_password(value) if value is not None else None


class UserRecord(BaseModel):
    """Representación interna. Nunca debe usarse como response_model."""

    id: int
    email: EmailStr
    hashed_password: str
    is_active: bool
    role: UserRole
    created_at: datetime


class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    role: UserRole
    created_at: datetime


class ProfileOut(ProfileFields):
    id: int
    user_id: int


class ProfileUpdate(ProfileFields):
    pass


class UserWithProfile(UserOut):
    profile: ProfileOut


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
