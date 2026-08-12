"use client";

export default function BackofficeError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <section role="alert" className="mx-auto max-w-xl rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-900">
      <h2 className="text-xl font-bold">No pudimos mostrar esta sección</h2>
      <p className="mt-2 text-sm">Tus datos no se han modificado. Puedes reintentar o volver al panel.</p>
      <div className="mt-4 flex gap-3">
        <button onClick={reset} className="rounded-lg bg-rose-700 px-4 py-2 text-sm font-semibold text-white">Reintentar</button>
        <a href="/" className="rounded-lg border border-rose-300 bg-white px-4 py-2 text-sm font-semibold text-rose-800">Volver al panel</a>
      </div>
    </section>
  );
}
