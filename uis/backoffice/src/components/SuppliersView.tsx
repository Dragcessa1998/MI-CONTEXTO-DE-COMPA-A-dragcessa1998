"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import {
  suppliersApi,
  type Supplier,
  type SupplierCategory,
  SUPPLIER_COUNTRIES,
  SUPPLIER_STATUS_LABELS,
  VALID_CATEGORIES,
  CATEGORY_LABELS,
} from "@/lib/suppliers";
import AddSupplierForm from "@/components/AddSupplierForm";
import ApiErrorState from "@/components/ApiErrorState";

type LoadState = "loading" | "ready" | "error";

/**
 * Directorio de Proveedores (página /suppliers). Consume la Supplier API
 * (FastAPI + TinyDB) en vivo: listado con filtros por país y categoría (vía
 * query params, sin recargar la página), alta, edición de tarifa y
 * activar/suspender con el cambio reflejado al instante.
 */
export default function SuppliersView() {
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState("");
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [country, setCountry] = useState("");
  const [category, setCategory] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [actionError, setActionError] = useState("");

  // Nº de secuencia de la petición en vuelo: si el usuario cambia los filtros en
  // rápida sucesión, una respuesta obsoleta no debe pisar a la más reciente.
  const loadSeq = useRef(0);

  const load = useCallback(async () => {
    const seq = ++loadSeq.current;
    setState("loading");
    setError("");
    try {
      const data = await suppliersApi.list({
        country: country || undefined,
        category: category || undefined,
      });
      if (seq !== loadSeq.current) return; // llegó tarde: la descartamos
      setSuppliers(data);
      setState("ready");
    } catch (err) {
      if (seq !== loadSeq.current) return;
      setError(err instanceof ApiError ? err.message : "No se pudieron cargar los proveedores.");
      setState("error");
    }
  }, [country, category]);

  useEffect(() => {
    load();
  }, [load]);

  /** Sustituye un proveedor en la lista por la versión que devolvió la API. */
  function replaceSupplier(updated: Supplier) {
    setSuppliers((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-900">Directorio de proveedores</h2>
          <p className="text-sm text-slate-500">
            Registro oficial y único de servicios externos (antes, la hoja de cálculo de Patricia) — en vivo desde la <strong>Supplier API</strong> (FastAPI + TinyDB).
          </p>
        </div>
        <button
          onClick={() => setShowForm((value) => !value)}
          className="rounded-lg bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-700"
        >
          {showForm ? "Cerrar" : "Nuevo proveedor"}
        </button>
      </div>

      {showForm && (
        <AddSupplierForm
          onCreated={() => {
            setShowForm(false);
            load();
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      {/* Filtros (actualizan la lista sin recargar la página) */}
      <div className="flex flex-wrap items-end gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">País</span>
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
          >
            <option value="">Todos</option>
            {SUPPLIER_COUNTRIES.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-slate-600">Categoría</span>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
          >
            <option value="">Todas</option>
            {VALID_CATEGORIES.map((option) => (
              <option key={option} value={option}>{CATEGORY_LABELS[option]}</option>
            ))}
          </select>
        </label>
        {(country || category) && (
          <button
            onClick={() => {
              setCountry("");
              setCategory("");
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Limpiar filtros
          </button>
        )}
        <span className="ml-auto text-xs text-slate-400">
          {state === "ready" ? `${suppliers.length} proveedor${suppliers.length === 1 ? "" : "es"}` : ""}
        </span>
      </div>

      {actionError && (
        <p role="alert" aria-live="polite" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {actionError}
        </p>
      )}

      {state === "loading" && (
        <div className="h-64 animate-pulse rounded-2xl border border-slate-200 bg-slate-200/60" />
      )}
      {state === "error" && <ApiErrorState message={error} onRetry={load} />}
      {state === "ready" && (
        <SuppliersTable
          suppliers={suppliers}
          onUpdated={replaceSupplier}
          onActionError={setActionError}
        />
      )}
    </div>
  );
}

/** ¿La renovación del contrato cae en los próximos 60 días? (restricción del CONTEXT) */
function renewalBadge(dateStr: string | null): { label: string; className: string } | null {
  if (!dateStr) return null;
  const renewal = new Date(`${dateStr}T00:00:00`);
  if (Number.isNaN(renewal.getTime())) return null;
  const days = Math.ceil((renewal.getTime() - Date.now()) / 86_400_000);
  if (days < 0) return { label: "Vencida", className: "bg-rose-50 text-rose-700 ring-rose-200" };
  if (days <= 60) return { label: `Renueva en ${days} d`, className: "bg-amber-50 text-amber-700 ring-amber-200" };
  return null;
}

function SuppliersTable({
  suppliers,
  onUpdated,
  onActionError,
}: {
  suppliers: Supplier[];
  onUpdated: (supplier: Supplier) => void;
  onActionError: (message: string) => void;
}) {
  if (suppliers.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-400">
        No hay proveedores con esos filtros.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="px-4 py-3">Proveedor</th>
            <th scope="col" className="px-4 py-3">País</th>
            <th scope="col" className="px-4 py-3">Categorías</th>
            <th scope="col" className="px-4 py-3">Tarifa mensual</th>
            <th scope="col" className="px-4 py-3">Renovación</th>
            <th scope="col" className="px-4 py-3">Estado</th>
            <th scope="col" className="px-4 py-3 text-right">Acciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {suppliers.map((supplier) => (
            <SupplierRow
              key={supplier.id}
              supplier={supplier}
              onUpdated={onUpdated}
              onActionError={onActionError}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SupplierRow({
  supplier,
  onUpdated,
  onActionError,
}: {
  supplier: Supplier;
  onUpdated: (supplier: Supplier) => void;
  onActionError: (message: string) => void;
}) {
  const [editingRate, setEditingRate] = useState(false);
  const [rateValue, setRateValue] = useState("");
  const [busy, setBusy] = useState(false);

  const suspended = supplier.status === "suspended";
  const renewal = renewalBadge(supplier.contract_renewal_date);

  async function saveRate() {
    const rate = Number(rateValue);
    if (!rateValue || Number.isNaN(rate) || rate <= 0) {
      onActionError("La tarifa debe ser un número mayor que 0");
      return;
    }
    setBusy(true);
    onActionError("");
    try {
      onUpdated(await suppliersApi.updateRate(supplier.id, rate));
      setEditingRate(false);
    } catch (err) {
      onActionError(err instanceof ApiError ? err.message : "No se pudo actualizar la tarifa");
    } finally {
      setBusy(false);
    }
  }

  async function toggleStatus() {
    setBusy(true);
    onActionError("");
    try {
      onUpdated(await suppliersApi.updateStatus(supplier.id, suspended ? "active" : "suspended"));
    } catch (err) {
      onActionError(err instanceof ApiError ? err.message : "No se pudo cambiar el estado");
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr className={suspended ? "bg-slate-50/80 text-slate-400" : ""}>
      <td className="px-4 py-3">
        <p className={`font-semibold ${suspended ? "text-slate-500" : "text-slate-900"}`}>{supplier.name}</p>
        {supplier.contact_email && <p className="text-xs text-slate-400">{supplier.contact_email}</p>}
      </td>
      <td className="px-4 py-3">{supplier.country}</td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {supplier.categories.map((cat) => (
            <span
              key={cat}
              className="rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-700 ring-1 ring-inset ring-brand-100"
            >
              {CATEGORY_LABELS[cat as SupplierCategory] ?? cat}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3 whitespace-nowrap">
        {editingRate ? (
          <span className="inline-flex items-center gap-1">
            <input
              type="number"
              min={0.01}
              step="0.01"
              value={rateValue}
              onChange={(e) => setRateValue(e.target.value)}
              className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-sm text-slate-900 focus:border-brand-600 focus:outline-none"
              autoFocus
            />
            <button onClick={saveRate} disabled={busy} className="rounded-lg bg-brand-600 px-2 py-1 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50">
              OK
            </button>
            <button onClick={() => setEditingRate(false)} className="rounded-lg border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50">
              ✕
            </button>
          </span>
        ) : (
          <span className={`font-semibold ${suspended ? "text-slate-500" : "text-slate-900"}`}>
            {supplier.monthly_rate.toLocaleString("es-ES", { minimumFractionDigits: 2 })} {supplier.currency}
          </span>
        )}
      </td>
      <td className="px-4 py-3 whitespace-nowrap">
        <span className="text-slate-500">{supplier.contract_renewal_date ?? "—"}</span>
        {renewal && (
          <span className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${renewal.className}`}>
            {renewal.label}
          </span>
        )}
      </td>
      <td className="px-4 py-3">
        {/* Distinción visual activo/suspendido (rúbrica) */}
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${
            suspended
              ? "bg-rose-50 text-rose-700 ring-rose-200"
              : "bg-emerald-50 text-emerald-700 ring-emerald-200"
          }`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${suspended ? "bg-rose-500" : "bg-emerald-500"}`} />
          {SUPPLIER_STATUS_LABELS[supplier.status]}
        </span>
      </td>
      <td className="px-4 py-3 text-right whitespace-nowrap">
        {!editingRate && (
          <button
            onClick={() => {
              setRateValue(String(supplier.monthly_rate));
              setEditingRate(true);
            }}
            disabled={busy}
            className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Tarifa
          </button>
        )}
        <button
          onClick={toggleStatus}
          disabled={busy}
          className={`ml-2 rounded-lg px-2.5 py-1 text-xs font-semibold disabled:opacity-50 ${
            suspended
              ? "bg-emerald-600 text-white hover:bg-emerald-700"
              : "border border-rose-300 bg-white text-rose-700 hover:bg-rose-50"
          }`}
        >
          {suspended ? "Activar" : "Suspender"}
        </button>
      </td>
    </tr>
  );
}
