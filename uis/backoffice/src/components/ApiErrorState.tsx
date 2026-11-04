/** Estado de error compartido con explicación humana y acciones de recuperación. */
export default function ApiErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6">
      <h3 className="text-sm font-bold text-rose-800">No se pudo cargar desde la API</h3>
      <p className="mt-1 text-sm text-rose-700">{message}</p>
      <p className="mt-3 text-xs text-slate-600">
        Comprueba tu conexión y vuelve a intentarlo. Si el problema continúa, contacta con soporte.
      </p>
      <button
        onClick={onRetry}
        className="mt-4 rounded-lg bg-rose-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-rose-700"
      >
        Reintentar
      </button>
      <a href="/" className="ml-3 inline-block text-sm font-semibold text-rose-700 underline hover:text-rose-900">
        Volver al panel
      </a>
    </div>
  );
}
