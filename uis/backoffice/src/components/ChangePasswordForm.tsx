"use client";

import { FormEvent, useState } from "react";

import { AuthError, authApi } from "@/lib/auth";

export default function ChangePasswordForm() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (newPassword.length < 8) {
      setError("La nueva contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (newPassword !== confirmation) {
      setError("La contraseña nueva y la confirmación no coinciden.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await authApi.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmation("");
      setMessage("Contraseña actualizada correctamente.");
    } catch (cause) {
      setError(cause instanceof AuthError ? cause.message : "No se pudo cambiar la contraseña.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-extrabold text-slate-900">Cambiar contraseña</h1>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block"><span className="mb-1 block text-sm font-medium">Contraseña actual</span><input type="password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
        <label className="block"><span className="mb-1 block text-sm font-medium">Nueva contraseña</span><input type="password" required value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
        <label className="block"><span className="mb-1 block text-sm font-medium">Confirmar contraseña</span><input type="password" required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
        {message && <p role="status" className="text-sm text-emerald-700">{message}</p>}
        {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
        <button type="submit" disabled={busy} className="rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white disabled:opacity-60">{busy ? "Guardando…" : "Cambiar contraseña"}</button>
      </form>
    </section>
  );
}
