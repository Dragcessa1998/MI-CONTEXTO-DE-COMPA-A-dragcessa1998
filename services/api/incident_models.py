"""Contratos del gestor centralizado de incidentes Nexova."""

from datetime import datetime

from nexova_shared.incidents import (
    INCIDENT_BRANCHES,
    INCIDENT_CATEGORIES,
    INCIDENT_ORIGINS,
    INCIDENT_STATUSES,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=5, max_length=10_000)
    category: str
    status: str = "open"
    origin: str
    branch: str

    @field_validator("title", "description")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("no puede estar vacío")
        return stripped

    @field_validator("category")
    @classmethod
    def valid_category(cls, value: str) -> str:
        if value not in INCIDENT_CATEGORIES:
            raise ValueError("categoría no permitida para Nexova")
        return value

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in INCIDENT_STATUSES:
            raise ValueError("estado no permitido")
        return value

    @field_validator("origin")
    @classmethod
    def valid_origin(cls, value: str) -> str:
        if value not in INCIDENT_ORIGINS:
            raise ValueError("origen no permitido")
        return value

    @field_validator("branch")
    @classmethod
    def valid_branch(cls, value: str) -> str:
        if value not in INCIDENT_BRANCHES:
            raise ValueError("sede no permitida para Nexova")
        return value


class IncidentOut(IncidentCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class IncidentStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, value: str) -> str:
        if value not in INCIDENT_STATUSES:
            raise ValueError("estado no permitido")
        return value


class IncidentSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_origin: dict[str, int]
    by_branch: dict[str, int]
