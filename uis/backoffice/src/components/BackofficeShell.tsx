"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import NavLinks from "@/components/NavLinks";
import { useAuth } from "@/components/AuthProvider";

const PUBLIC_ROUTES = new Set(["/login", "/register"]);

export default function BackofficeShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading } = useAuth();
  const publicRoute = PUBLIC_ROUTES.has(pathname);

  useEffect(() => {
    if (!loading && !user && !publicRoute) router.replace("/login");
    if (!loading && user && publicRoute) router.replace("/");
  }, [loading, pathname, publicRoute, router, user]);

  if (publicRoute) return <main className="min-h-screen p-6">{children}</main>;
  if (loading || !user) {
    return (
      <main className="grid min-h-screen place-items-center" aria-live="polite">
        <p className="text-sm text-slate-500">Verificando sesión…</p>
      </main>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-slate-900 text-slate-200 md:flex">
        <div className="flex items-center gap-2 px-5 py-4">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-brand-600 text-lg font-black text-white">N</span>
          <div className="leading-tight">
            <span className="block text-sm font-extrabold text-white">Nexova</span>
            <span className="block text-xs text-slate-400">Backoffice</span>
          </div>
        </div>
        <nav className="mt-2 flex-1 px-3" aria-label="Navegación del backoffice">
          <NavLinks />
        </nav>
        <p className="px-5 py-4 text-xs text-slate-500">{user.email}</p>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-slate-200 bg-white px-6 py-3">
          <h1 className="text-sm font-semibold text-slate-500">Backoffice de Nexova</h1>
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
