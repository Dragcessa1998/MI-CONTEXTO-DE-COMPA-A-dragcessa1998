"use client";

import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import { AVAILABILITY_OPTIONS } from "@/lib/labels";
import {
  ENGLISH_ORDER,
  SENIORITY_ORDER,
  CANDIDATE_STATUSES,
} from "@logic/types/models";

/** Estado inicial del formulario (valores válidos por defecto para alta rápida). */
const INITIAL = {
  fullName: "",
  email: "",
  phone: "",
  yearsOfExperience: "3",
  skills: "TypeScript, React",
  englishLevel: "B2",
  seniority: "Semi-Senior",
  currentSalary: "3000",
  expectedSalary: "3500",
  availability: "1 month",
  location: "Valencia",
  remoteOnly: false,
  status: "Active",
};

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100";

/** Campo con etiqueta. */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
    </label>
  );
}

/**
 * Formulario de alta de candidato. Envía `POST /candidates` a la Talent API y
 * muestra inline los errores de validación (400) que devuelve la lógica del Hito 2.
 * Al crear con éxito, invoca `onCreated` para que el panel recargue los datos en vivo.
 */
export default function AddCandidateForm({
  onCreated,
  onCancel,
}: {
  onCreated: () => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState(INITIAL);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  function update<K extends keyof typeof INITIAL>(key: K, value: (typeof INITIAL)[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setErrors([]);

    const payload = {
      fullName: form.fullName,
      email: form.email,
      phone: form.phone,
      yearsOfExperience: Number(form.yearsOfExperience),
      skills: form.skills.split(",").map((s) => s.trim()).filter(Boolean),
      englishLevel: form.englishLevel,
      seniority: form.seniority,
      currentSalary: Number(form.currentSalary),
      expectedSalary: Number(form.expectedSalary),
      availability: form.availability,
      location: form.location,
      remoteOnly: form.remoteOnly,
      status: form.status,
    };

    try {
      await api.createCandidate(payload);
      onCreated();
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.message.split(" · "));
      } else {
        setErrors(["No se pudo crear el candidato. Revisa los datos y vuelve a intentarlo."]);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-900">Nuevo candidato</h3>
        <span className="hidden text-xs text-slate-400 sm:inline">
          POST /candidates · valida con la lógica del Hito 2
        </span>
      </div>

      {errors.length > 0 && (
        <div role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 py-3 pl-4 pr-4 text-sm text-rose-700">
          <ul className="list-disc space-y-1 pl-4">{errors.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}</ul>
          <p className="mt-2 text-xs">Corrige los campos y vuelve a pulsar “Crear candidato”.</p>
        </div>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Nombre completo">
          <input required value={form.fullName} onChange={(e) => update("fullName", e.target.value)} className={inputClass} placeholder="Ana Ruiz" />
        </Field>
        <Field label="Email">
          <input type="email" required value={form.email} onChange={(e) => update("email", e.target.value)} className={inputClass} placeholder="ana@mail.com" />
        </Field>
        <Field label="Teléfono">
          <input required value={form.phone} onChange={(e) => update("phone", e.target.value)} className={inputClass} placeholder="+34600000000" />
        </Field>
        <Field label="Años de experiencia">
          <input type="number" min={0} max={50} value={form.yearsOfExperience} onChange={(e) => update("yearsOfExperience", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Habilidades (separadas por comas)">
          <input value={form.skills} onChange={(e) => update("skills", e.target.value)} className={inputClass} placeholder="TypeScript, React" />
        </Field>
        <Field label="Nivel de inglés">
          <select value={form.englishLevel} onChange={(e) => update("englishLevel", e.target.value)} className={inputClass}>
            {ENGLISH_ORDER.map((level) => (
              <option key={level} value={level}>{level}</option>
            ))}
          </select>
        </Field>
        <Field label="Seniority">
          <select value={form.seniority} onChange={(e) => update("seniority", e.target.value)} className={inputClass}>
            {SENIORITY_ORDER.map((level) => (
              <option key={level} value={level}>{level}</option>
            ))}
          </select>
        </Field>
        <Field label="Salario actual ($)">
          <input type="number" min={0} value={form.currentSalary} onChange={(e) => update("currentSalary", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Salario esperado ($)">
          <input type="number" min={0} value={form.expectedSalary} onChange={(e) => update("expectedSalary", e.target.value)} className={inputClass} />
        </Field>
        <Field label="Disponibilidad">
          <select value={form.availability} onChange={(e) => update("availability", e.target.value)} className={inputClass}>
            {AVAILABILITY_OPTIONS.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </Field>
        <Field label="Ubicación">
          <input value={form.location} onChange={(e) => update("location", e.target.value)} className={inputClass} placeholder="Valencia" />
        </Field>
        <Field label="Estado">
          <select value={form.status} onChange={(e) => update("status", e.target.value)} className={inputClass}>
            {CANDIDATE_STATUSES.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </Field>
      </div>

      <label className="mt-4 flex items-center gap-2 text-sm text-slate-600">
        <input type="checkbox" checked={form.remoteOnly} onChange={(e) => update("remoteOnly", e.target.checked)} className="h-4 w-4 rounded border-slate-300" />
        Solo remoto
      </label>

      <div className="mt-5 flex gap-3">
        <button type="submit" disabled={submitting} className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60">
          {submitting ? "Guardando…" : "Crear candidato"}
        </button>
        <button type="button" onClick={onCancel} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          Cancelar
        </button>
      </div>
    </form>
  );
}
