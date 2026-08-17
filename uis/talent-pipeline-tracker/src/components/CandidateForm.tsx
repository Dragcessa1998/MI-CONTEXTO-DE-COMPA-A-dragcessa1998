"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createRecord, getRecord, updateRecord, TrackerApiError } from "@/lib/api";
import type { RecordCreateInput } from "@/types/tracker";
import { LoadingState, ErrorState } from "./ui";

interface CandidateFormProps {
  mode: "create" | "edit";
  recordId?: string;
}

interface FormValues {
  full_name: string;
  email: string;
  phone: string;
  position: string;
  experience_years: string;
  linkedin_url: string;
  cv_url: string;
}

type FormErrors = Partial<Record<keyof FormValues, string>>;

const EMPTY_FORM: FormValues = {
  full_name: "",
  email: "",
  phone: "",
  position: "Asistente de Dirección",
  experience_years: "",
  linkedin_url: "",
  cv_url: "",
};

function validate(values: FormValues): FormErrors {
  const errors: FormErrors = {};

  if (values.full_name.trim() === "") {
    errors.full_name = "El nombre completo es obligatorio";
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
    errors.email = "Introduce un email válido";
  }
  if (values.phone.trim() === "") {
    errors.phone = "El teléfono es obligatorio";
  }
  if (values.position.trim() === "") {
    errors.position = "El puesto es obligatorio";
  }
  const years = Number(values.experience_years);
  if (values.experience_years.trim() === "" || Number.isNaN(years) || years < 0) {
    errors.experience_years = "Indica los años de experiencia (0 o más)";
  }
  if (values.linkedin_url.trim() !== "" && !/^https?:\/\/\S+$/i.test(values.linkedin_url.trim())) {
    errors.linkedin_url = "La URL de LinkedIn debe empezar por http:// o https://";
  }
  if (values.cv_url.trim() !== "" && !/^https?:\/\/\S+$/i.test(values.cv_url.trim())) {
    errors.cv_url = "La URL del CV debe empezar por http:// o https://";
  }
  return errors;
}

export default function CandidateForm({ mode, recordId }: CandidateFormProps) {
  const router = useRouter();

  const [values, setValues] = useState<FormValues>(EMPTY_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Estado de carga inicial (solo en modo edición).
  const [loadingInitial, setLoadingInitial] = useState(mode === "edit");
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadRecord = useCallback(async () => {
    if (mode !== "edit" || !recordId) return;
    setLoadingInitial(true);
    setLoadError(null);
    try {
      const record = await getRecord(recordId);
      setValues({
        full_name: record.full_name,
        email: record.email,
        phone: record.phone,
        position: record.position,
        experience_years: String(record.experience_years),
        linkedin_url: record.linkedin_url ?? "",
        cv_url: record.cv_url ?? "",
      });
    } catch (err) {
      setLoadError(err instanceof TrackerApiError ? err.message : "No se pudo cargar la candidatura.");
    } finally {
      setLoadingInitial(false);
    }
  }, [mode, recordId]);

  useEffect(() => {
    loadRecord();
  }, [loadRecord]);

  function setField(field: keyof FormValues, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const validationErrors = validate(values);
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    const payload: RecordCreateInput = {
      full_name: values.full_name.trim(),
      email: values.email.trim(),
      phone: values.phone.trim(),
      position: values.position.trim(),
      experience_years: Number(values.experience_years),
      linkedin_url: values.linkedin_url.trim() === "" ? null : values.linkedin_url.trim(),
      cv_url: values.cv_url.trim() === "" ? null : values.cv_url.trim(),
    };

    setSubmitting(true);
    setSubmitError(null);
    try {
      if (mode === "create") {
        const created = await createRecord(payload);
        router.push(`/candidates/${created.id}`);
      } else if (recordId) {
        await updateRecord(recordId, payload);
        router.push(`/candidates/${recordId}`);
      }
    } catch (err) {
      setSubmitError(err instanceof TrackerApiError ? err.message : "No se pudo guardar la candidatura.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loadingInitial) return <LoadingState label="Cargando datos de la candidatura…" />;
  if (loadError) return <ErrorState message={loadError} onRetry={loadRecord} />;

  const title = mode === "create" ? "Registrar nueva candidatura" : "Editar candidatura";
  const cancelHref = mode === "edit" && recordId ? `/candidates/${recordId}` : "/";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link href={cancelHref} className="text-sm font-medium text-brand-600 hover:text-brand-700">
          ← Cancelar
        </Link>
        <h1 className="mt-2 text-2xl font-extrabold text-slate-900">{title}</h1>
      </div>

      <form onSubmit={handleSubmit} noValidate className="space-y-5 rounded-xl border border-slate-200 bg-white p-6">
        <FormField id="full_name" label="Nombre completo" required error={errors.full_name}>
          <input
            id="full_name"
            type="text"
            value={values.full_name}
            onChange={(e) => setField("full_name", e.target.value)}
            className={inputClass(errors.full_name)}
            placeholder="Ej: María González"
          />
        </FormField>

        <FormField id="email" label="Email" required error={errors.email}>
          <input
            id="email"
            type="email"
            value={values.email}
            onChange={(e) => setField("email", e.target.value)}
            className={inputClass(errors.email)}
            placeholder="nombre@email.com"
          />
        </FormField>

        <FormField id="phone" label="Teléfono" required error={errors.phone}>
          <input
            id="phone"
            type="tel"
            value={values.phone}
            onChange={(e) => setField("phone", e.target.value)}
            className={inputClass(errors.phone)}
            placeholder="+34 612 345 678"
          />
        </FormField>

        <FormField id="position" label="Puesto" required error={errors.position}>
          <input
            id="position"
            type="text"
            value={values.position}
            onChange={(e) => setField("position", e.target.value)}
            className={inputClass(errors.position)}
            placeholder="Ej: Asistente de Dirección"
          />
        </FormField>

        <FormField id="experience_years" label="Años de experiencia" required error={errors.experience_years}>
          <input
            id="experience_years"
            type="number"
            min={0}
            value={values.experience_years}
            onChange={(e) => setField("experience_years", e.target.value)}
            className={inputClass(errors.experience_years)}
            placeholder="Ej: 5"
          />
        </FormField>

        <FormField id="linkedin_url" label="LinkedIn (URL)" error={errors.linkedin_url}>
          <input
            id="linkedin_url"
            type="url"
            value={values.linkedin_url}
            onChange={(e) => setField("linkedin_url", e.target.value)}
            className={inputClass(errors.linkedin_url)}
            placeholder="https://linkedin.com/in/perfil"
          />
        </FormField>

        <FormField id="cv_url" label="CV (URL)" error={errors.cv_url}>
          <input
            id="cv_url"
            type="url"
            value={values.cv_url}
            onChange={(e) => setField("cv_url", e.target.value)}
            className={inputClass(errors.cv_url)}
            placeholder="https://…/cv.pdf"
          />
        </FormField>

        {submitError && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            <p>{submitError}</p>
            <p className="mt-1 text-xs">Corrige los datos si es necesario y vuelve a pulsar “Guardar”.</p>
          </div>
        )}

        <div className="flex flex-col gap-3 border-t border-slate-200 pt-5 sm:flex-row-reverse">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-brand-600 px-6 py-2.5 font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-60 sm:flex-1"
          >
            {submitting ? "Guardando…" : mode === "create" ? "Registrar candidatura" : "Guardar cambios"}
          </button>
          <Link
            href={cancelHref}
            className="rounded-lg border border-slate-300 bg-white px-6 py-2.5 text-center font-semibold text-slate-700 transition hover:bg-slate-50 sm:flex-1"
          >
            Cancelar
          </Link>
        </div>
      </form>
    </div>
  );
}

function inputClass(error?: string): string {
  const base =
    "mt-1 block w-full rounded-lg border px-3 py-2.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-600/30";
  return error
    ? `${base} border-red-400 focus:border-red-500`
    : `${base} border-slate-300 focus:border-brand-600`;
}

function FormField({
  id,
  label,
  required,
  error,
  children,
}: {
  id: string;
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label} {required && <span className="text-brand-700">*</span>}
      </label>
      {children}
      {error && (
        <p role="alert" className="mt-1 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
