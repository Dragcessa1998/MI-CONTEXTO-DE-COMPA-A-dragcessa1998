"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AuthError, authApi } from "@/lib/auth";

export default function ResetPasswordForm({ token }: { token: string }) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState(token ? "" : "El enlace no incluye un token válido.");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    if (password.length < 8) return setError("La nueva contraseña debe tener al menos 8 caracteres.");
    if (password !== confirmation) return setError("La contraseña y la confirmación no coinciden.");
    setBusy(true);
    setError("");
    try {
      await authApi.resetPassword(token, password);
      router.replace("/login?reset=success");
    } catch (cause) {
      setError(cause instanceof AuthError ? cause.message : "El enlace no es válido o ha expirado.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto mt-12 max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
      <h1 className="text-2xl font-extrabold text-slate-900">Crear contraseña nueva</h1>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <label className="block"><span className="mb-1 block text-sm font-medium">Nueva contraseña</span><input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
        <label className="block"><span className="mb-1 block text-sm font-medium">Confirmar contraseña</span><input type="password" required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2" /></label>
        {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
        {error && <Link href="/forgot-password" className="block text-sm font-semibold text-brand-700 hover:underline">Solicitar un enlace nuevo</Link>}
        <button type="submit" disabled={busy || !token} className="w-full rounded-lg bg-brand-600 px-4 py-2.5 font-semibold text-white disabled:opacity-60">{busy ? "Guardando…" : "Restablecer contraseña"}</button>
      </form>
    </section>
  );
}
