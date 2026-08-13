"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";

import {
  ASSET_CATEGORIES,
  CATEGORY_LABELS,
  InventoryApiError,
  OFFICES,
  inventoryApi,
  type Asset,
  type AssetInput,
} from "@/lib/inventory";

const EMPTY: AssetInput = { name: "", sku: "", category: "hardware", office: "Valencia" };
const inputClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100";

export default function InventoryProducts() {
  const [products, setProducts] = useState<Asset[]>([]);
  const [form, setForm] = useState<AssetInput>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setProducts(await inventoryApi.listProducts()); }
    catch (reason) { setError(reason instanceof InventoryApiError ? reason.message : "No pudimos cargar los activos."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (!form.name.trim() || !form.sku.trim()) return setError("Nombre y SKU son obligatorios.");
    setBusy(true);
    try {
      const created = await inventoryApi.createProduct({ ...form, name: form.name.trim(), sku: form.sku.trim().toUpperCase() });
      setProducts((current) => [...current, created].sort((a, b) => a.office.localeCompare(b.office) || a.name.localeCompare(b.name)));
      setForm(EMPTY);
      setSuccess("Activo creado correctamente.");
    } catch (reason) {
      setError(reason instanceof InventoryApiError ? reason.message : "No pudimos crear el activo.");
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-6">
      <InventoryHeader title="Productos y stock" description="Catálogo de activos Nexova con existencias calculadas por sede." />
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-lg font-bold text-slate-900">Crear activo</h3>
        <form onSubmit={submit} className="mt-4 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Field label="Nombre"><input className={inputClass} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></Field>
          <Field label="SKU"><input className={inputClass} value={form.sku} onChange={(event) => setForm({ ...form, sku: event.target.value })} /></Field>
          <Field label="Categoría"><select className={inputClass} value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value as AssetInput["category"] })}>{ASSET_CATEGORIES.map((category) => <option key={category} value={category}>{CATEGORY_LABELS[category]}</option>)}</select></Field>
          <Field label="Sede"><select className={inputClass} value={form.office} onChange={(event) => setForm({ ...form, office: event.target.value as AssetInput["office"] })}>{OFFICES.map((office) => <option key={office}>{office}</option>)}</select></Field>
          <div className="flex flex-wrap items-center gap-3 md:col-span-2 lg:col-span-4">
            <button disabled={busy} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60">{busy ? "Creando…" : "Crear activo"}</button>
            {success && <p role="status" className="text-sm font-medium text-emerald-700">{success}</p>}
            {error && <p role="alert" className="text-sm font-medium text-rose-700">{error}</p>}
          </div>
        </form>
      </section>
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><h3 className="font-bold text-slate-900">Activos ({products.length})</h3><button onClick={() => void load()} className="text-sm font-semibold text-brand-700 hover:underline">Actualizar</button></div>
        {loading ? <Loading /> : error && !products.length ? <Retry message={error} onRetry={load} /> : !products.length ? <Empty message="Todavía no hay activos." /> : (
          <div className="overflow-x-auto"><table className="min-w-full divide-y divide-slate-200 text-sm"><thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Activo</th><th className="px-4 py-3">SKU</th><th className="px-4 py-3">Categoría</th><th className="px-4 py-3">Sede</th><th className="px-4 py-3 text-right">Stock actual</th><th className="px-4 py-3 text-right">Acciones</th></tr></thead><tbody className="divide-y divide-slate-100">{products.map((product) => <tr key={product.id}><td className="px-4 py-3 font-semibold text-slate-900">{product.name}</td><td className="px-4 py-3 font-mono text-xs">{product.sku}</td><td className="px-4 py-3">{CATEGORY_LABELS[product.category]}</td><td className="px-4 py-3">{product.office}</td><td className="px-4 py-3 text-right"><Stock value={product.current_stock} /></td><td className="whitespace-nowrap px-4 py-3 text-right"><Link className="font-semibold text-emerald-700 hover:underline" href={`/inventory/orders/inbound?asset=${product.id}`}>Entrada</Link><span className="px-2 text-slate-300">·</span><Link className="font-semibold text-blue-700 hover:underline" href={`/inventory/orders/outbound?asset=${product.id}`}>Salida</Link></td></tr>)}</tbody></table></div>
        )}
      </section>
    </div>
  );
}

export function InventoryHeader({ title, description }: { title: string; description: string }) {
  return <header><p className="text-xs font-bold uppercase tracking-widest text-brand-600">Operaciones · Inventario</p><h2 className="text-2xl font-extrabold text-slate-900">{title}</h2><p className="text-sm text-slate-500">{description}</p></header>;
}
export function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="block"><span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>{children}</label>; }
export function Loading() { return <div className="p-6 text-sm text-slate-500" aria-live="polite">Cargando…</div>; }
export function Empty({ message }: { message: string }) { return <div className="p-8 text-center text-sm text-slate-500">{message}</div>; }
export function Retry({ message, onRetry }: { message: string; onRetry: () => void | Promise<void> }) { return <div className="p-6"><p role="alert" className="text-sm text-rose-700">{message}</p><button onClick={() => void onRetry()} className="mt-3 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold hover:bg-slate-50">Reintentar</button></div>; }
/** Semáforo operativo: saludable >5, bajo 1–5 y agotado 0. */
export function Stock({ value }: { value: number }) { return <span className={`inline-flex min-w-12 justify-center rounded-full px-2.5 py-1 font-bold ${value > 5 ? "bg-emerald-50 text-emerald-700" : value > 0 ? "bg-amber-50 text-amber-700" : "bg-rose-50 text-rose-700"}`}>{value}</span>; }
export { inputClass };
