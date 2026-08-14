"""
Modelos Pydantic del Directorio de Proveedores de Nexova.

Los nombres de campos, las categorías válidas y los estados permitidos replican
EXACTAMENTE lo definido en CONTEXT.md (CONTEXT-nexova · supplier-directory).
Pydantic rechaza con 422 cualquier entrada que no cumpla antes de tocar TinyDB.
"""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Categorías válidas (lista literal del CONTEXT).
VALID_CATEGORIES = [
    "job_boards",
    "ats_software",
    "assessment_tools",
    "training_platforms",
    "payroll_and_hr_software",
    "video_interview",
    "background_check",
    "office_and_facilities",
    "it_and_software_licenses",
]

# Estados válidos (lista literal del CONTEXT).
VALID_STATUSES = ["active", "suspended"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    suppliers: int = Field(ge=0)


class DeleteResponse(BaseModel):
    detail: str


class SupplierStatus(str, Enum):
    """Solo los dos estados que define el CONTEXT; cualquier otro valor → 422."""

    active = "active"
    suspended = "suspended"


class SupplierIn(BaseModel):
    """Modelo de ENTRADA: lo que el cliente envía. `rate_updated_at` NO se acepta
    aquí porque lo genera el sistema (ver SupplierOut)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Nombre comercial del proveedor o plataforma")
    country: Literal["Spain", "USA"] = Field(description='País del contrato activo: "Spain" o "USA"')
    categories: list[str] = Field(min_length=1, description="Tipo de servicio que provee (ver lista válida)")
    monthly_rate: float = Field(gt=0, allow_inf_nan=False, description="Coste mensual vigente en la moneda del contrato")
    currency: Literal["EUR", "USD"] = Field(description='"EUR" para Spain, "USD" para USA')
    status: SupplierStatus
    contract_renewal_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Fecha de renovación del contrato (formato YYYY-MM-DD)",
    )
    contact_email: str | None = Field(default=None, description="Email del account manager del proveedor")
    notes: str | None = Field(default=None, description="Observaciones internas")

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("El nombre no puede estar vacío ni ser solo espacios")
        return value

    @field_validator("contract_renewal_date")
    @classmethod
    def renewal_date_must_be_real(cls, value: str | None) -> str | None:
        # La regex del Field valida el formato; esto descarta fechas imposibles (2025-13-45).
        if value is not None:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("contract_renewal_date debe ser una fecha real (YYYY-MM-DD)") from exc
        return value

    @field_validator("categories")
    @classmethod
    def categories_must_be_valid(cls, value: list[str]) -> list[str]:
        invalid = [c for c in value if c not in VALID_CATEGORIES]
        if invalid:
            raise ValueError(
                f"Categorías no válidas: {invalid}. Las válidas son: {VALID_CATEGORIES}"
            )
        return value

    @model_validator(mode="after")
    def currency_must_match_country(self) -> "SupplierIn":
        # Restricción de negocio del CONTEXT: Spain→EUR, USA→USD; se rechaza lo demás.
        expected = "EUR" if self.country == "Spain" else "USD"
        if self.currency != expected:
            raise ValueError(
                f'Un proveedor de "{self.country}" debe tener currency = "{expected}"'
            )
        return self


class SupplierOut(SupplierIn):
    """Modelo de RESPUESTA: añade el ID asignado por TinyDB y el timestamp de
    tarifa generado por el sistema."""

    id: int
    rate_updated_at: datetime


class RateUpdate(BaseModel):
    """Cuerpo de PATCH /suppliers/{id}/rate — la tarifa debe ser > 0 (y finita)."""

    model_config = ConfigDict(extra="forbid")

    monthly_rate: float = Field(gt=0, allow_inf_nan=False)


class StatusUpdate(BaseModel):
    """Cuerpo de PATCH /suppliers/{id}/status — solo "active" o "suspended"."""

    model_config = ConfigDict(extra="forbid")

    status: SupplierStatus
