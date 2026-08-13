"use client";

import { FormEvent, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { AuthError } from "@/lib/auth";

export default function ProfileForm() {
  const { user, updateProfile } = useAuth();
  const [form, setForm] = useState(() => ({ name: user?.profile.name ?? "", phone: user?.profile.phone ?? "", address: user?.profile.address ?? "" }));
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
      <h1 className="text-2xl font-extrabold text-slate-900">Mi perfil</h1>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block"><span className="mb-1 block text-sm font-medium">Email</span><input value={user.email} readOnly className="w-full rounded-lg border border-slate-200 bg-slate-100 px-3 py-2" /></label>
        {(["name", "phone", "address"] as const).map((name) => (
          <label key={name} className="block">
            <span className="mb-1 block text-sm font-medium">{name === "name" ? "Nombre" : name === "phone" ? "Teléfono" : "Dirección"}</span>
            <input value={form[name]} onChange={(event) => setForm((current) => ({ ...current, [name]: event.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
          </label>
        ))}
        {message && <p role="status" className="text-sm text-emerald-700">{message}</p>}
        {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
        <button type="submit" disabled={busy} className="rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white disabled:opacity-60">{busy ? "Guardando…" : "Guardar cambios"}</button>
      </form>
    </section>
  );
}
