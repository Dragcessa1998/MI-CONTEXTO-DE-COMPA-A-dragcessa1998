"use client";

import { useCallback, useEffect, useState } from "react";

import { Empty, InventoryHeader, Loading, Retry } from "@/components/InventoryProducts";
import { EXIT_TYPE_LABELS, InventoryApiError, inventoryApi, type InventoryOrder } from "@/lib/inventory";

export default function InventoryOrders() {
  const [orders, setOrders] = useState<InventoryOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setOrders(await inventoryApi.listOrders()); }
    catch (reason) { setError(reason instanceof InventoryApiError ? reason.message : "No pudimos cargar el historial."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return <div className="space-y-6"><InventoryHeader title="Historial de movimientos" description="Entradas y salidas trazables, ordenadas de más reciente a más antigua." /><section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex items-center justify-between border-b border-slate-200 px-5 py-4"><h3 className="font-bold text-slate-900">Órdenes ({orders.length})</h3><button onClick={() => void load()} className="text-sm font-semibold text-brand-700 hover:underline">Actualizar</button></div>{loading ? <Loading /> : error ? <Retry message={error} onRetry={load} /> : !orders.length ? <Empty message="Todavía no hay movimientos de inventario." /> : <div className="overflow-x-auto"><table className="min-w-full divide-y divide-slate-200 text-sm"><thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Fecha</th><th className="px-4 py-3">Movimiento</th><th className="px-4 py-3">Activo</th><th className="px-4 py-3">Sede</th><th className="px-4 py-3 text-right">Cantidad</th><th className="px-4 py-3">Detalle</th><th className="px-4 py-3">Usuario</th></tr></thead><tbody className="divide-y divide-slate-100">{orders.map((order) => <tr key={`${order.order_type}-${order.id}`}><td className="whitespace-nowrap px-4 py-3 text-slate-500">{new Intl.DateTimeFormat("es-ES", { dateStyle: "short", timeStyle: "short" }).format(new Date(order.created_at))}</td><td className="px-4 py-3"><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${order.order_type === "inbound" ? "bg-emerald-50 text-emerald-700" : "bg-blue-50 text-blue-700"}`}>{order.order_type === "inbound" ? "Entrada" : "Salida"}</span></td><td className="px-4 py-3"><p className="font-semibold text-slate-900">{order.asset.name}</p><p className="font-mono text-xs text-slate-400">{order.asset.sku}</p></td><td className="px-4 py-3">{order.office}</td><td className="px-4 py-3 text-right font-bold">{order.quantity}</td><td className="px-4 py-3 text-slate-600">{order.order_type === "inbound" ? `Proveedor: ${order.supplier ?? "—"}` : `${order.exit_type ? EXIT_TYPE_LABELS[order.exit_type] : "Salida"}${order.assigned_to ? ` · ${order.assigned_to}` : ""}`}</td><td className="max-w-36 truncate px-4 py-3 font-mono text-xs text-slate-400" title={order.user_uuid}>{order.user_uuid}</td></tr>)}</tbody></table></div>}</section></div>;
}
