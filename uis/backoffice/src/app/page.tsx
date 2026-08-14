import dynamic from "next/dynamic";

// The dashboard pulls several report datasets and renders KPI/ranking sections;
// split it from the route shell so navigation does not pay that client bundle cost.
const Dashboard = dynamic(() => import("@/components/Dashboard"), {
  loading: () => <p className="text-sm text-slate-500">Cargando panel…</p>,
});

/**
 * Página del panel. El backoffice ahora consume la Nexova Talent API (Hito 5) en
 * vivo: toda la carga de datos vive en el componente cliente `Dashboard`.
 */
export default function DashboardPage() {
  return <Dashboard />;
}
