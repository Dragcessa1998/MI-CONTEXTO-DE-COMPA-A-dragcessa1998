"""Seeder idempotente del inventario mínimo definido para Nexova."""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlmodel import Session, select
from tinydb import Query

from database import create_inventory_schema, inventory_engine, users_table
from inventory_models import Asset, AssetEntry, AssetExit


ASSETS_SEED = [
    ("Laptop 14\" Business", "NXV-IT-001", "hardware", "Valencia"),
    ("Laptop 14\" Business", "NXV-IT-002", "hardware", "Miami"),
    ("Ergonomic mouse", "NXV-PER-001", "peripherals", "Valencia"),
    ("USB-C Hub", "NXV-PER-002", "peripherals", "Miami"),
    ("A4 paper ream", "NXV-OFF-001", "office_supplies", "Valencia"),
    ("Leadership training workbook", "NXV-TRN-001", "training_materials", "Valencia"),
]


def _seed_user_uuid() -> str:
    user_uuid = str(uuid5(NAMESPACE_URL, "nexova:inventory-seed-user"))
    table = users_table()
    if table.get(Query().uuid == user_uuid) is None:
        record = {
            "uuid": user_uuid,
            "email": "inventory-seed@nexova.invalid",
            "hashed_password": "!disabled-seed-account!",
            "is_active": False,
            "role": "manager",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        doc_id = table.insert(record)
        table.update({"id": doc_id}, doc_ids=[doc_id])
    return user_uuid


def seed_inventory(session: Session, user_uuid: str) -> tuple[int, int, int]:
    assets_by_sku = {asset.sku: asset for asset in session.exec(select(Asset)).all()}
    inserted_assets = 0
    for name, sku, category, office in ASSETS_SEED:
        if sku in assets_by_sku:
            continue
        asset = Asset(name=name, sku=sku, category=category, office=office)
        session.add(asset)
        session.flush()
        assets_by_sku[sku] = asset
        inserted_assets += 1

    inserted_entries = 0
    if session.exec(select(AssetEntry)).first() is None:
        entry_specs = [
            ("NXV-IT-001", 10, "TechDistrib Valencia S.L."),
            ("NXV-IT-001", 5, "TechDistrib Valencia S.L."),
            ("NXV-PER-001", 20, "TechDistrib Valencia S.L."),
            ("NXV-OFF-001", 50, "Office Depot Valencia"),
        ]
        for sku, quantity, supplier in entry_specs:
            asset = assets_by_sku[sku]
            session.add(
                AssetEntry(
                    asset_id=int(asset.id),
                    quantity=quantity,
                    supplier=supplier,
                    office=asset.office,
                    user_uuid=user_uuid,
                )
            )
        inserted_entries = len(entry_specs)

    inserted_exits = 0
    if session.exec(select(AssetExit)).first() is None:
        exit_specs = [
            ("NXV-IT-001", 2, "allocation", "María Torres"),
            ("NXV-PER-001", 3, "allocation", "David Romero"),
            ("NXV-OFF-001", 8, "consumption", None),
        ]
        for sku, quantity, exit_type, assigned_to in exit_specs:
            asset = assets_by_sku[sku]
            session.add(
                AssetExit(
                    asset_id=int(asset.id),
                    quantity=quantity,
                    exit_type=exit_type,
                    assigned_to=assigned_to,
                    office=asset.office,
                    user_uuid=user_uuid,
                )
            )
        inserted_exits = len(exit_specs)

    session.commit()
    return inserted_assets, inserted_entries, inserted_exits


def main() -> int:
    create_inventory_schema()
    with Session(inventory_engine) as session:
        counts = seed_inventory(session, _seed_user_uuid())
    print(
        "Inventory seed complete: "
        f"{counts[0]} assets, {counts[1]} entries, {counts[2]} exits inserted."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
