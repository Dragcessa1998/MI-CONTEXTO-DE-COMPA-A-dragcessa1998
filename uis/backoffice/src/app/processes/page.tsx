import dynamic from "next/dynamic";

// The interactive board and its mutation controls are only needed on this route,
// so they are emitted as a separate chunk instead of entering the route shell.
const PipelineBoard = dynamic(() => import("@/components/PipelineBoard"), {
  loading: () => <p className="text-sm text-slate-500">Cargando procesos…</p>,
});

/** Página del pipeline de procesos de selección (datos en vivo de la Talent API). */
export default function ProcessesPage() {
  return <PipelineBoard />;
}
