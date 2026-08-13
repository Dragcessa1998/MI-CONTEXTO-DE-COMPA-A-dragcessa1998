"use client";

import { FormEvent, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { AuthError } from "@/lib/auth";

export default function ProfileForm() {
  const { user, updateProfile } = useAuth();
  const [form, setForm] = useState(() => ({
    name: user?.profile.name ?? "",
    phone: user?.profile.phone ?? "",
    address: user?.profile.address ?? "",
  }));
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!user) return null;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await updateProfile(form);
      setMessage("Perfil actualizado correctamente.");
    } catch (cause) {
      setError(cause instanceof AuthError ? cause.message : "No se pudo actualizar el perfil.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-2xl font-extrabold text-slate-900">Mi perfil</h2>
      <p className="mt-1 text-sm text-slate-500">Gestiona tus datos de contacto vinculados a la cuenta.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Email</span>
          <input value={user.email} readOnly className="w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2 text-slate-600" />
        </label>
        {(["name", "phone", "address"] as const).map((name) => (
          <label key={name} className="block">
            <span className="mb-1 block text-sm font-medium capitalize text-slate-700">
              {name === "name" ? "Nombre" : name === "phone" ? "Teléfono" : "Dirección"}
            </span>
            <input
              value={form[name]}
              onChange={(event) => setForm((current) => ({ ...current, [name]: event.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
          </label>
        ))}
        {message && <p role="status" className="text-sm text-emerald-700">{message}</p>}
        {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
        <button type="submit" disabled={busy} className="rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white hover:bg-brand-700 disabled:opacity-60">
          {busy ? "Guardando…" : "Guardar cambios"}
        </button>
      </form>
    </section>
  );
}
