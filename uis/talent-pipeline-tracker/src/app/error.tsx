"use client";

export default function TrackerError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <section role="alert" className="mx-auto max-w-xl rounded-xl border border-red-200 bg-red-50 p-6 text-red-900">
      <h2 className="text-xl font-bold">No pudimos mostrar esta página</h2>
      <p className="mt-2 text-sm">La candidatura no se ha modificado. Reintenta o vuelve al listado.</p>
      <div className="mt-4 flex gap-3">
        <button onClick={reset} className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white">Reintentar</button>
        <a href="/" className="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-800">Volver al listado</a>
      </div>
    </section>
  );
}
