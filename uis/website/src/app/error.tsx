"use client";

export default function WebsiteError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <section role="alert" className="mx-auto my-16 max-w-xl rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900">
      <h2 className="text-xl font-bold">No pudimos cargar esta página</h2>
      <p className="mt-2 text-sm">Reintenta la carga o vuelve al inicio de Nexova.</p>
      <div className="mt-4 flex gap-3">
        <button onClick={reset} className="rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white">Reintentar</button>
        <a href="/" className="rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-800">Ir al inicio</a>
      </div>
    </section>
  );
}
