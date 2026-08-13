"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";

const PUBLIC_ROUTES = new Set(["/login", "/register"]);

export default function SessionShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const publicRoute = PUBLIC_ROUTES.has(pathname);

  useEffect(() => {
    if (!loading && !user && !publicRoute) router.replace("/login");
    if (!loading && user && publicRoute) router.replace("/");
  }, [loading, publicRoute, router, user]);

  if (publicRoute) return <main className="min-h-screen px-4 py-8">{children}</main>;
  if (loading || !user) {
    return <main className="grid min-h-screen place-items-center text-sm text-slate-500">Verificando sesión…</main>;
  }

  return (
    <>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand-600 text-lg font-black text-white">N</span>
            <span className="leading-tight">
              <span className="block text-base font-extrabold text-slate-900">Nexova</span>
              <span className="block text-xs text-slate-500">People &amp; Talent — Seguimiento</span>
            </span>
          </Link>
          <nav aria-label="Acciones" className="flex items-center gap-3 text-sm font-medium">
            <Link href="/" className="text-slate-600 hover:text-brand-600">Candidaturas</Link>
            <Link href="/account/profile" className="text-slate-600 hover:text-brand-600">Mi perfil</Link>
            <Link href="/candidates/new" className="rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white hover:bg-brand-700">+ Nueva candidatura</Link>
            <button
              type="button"
              onClick={() => {
                logout();
                router.replace("/login");
              }}
              className="text-slate-600 hover:text-brand-600"
            >
              Salir
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">{children}</main>
    </>
  );
}
