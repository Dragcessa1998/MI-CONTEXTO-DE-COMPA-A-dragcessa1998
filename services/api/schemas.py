"""Contratos Pydantic del inventario, separados de los modelos ORM."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Office = Literal["Valencia", "Miami"]
AssetCategory = Literal[
    "hardware", "peripherals", "office_supplies", "training_materials"
]
ExitType = Literal["allocation", "consumption"]


class AssetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    sku: str = Field(min_length=1, max_length=64)
    category: AssetCategory
    office: Office


class AssetSummary(BaseModel):
    id: int
    name: str
    sku: str
    category: AssetCategory
    office: Office


class AssetResponse(AssetSummary):
    current_stock: int


class AssetEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    supplier: str = Field(min_length=1, max_length=160)
    office: Office


class AssetExitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    exit_type: ExitType
    assigned_to: str | None = Field(default=None, max_length=160)
    office: Office

    @model_validator(mode="after")
    def assignment_matches_exit_type(self) -> "AssetExitCreate":
        assigned = self.assigned_to.strip() if self.assigned_to else None
        if self.exit_type == "allocation" and not assigned:
            raise ValueError("assigned_to is required when exit_type is allocation")
        if self.exit_type == "consumption" and assigned is not None:
            raise ValueError("assigned_to must be null when exit_type is consumption")
        self.assigned_to = assigned
        return self


class AssetEntryResponse(BaseModel):
    id: int
    asset_id: int
    quantity: int
    supplier: str
    office: Office
    created_at: datetime
    user_uuid: str
    asset: AssetSummary


class AssetExitResponse(BaseModel):
    id: int
    asset_id: int
    quantity: int
    exit_type: ExitType
    assigned_to: str | None
    office: Office
    created_at: datetime
    user_uuid: str
    asset: AssetSummary


class OrderResponse(BaseModel):
    id: int
    order_type: Literal["inbound", "outbound"]
    asset_id: int
    quantity: int
    office: Office
    created_at: datetime
    user_uuid: str
    asset: AssetSummary
    supplier: str | None = None
    exit_type: ExitType | None = None
    assigned_to: str | None = None
