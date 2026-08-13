"use client";

import { usePathname } from "next/navigation";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";

const NAV = [
  { label: "Panel", href: "/" },
  { label: "Procesos", href: "/processes" },
  { label: "Proveedores", href: "/suppliers" },
  { label: "Mi perfil", href: "/account/profile" },
  { label: "Cambiar contraseña", href: "/account/change-password" },
];

/** Enlaces de la barra lateral con resaltado de la ruta activa. */
export default function NavLinks() {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();
  return (
    <ul className="space-y-1">
      {NAV.map((item) => {
        const active = pathname === item.href;
        return (
          <li key={item.href}>
            <a
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`block rounded-lg px-3 py-2 text-sm font-medium ${
                active ? "bg-brand-600 text-white" : "text-slate-300 hover:bg-slate-800"
              }`}
            >
              {item.label}
            </a>
          </li>
        );
      })}
      <li className="pt-3">
        <button
          type="button"
          onClick={() => {
            logout();
            router.replace("/login");
          }}
          className="w-full rounded-lg px-3 py-2 text-left text-sm font-medium text-slate-300 hover:bg-slate-800"
        >
          Cerrar sesión
        </button>
      </li>
    </ul>
  );
}
