import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import BackofficeShell from "@/components/BackofficeShell";

export const metadata: Metadata = {
  title: "Nexova — Backoffice",
  description: "Panel interno de Nexova: operación y métricas del banco de talento.",
};

/** Layout propio del backoffice (sidebar), distinto del layout público de website. */
export default function BackofficeLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <AuthProvider><BackofficeShell>{children}</BackofficeShell></AuthProvider>
      </body>
    </html>
  );
}
