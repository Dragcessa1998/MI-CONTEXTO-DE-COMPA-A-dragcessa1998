"""Modelos SQLModel del inventario de equipos y suministros de Nexova."""

from datetime import datetime, timezone
from typing import ClassVar, Optional

from sqlalchemy import Column, String
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Asset(SQLModel, table=True):
    __tablename__: ClassVar[str] = "assets"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=160)
    sku: str = Field(
        sa_column=Column(String(64), unique=True, nullable=False, index=True)
    )
    category: str = Field(max_length=40)
    office: str = Field(max_length=20)

    entries: list["AssetEntry"] = Relationship(back_populates="asset")
    exits: list["AssetExit"] = Relationship(back_populates="asset")


class AssetEntry(SQLModel, table=True):
    __tablename__: ClassVar[str] = "asset_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    quantity: int = Field(gt=0)
    supplier: str = Field(min_length=1, max_length=160)
    office: str = Field(max_length=20, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    user_uuid: str = Field(max_length=64, index=True)

    asset: Optional[Asset] = Relationship(back_populates="entries")


class AssetExit(SQLModel, table=True):
    __tablename__: ClassVar[str] = "asset_exits"

    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    quantity: int = Field(gt=0)
    exit_type: str = Field(max_length=20)
    assigned_to: Optional[str] = Field(default=None, max_length=160)
    office: str = Field(max_length=20, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    user_uuid: str = Field(max_length=64, index=True)

    asset: Optional[Asset] = Relationship(back_populates="exits")
