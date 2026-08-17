import type { Metadata } from "next";
import "./globals.css";
import NavLinks from "@/components/NavLinks";
import TelemetryProvider from "@/components/TelemetryProvider";

export const metadata: Metadata = {
  title: "Nexova — Backoffice",
  description: "Panel interno de Nexova: operación y métricas del banco de talento.",
};

/** Layout propio del backoffice (sidebar), distinto del layout público de website. */
export default function BackofficeLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <TelemetryProvider>
          <div className="flex min-h-screen">
          {/* Sidebar */}
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
            <p className="px-5 py-4 text-xs text-slate-400">Operaciones de Selección</p>
          </aside>

          {/* Contenido */}
          <div className="flex min-w-0 flex-1 flex-col">
            <header className="border-b border-slate-200 bg-white px-6 py-3">
              <h1 className="text-sm font-semibold text-slate-500">Backoffice de Nexova</h1>
            </header>
            <main className="flex-1 p-6">{children}</main>
          </div>
          </div>
        </TelemetryProvider>
      </body>
    </html>
  );
}
