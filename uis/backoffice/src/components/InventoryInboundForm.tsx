"use client";

import { FormEvent, useEffect, useState } from "react";

import { Field, InventoryHeader, Loading, Retry, inputClass } from "@/components/InventoryProducts";
import { InventoryApiError, inventoryApi, type Asset } from "@/lib/inventory";

export default function InventoryInboundForm() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [assetId, setAssetId] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [supplier, setSupplier] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const selected = assets.find((asset) => asset.id === assetId);

  async function load() {
    setLoading(true); setError("");
    try {
      const rows = await inventoryApi.listProducts();
      const requested = Number(new URLSearchParams(window.location.search).get("asset"));
      const requestedExists = rows.some((asset) => asset.id === requested);
      setAssets(rows);
      setAssetId((current) => current || (requestedExists ? requested : rows[0]?.id || 0));
    }
    catch (reason) { setError(reason instanceof InventoryApiError ? reason.message : "No pudimos cargar los activos."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void load(); }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setSuccess("");
    if (!selected) return setError("Selecciona un activo.");
    if (!Number.isInteger(quantity) || quantity < 1) return setError("La cantidad debe ser un entero mayor que cero.");
    if (!supplier.trim()) return setError("Escribe el proveedor de la entrada.");
    setBusy(true);
    try {
      await inventoryApi.createInbound({ asset_id: selected.id, quantity, supplier: supplier.trim(), office: selected.office });
      setQuantity(1); setSupplier(""); setSuccess(`Entrada registrada en ${selected.office}.`); await load();
    } catch (reason) { setError(reason instanceof InventoryApiError ? reason.message : "No pudimos registrar la entrada."); }
    finally { setBusy(false); }
  }

  if (loading && !assets.length) return <><InventoryHeader title="Entrada de inventario" description="Registra compras y reposiciones por sede." /><Loading /></>;
  if (error && !assets.length) return <><InventoryHeader title="Entrada de inventario" description="Registra compras y reposiciones por sede." /><Retry message={error} onRetry={load} /></>;
  return <div className="space-y-6"><InventoryHeader title="Entrada de inventario" description="Registra compras y reposiciones por sede." /><section className="max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><form onSubmit={submit} className="space-y-4"><Field label="Activo"><select className={inputClass} value={assetId} onChange={(event) => setAssetId(Number(event.target.value))}>{assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.name} · {asset.sku} · {asset.office}</option>)}</select></Field><div className="grid gap-4 sm:grid-cols-2"><Field label="Cantidad"><input className={inputClass} type="number" min={1} step={1} value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} /></Field><Field label="Sede"><input className={`${inputClass} bg-slate-50`} value={selected?.office ?? ""} readOnly /></Field></div><Field label="Proveedor"><input className={inputClass} value={supplier} onChange={(event) => setSupplier(event.target.value)} placeholder="Ej. Tech Supply Iberia" /></Field>{selected && <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">Stock actual: <strong>{selected.current_stock}</strong>. Tras la entrada: <strong>{selected.current_stock + Math.max(quantity || 0, 0)}</strong>.</p>}{error && <p role="alert" className="text-sm text-rose-700">{error}</p>}{success && <p role="status" className="text-sm text-emerald-700">{success}</p>}<button disabled={busy || !assets.length} className="rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60">{busy ? "Registrando…" : "Registrar entrada"}</button></form></section></div>;
}
