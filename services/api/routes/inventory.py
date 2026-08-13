"""API de inventario Nexova bajo /inventory, respaldada por SQLModel."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from auth_models import UserRecord
from database import get_db
from inventory_models import Asset, AssetEntry, AssetExit
from schemas import (
    AssetCreate,
    AssetEntryCreate,
    AssetEntryResponse,
    AssetExitCreate,
    AssetExitResponse,
    AssetResponse,
    AssetSummary,
    OrderResponse,
)
from security import get_current_user


router = APIRouter(prefix="/inventory", tags=["inventory"])


def _require_asset(session: Session, asset_id: int) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def _validate_office(asset: Asset, office: str) -> None:
    if asset.office != office:
        raise HTTPException(
            status_code=400,
            detail=f"Asset '{asset.name}' belongs to {asset.office}, not {office}.",
        )


def _stock_totals(session: Session) -> tuple[dict[tuple[int, str], int], dict[tuple[int, str], int]]:
    inbound_rows = session.exec(
        select(AssetEntry.asset_id, AssetEntry.office, func.sum(AssetEntry.quantity))
        .group_by(AssetEntry.asset_id, AssetEntry.office)
    ).all()
    outbound_rows = session.exec(
        select(AssetExit.asset_id, AssetExit.office, func.sum(AssetExit.quantity))
        .group_by(AssetExit.asset_id, AssetExit.office)
    ).all()
    inbound = {(asset_id, office): int(total or 0) for asset_id, office, total in inbound_rows}
    outbound = {(asset_id, office): int(total or 0) for asset_id, office, total in outbound_rows}
    return inbound, outbound


def _current_stock(session: Session, asset: Asset) -> int:
    inbound, outbound = _stock_totals(session)
    key = (int(asset.id), asset.office)
    return inbound.get(key, 0) - outbound.get(key, 0)


def _asset_response(asset: Asset, current_stock: int) -> AssetResponse:
    return AssetResponse(
        id=int(asset.id),
        name=asset.name,
        sku=asset.sku,
        category=asset.category,
        office=asset.office,
        current_stock=current_stock,
    )


def _asset_summary(asset: Asset) -> AssetSummary:
    return AssetSummary(
        id=int(asset.id),
        name=asset.name,
        sku=asset.sku,
        category=asset.category,
        office=asset.office,
    )


@router.get("/products", response_model=list[AssetResponse])
def list_assets(session: Session = Depends(get_db)) -> list[AssetResponse]:
    assets = session.exec(select(Asset).order_by(Asset.office, Asset.name, Asset.sku)).all()
    inbound, outbound = _stock_totals(session)
    return [
        _asset_response(
            asset,
            inbound.get((int(asset.id), asset.office), 0)
            - outbound.get((int(asset.id), asset.office), 0),
        )
        for asset in assets
    ]


@router.post("/products", status_code=status.HTTP_201_CREATED, response_model=AssetResponse)
def create_asset(
    payload: AssetCreate,
    session: Session = Depends(get_db),
    _current_user: UserRecord = Depends(get_current_user),
) -> AssetResponse:
    if session.exec(select(Asset).where(Asset.sku == payload.sku)).first() is not None:
        raise HTTPException(status_code=409, detail="An asset with this SKU already exists")
    asset = Asset(**payload.model_dump())
    session.add(asset)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="An asset with this SKU already exists") from exc
    session.refresh(asset)
    return _asset_response(asset, 0)


@router.get("/products/{asset_id}", response_model=AssetResponse)
def read_asset(asset_id: int, session: Session = Depends(get_db)) -> AssetResponse:
    asset = _require_asset(session, asset_id)
    return _asset_response(asset, _current_stock(session, asset))


@router.post(
    "/orders/inbound",
    status_code=status.HTTP_201_CREATED,
    response_model=AssetEntryResponse,
)
def register_asset_entry(
    payload: AssetEntryCreate,
    session: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> AssetEntryResponse:
    asset = _require_asset(session, payload.asset_id)
    _validate_office(asset, payload.office)
    entry = AssetEntry(**payload.model_dump(), user_uuid=current_user.uuid)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return AssetEntryResponse(**entry.model_dump(), asset=_asset_summary(asset))


@router.post(
    "/orders/outbound",
    status_code=status.HTTP_201_CREATED,
    response_model=AssetExitResponse,
)
def register_asset_exit(
    payload: AssetExitCreate,
    session: Session = Depends(get_db),
    current_user: UserRecord = Depends(get_current_user),
) -> AssetExitResponse:
    asset = _require_asset(session, payload.asset_id)
    _validate_office(asset, payload.office)
    available = _current_stock(session, asset)
    if payload.quantity > available:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient stock for asset '{asset.name}'. "
                f"Available: {available}, requested: {payload.quantity}."
            ),
        )
    asset_exit = AssetExit(**payload.model_dump(), user_uuid=current_user.uuid)
    session.add(asset_exit)
    session.commit()
    session.refresh(asset_exit)
    return AssetExitResponse(**asset_exit.model_dump(), asset=_asset_summary(asset))


@router.get("/orders", response_model=list[OrderResponse])
def list_orders(session: Session = Depends(get_db)) -> list[OrderResponse]:
    entries = session.exec(
        select(AssetEntry).options(selectinload(AssetEntry.asset))
    ).all()
    exits = session.exec(
        select(AssetExit).options(selectinload(AssetExit.asset))
    ).all()
    orders = [
        OrderResponse(
            id=int(entry.id),
            order_type="inbound",
            asset_id=entry.asset_id,
            quantity=entry.quantity,
            supplier=entry.supplier,
            office=entry.office,
            created_at=entry.created_at,
            user_uuid=entry.user_uuid,
            asset=_asset_summary(entry.asset),
        )
        for entry in entries
        if entry.asset is not None
    ]
    orders.extend(
        OrderResponse(
            id=int(asset_exit.id),
            order_type="outbound",
            asset_id=asset_exit.asset_id,
            quantity=asset_exit.quantity,
            exit_type=asset_exit.exit_type,
            assigned_to=asset_exit.assigned_to,
            office=asset_exit.office,
            created_at=asset_exit.created_at,
            user_uuid=asset_exit.user_uuid,
            asset=_asset_summary(asset_exit.asset),
        )
        for asset_exit in exits
        if asset_exit.asset is not None
    )
    return sorted(orders, key=lambda order: order.created_at, reverse=True)
