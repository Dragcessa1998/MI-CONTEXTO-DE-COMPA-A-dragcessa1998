import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";
import SessionShell from "@/components/SessionShell";

export const metadata: Metadata = {
  title: "Talent Pipeline Tracker — Nexova",
  description:
    "Herramienta interna de People & Talent de Nexova para gestionar las candidaturas del proceso de selección.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="min-h-screen">
        <AuthProvider>
          <SessionShell>{children}</SessionShell>
        </AuthProvider>
      </body>
    </html>
  );
}
