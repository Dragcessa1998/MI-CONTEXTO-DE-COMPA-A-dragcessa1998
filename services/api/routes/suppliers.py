"""
Endpoints del Directorio de Proveedores de Nexova.

Errores HTTP consistentes (rúbrica): 404 si no existe, 422 si la entrada es
inválida (la valida Pydantic antes de tocar TinyDB), 200/201 si la operación
tiene éxito.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from tinydb.table import Document

from database import suppliers_table
from models import RateUpdate, StatusUpdate, SupplierIn, SupplierOut
from security import get_current_user

router = APIRouter(
    prefix="/suppliers",
    tags=["suppliers"],
    dependencies=[Depends(get_current_user)],
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_out(doc: Document) -> SupplierOut:
    """Convierte un documento de TinyDB (datos + doc_id) al modelo de respuesta."""
    return SupplierOut(id=doc.doc_id, **doc)


def _get_or_404(supplier_id: int) -> Document:
    doc = suppliers_table().get(doc_id=supplier_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return doc


@router.post("", status_code=201, response_model=SupplierOut)
def create_supplier(payload: SupplierIn) -> SupplierOut:
    """Registra un proveedor. Devuelve el objeto creado con su ID de TinyDB.
    Las entradas inválidas se rechazan con 422 (Pydantic)."""
    record = payload.model_dump()
    record["rate_updated_at"] = _now_iso()  # generado por el sistema, no por el cliente
    doc_id = suppliers_table().insert(record)
    return SupplierOut(id=doc_id, **record)


@router.get("", response_model=list[SupplierOut])
def list_suppliers(
    country: str | None = Query(default=None, description='Filtrar por país ("Spain" / "USA")'),
    category: str | None = Query(default=None, description="Filtrar por categoría de servicio"),
) -> list[SupplierOut]:
    """Lista los proveedores. Sin parámetros devuelve todos; `country` y
    `category` filtran (y se pueden combinar)."""
    docs = suppliers_table().all()
    if country is not None:
        docs = [d for d in docs if d.get("country") == country]
    if category is not None:
        docs = [d for d in docs if category in d.get("categories", [])]
    return [_to_out(d) for d in docs]


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: int) -> SupplierOut:
    """Detalle de un proveedor por ID. 404 si no existe."""
    return _to_out(_get_or_404(supplier_id))


@router.patch("/{supplier_id}/rate", response_model=SupplierOut)
def update_rate(supplier_id: int, payload: RateUpdate) -> SupplierOut:
    """Actualiza la tarifa mensual y registra `rate_updated_at` automáticamente
    (trazabilidad para auditorías). Tarifas <= 0 → 422."""
    _get_or_404(supplier_id)
    table = suppliers_table()
    table.update(
        {"monthly_rate": payload.monthly_rate, "rate_updated_at": _now_iso()},
        doc_ids=[supplier_id],
    )
    return _to_out(table.get(doc_id=supplier_id))


@router.patch("/{supplier_id}/status", response_model=SupplierOut)
def update_status(supplier_id: int, payload: StatusUpdate) -> SupplierOut:
    """Activa o suspende un proveedor. Solo acepta los dos estados del CONTEXT."""
    _get_or_404(supplier_id)
    table = suppliers_table()
    table.update({"status": payload.status.value}, doc_ids=[supplier_id])
    return _to_out(table.get(doc_id=supplier_id))


@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: int) -> dict:
    """Elimina un proveedor del directorio. 404 si el ID no existe."""
    _get_or_404(supplier_id)
    suppliers_table().remove(doc_ids=[supplier_id])
    return {"detail": f"Proveedor {supplier_id} eliminado"}
