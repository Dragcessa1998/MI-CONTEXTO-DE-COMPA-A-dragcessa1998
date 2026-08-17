"use client";

import { FormEvent, useEffect, useState } from "react";

import { Field, InventoryHeader, Loading, Retry, Stock, inputClass } from "@/components/InventoryProducts";
import { EXIT_TYPE_LABELS, InventoryApiError, inventoryApi, outboundWarning, type Asset, type ExitType } from "@/lib/inventory";

export default function InventoryOutboundForm() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [assetId, setAssetId] = useState(0);
  const [quantity, setQuantity] = useState(1);
  const [exitType, setExitType] = useState<ExitType>("allocation");
  const [assignedTo, setAssignedTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const selected = assets.find((asset) => asset.id === assetId);
  const warning = selected ? outboundWarning(quantity, selected.current_stock) : "";

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
  useEffect(() => {
    if (!assetId) return;
    let active = true;
    inventoryApi.getProduct(assetId)
      .then((fresh) => {
        if (active) setAssets((current) => current.map((asset) => asset.id === fresh.id ? fresh : asset));
      })
      .catch((reason) => {
        if (active) setError(reason instanceof InventoryApiError ? reason.message : "No pudimos actualizar el stock.");
      });
    return () => { active = false; };
  }, [assetId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setSuccess("");
    if (!selected) return setError("Selecciona un activo.");
    if (!Number.isInteger(quantity) || quantity < 1) return setError("La cantidad debe ser un entero mayor que cero.");
    if (warning) return setError(warning);
    if (exitType === "allocation" && !assignedTo.trim()) return setError("Indica la persona o equipo que recibirá el activo.");
    setBusy(true);
    try {
      await inventoryApi.createOutbound({ asset_id: selected.id, quantity, exit_type: exitType, assigned_to: exitType === "allocation" ? assignedTo.trim() : null, office: selected.office });
      setQuantity(1); setAssignedTo(""); setSuccess(`Salida registrada en ${selected.office}.`); await load();
    } catch (reason) { setError(reason instanceof InventoryApiError ? reason.message : "No pudimos registrar la salida."); }
    finally { setBusy(false); }
  }

  if (loading && !assets.length) return <><InventoryHeader title="Salida de inventario" description="Registra asignaciones o consumos sin permitir stock negativo." /><Loading /></>;
  if (error && !assets.length) return <><InventoryHeader title="Salida de inventario" description="Registra asignaciones o consumos sin permitir stock negativo." /><Retry message={error} onRetry={load} /></>;
  return <div className="space-y-6"><InventoryHeader title="Salida de inventario" description="Registra asignaciones o consumos sin permitir stock negativo." /><section className="max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><form onSubmit={submit} className="space-y-4"><Field label="Activo"><select className={inputClass} value={assetId} onChange={(event) => { setAssetId(Number(event.target.value)); setError(""); }}>{assets.map((asset) => <option key={asset.id} value={asset.id}>{asset.name} · {asset.sku} · {asset.office}</option>)}</select></Field><div className="grid gap-4 sm:grid-cols-2"><Field label="Cantidad"><input className={inputClass} type="number" min={1} step={1} value={quantity} onChange={(event) => { setQuantity(Number(event.target.value)); setError(""); }} /></Field><Field label="Sede"><input className={`${inputClass} bg-slate-50`} value={selected?.office ?? ""} readOnly /></Field></div><Field label="Tipo de salida"><select className={inputClass} value={exitType} onChange={(event) => { const value = event.target.value as ExitType; setExitType(value); if (value === "consumption") setAssignedTo(""); }}>{Object.entries(EXIT_TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>{exitType === "allocation" && <Field label="Asignado a"><input className={inputClass} value={assignedTo} onChange={(event) => setAssignedTo(event.target.value)} placeholder="Persona, equipo o departamento" /></Field>}{selected && <div className="flex items-center gap-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600"><span>Stock disponible:</span><Stock value={selected.current_stock} /><span>Stock posterior: <strong>{selected.current_stock - Math.max(quantity || 0, 0)}</strong></span></div>}{warning && <p role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm font-medium text-amber-800">{warning}</p>}{error && error !== warning && <p role="alert" className="text-sm text-rose-700">{error}</p>}{success && <p role="status" className="text-sm text-emerald-700">{success}</p>}<button disabled={busy || !assets.length || Boolean(warning)} className="rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50">{busy ? "Registrando…" : "Registrar salida"}</button></form></section></div>;
}
