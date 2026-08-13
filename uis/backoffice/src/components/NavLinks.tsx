"use client";

import { usePathname } from "next/navigation";

const NAV = [
  { label: "Panel", href: "/" },
  { label: "Procesos", href: "/processes" },
  { label: "Proveedores", href: "/suppliers" },
  { label: "Incidentes", href: "/incidents" },
  { label: "Analizar CSV", href: "/incident-analysis" },
];

/** Enlaces de la barra lateral con resaltado de la ruta activa. */
export default function NavLinks() {
  const pathname = usePathname();
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
    </ul>
  );
}
