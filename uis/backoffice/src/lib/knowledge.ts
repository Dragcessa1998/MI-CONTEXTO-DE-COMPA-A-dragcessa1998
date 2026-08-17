const API_URL = process.env.NEXT_PUBLIC_PLATFORM_API_URL ?? "/platform-api";

export class KnowledgeApiError extends Error {}

export async function askKnowledgeBase(question: string): Promise<string> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/knowledge/query`, {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new KnowledgeApiError(
      "No se pudo conectar con el asistente. Comprueba la conexión e inténtalo de nuevo.",
    );
  }

  if (!response.ok) {
    throw new KnowledgeApiError(
      response.status === 422
        ? "Escribe una pregunta concreta antes de enviarla."
        : "El asistente no está disponible temporalmente. Inténtalo de nuevo.",
    );
  }
  try {
    const body = (await response.json()) as { answer?: unknown };
    if (typeof body.answer !== "string" || !body.answer.trim()) throw new Error("invalid answer");
    return body.answer;
  } catch {
    throw new KnowledgeApiError("El asistente devolvió una respuesta no válida. Inténtalo de nuevo.");
  }
}
