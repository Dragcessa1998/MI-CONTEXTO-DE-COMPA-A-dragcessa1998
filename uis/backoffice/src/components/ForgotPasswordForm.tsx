"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

import { authApi } from "@/lib/auth";

const CONFIRMATION = "Si la dirección está registrada, recibirás un enlace en breve.";

export default function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitted || busy) return;
    setBusy(true);
    setError("");
    try {
      await authApi.forgotPassword(email.trim());
      setSubmitted(true);
    } catch {
      setError("No se pudo enviar la solicitud. Inténtalo de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto mt-12 max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-widest text-brand-600">Recuperación segura</p>
      <h1 className="mt-1 text-2xl font-extrabold text-slate-900">Restablecer contraseña</h1>
      <p className="mt-2 text-sm text-slate-500">Te enviaremos un enlace de un solo uso si la cuenta existe.</p>
      {submitted ? (
        <p role="status" className="mt-6 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{CONFIRMATION}</p>
      ) : (
        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Email</span>
            <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} disabled={busy} className="w-full rounded-lg border border-slate-300 px-3 py-2" />
          </label>
          {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
          <button type="submit" disabled={busy} className="w-full rounded-lg bg-brand-600 px-4 py-2.5 font-semibold text-white disabled:opacity-60">{busy ? "Enviando…" : "Enviar enlace"}</button>
        </form>
      )}
      <Link href="/login" className="mt-5 block text-center text-sm font-semibold text-brand-700 hover:underline">Volver al inicio de sesión</Link>
    </section>
  );
}
