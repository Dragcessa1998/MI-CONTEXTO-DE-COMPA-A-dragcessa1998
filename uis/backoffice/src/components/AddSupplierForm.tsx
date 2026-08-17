"use client";

import { useState } from "react";

import { ApiError } from "@/lib/api";
import {
  suppliersApi,
  type Supplier,
  type SupplierCountry,
  type SupplierStatus,
  SUPPLIER_COUNTRIES,
  SUPPLIER_STATUSES,
  SUPPLIER_STATUS_LABELS,
  VALID_CATEGORIES,
  CATEGORY_LABELS,
  CURRENCY_BY_COUNTRY,
} from "@/lib/suppliers";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
    </label>
  );
}

/**
 * Alta de proveedor → POST /suppliers de la Supplier API (FastAPI).
 * Valida lo básico en el cliente (campos requeridos, ≥1 categoría) y muestra
 * inline los errores 422 que devuelva Pydantic. La moneda se fija sola según
 * el país (restricción del CONTEXT: Spain→EUR, USA→USD).
 */
export default function AddSupplierForm({
  onCreated,
  onCancel,
}: {
  onCreated: (created: Supplier) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [country, setCountry] = useState<SupplierCountry>("Spain");
  const [categories, setCategories] = useState<string[]>([]);
  const [monthlyRate, setMonthlyRate] = useState("");
  const [status, setStatus] = useState<SupplierStatus>("active");
  const [renewalDate, setRenewalDate] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const currency = CURRENCY_BY_COUNTRY[country];

  function toggleCategory(category: string) {
    setCategories((prev) =>
      prev.includes(category) ? prev.filter((c) => c !== category) : [...prev, category],
    );
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    // Validación de cliente (la rúbrica pide validar requeridos en el cliente).
    const clientErrors: string[] = [];
    if (!name.trim()) clientErrors.push("El nombre es obligatorio");
    if (categories.length === 0) clientErrors.push("Selecciona al menos una categoría");
    const rate = Number(monthlyRate);
    if (!monthlyRate || Number.isNaN(rate) || rate <= 0) {
      clientErrors.push("La tarifa mensual debe ser un número mayor que 0");
    }
    if (clientErrors.length > 0) {
      setErrors(clientErrors);
      return;
    }

    setSubmitting(true);
    setErrors([]);
    try {
      const created = await suppliersApi.create({
        name: name.trim(),
        country,
        categories,
        monthly_rate: rate,
        currency,
        status,
        contract_renewal_date: renewalDate || null,
        contact_email: contactEmail.trim() || null,
        notes: notes.trim() || null,
      });
      onCreated(created);
    } catch (err) {
      setErrors(
        err instanceof ApiError
          ? err.message.split(" · ")
          : ["No se pudo crear el proveedor. Revisa los datos y vuelve a intentarlo."],
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-900">Nuevo proveedor</h3>
        <span className="hidden text-xs text-slate-400 sm:inline">POST /suppliers · valida Pydantic (422)</span>
      </div>

      {errors.length > 0 && (
        <div role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 py-3 pl-4 pr-4 text-sm text-rose-700">
          <ul className="list-disc space-y-1 pl-4">{errors.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}</ul>
          <p className="mt-2 text-xs">Corrige los campos y vuelve a pulsar “Registrar proveedor”.</p>
        </div>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Nombre del proveedor *">
          <input value={name} onChange={(e) => setName(e.target.value)} className={inputClass} placeholder="LinkedIn Talent Solutions" />
        </Field>
        <Field label="País del contrato *">
          <select value={country} onChange={(e) => setCountry(e.target.value as SupplierCountry)} className={inputClass}>
            {SUPPLIER_COUNTRIES.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </Field>
        <Field label="Moneda (según el país)">
          <input value={currency} readOnly className={`${inputClass} bg-slate-50 text-slate-500`} />
        </Field>
        <Field label="Tarifa mensual *">
          <input type="number" min={0.01} step="0.01" value={monthlyRate} onChange={(e) => setMonthlyRate(e.target.value)} className={inputClass} placeholder="490.00" />
        </Field>
        <Field label="Estado *">
          <select value={status} onChange={(e) => setStatus(e.target.value as SupplierStatus)} className={inputClass}>
            {SUPPLIER_STATUSES.map((option) => (
              <option key={option} value={option}>{SUPPLIER_STATUS_LABELS[option]}</option>
            ))}
          </select>
        </Field>
        <Field label="Renovación del contrato (opcional)">
          <input type="date" value={renewalDate} onChange={(e) => setRenewalDate(e.target.value)} className={inputClass} />
        </Field>
        <Field label="Email de contacto (opcional)">
          <input type="email" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} className={inputClass} placeholder="account@proveedor.com" />
        </Field>
        <div className="sm:col-span-2 lg:col-span-1">
          <Field label="Notas (opcional)">
            <input value={notes} onChange={(e) => setNotes(e.target.value)} className={inputClass} placeholder="Observaciones internas" />
          </Field>
        </div>
      </div>

      <fieldset className="mt-4">
        <legend className="mb-2 text-xs font-medium text-slate-600">Categorías de servicio * (mínimo 1)</legend>
        <div className="flex flex-wrap gap-2">
          {VALID_CATEGORIES.map((category) => {
            const checked = categories.includes(category);
            return (
              <label
                key={category}
                className={`cursor-pointer rounded-full px-3 py-1 text-sm ring-1 ring-inset ${
                  checked
                    ? "bg-brand-600 text-white ring-brand-600"
                    : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleCategory(category)}
                  className="sr-only"
                />
                {CATEGORY_LABELS[category]}
              </label>
            );
          })}
        </div>
      </fieldset>

      <div className="mt-5 flex gap-3">
        <button type="submit" disabled={submitting} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60">
          {submitting ? "Guardando…" : "Registrar proveedor"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          Cancelar
        </button>
      </div>
    </form>
  );
}
