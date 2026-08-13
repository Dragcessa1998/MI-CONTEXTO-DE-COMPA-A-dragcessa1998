"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { AuthError, type RegistrationInput } from "@/lib/auth";

const EMPTY_REGISTRATION: RegistrationInput = {
  email: "",
  password: "",
  name: "",
  phone: "",
  address: "",
};

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const { login, register } = useAuth();
  const [form, setForm] = useState(EMPTY_REGISTRATION);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  function change(field: keyof RegistrationInput, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: "" }));
    setMessage("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};
    if (!form.email.trim()) nextErrors.email = "Escribe tu email.";
    if (!form.password) nextErrors.password = "Escribe tu contraseña.";
    if (mode === "register" && form.password.length < 8) {
      nextErrors.password = "Usa al menos 8 caracteres.";
    }
    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }

    setBusy(true);
    setMessage("");
    try {
      if (mode === "login") await login(form.email.trim(), form.password);
      else await register({ ...form, email: form.email.trim() });
      router.replace("/");
    } catch (error) {
      if (error instanceof AuthError) {
        setErrors(error.fields);
        setMessage(error.status === 401 ? "Email o contraseña incorrectos." : error.message);
      } else {
        setMessage("No se pudo completar la operación.");
      }
    } finally {
      setBusy(false);
    }
  }

  const field = (name: keyof RegistrationInput, label: string, type = "text") => (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      <input
        type={type}
        value={form[name]}
        onChange={(event) => change(name, event.target.value)}
        required={name === "email" || name === "password"}
        autoComplete={name === "email" ? "email" : name === "password" ? (mode === "login" ? "current-password" : "new-password") : undefined}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100"
      />
      {errors[name] && <span className="mt-1 block text-sm text-rose-700">{errors[name]}</span>}
    </label>
  );

  return (
    <section className="mx-auto mt-12 max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-widest text-brand-600">Nexova · Acceso seguro</p>
      <h1 className="mt-1 text-2xl font-extrabold text-slate-900">
        {mode === "login" ? "Iniciar sesión" : "Crear cuenta"}
      </h1>
      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        {field("email", "Email", "email")}
        {field("password", "Contraseña", "password")}
        {mode === "register" && (
          <>
            {field("name", "Nombre")}
            {field("phone", "Teléfono", "tel")}
            {field("address", "Dirección")}
          </>
        )}
        {message && <p role="alert" className="text-sm text-rose-700">{message}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-brand-600 px-4 py-2.5 font-semibold text-white hover:bg-brand-700 disabled:cursor-wait disabled:opacity-60"
        >
          {busy ? "Procesando…" : mode === "login" ? "Entrar" : "Registrarme"}
        </button>
      </form>
      <p className="mt-5 text-center text-sm text-slate-500">
        {mode === "login" ? "¿Aún no tienes cuenta? " : "¿Ya tienes una cuenta? "}
        <Link className="font-semibold text-brand-700 hover:underline" href={mode === "login" ? "/register" : "/login"}>
          {mode === "login" ? "Regístrate" : "Inicia sesión"}
        </Link>
      </p>
    </section>
  );
}
