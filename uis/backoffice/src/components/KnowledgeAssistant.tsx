"use client";

import { FormEvent, useState } from "react";
import { askKnowledgeBase } from "@/lib/knowledge";


const EXAMPLES = [
  "¿Cuánto cuesta un programa de formación de 8 semanas?",
  "¿Qué pasa si la terna no me convence?",
  "¿Cuánto suele tardar una búsqueda ejecutiva?",
];

export default function KnowledgeAssistant() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = question.trim();
    if (!normalized) {
      setError("Escribe una pregunta para consultar la base comercial.");
      return;
    }
    setLoading(true);
    setError("");
    setAnswer("");
    try {
      setAnswer(await askKnowledgeBase(normalized));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No pudimos completar la consulta.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mx-auto max-w-4xl space-y-6">
      <header>
        <p className="text-sm font-bold uppercase tracking-[0.18em] text-brand-700">Ventas · Nexova</p>
        <h2 className="mt-2 text-3xl font-black text-slate-950">Asistente de conocimiento comercial</h2>
        <p className="mt-2 max-w-2xl text-slate-600">
          Consulta líneas de servicio, tarifas, SLA y respuestas aprobadas a objeciones. El asistente
          responde sólo con información presente en los documentos internos.
        </p>
      </header>

      <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <label htmlFor="knowledge-question" className="text-sm font-bold text-slate-800">
          Pregunta del SDR
        </label>
        <textarea
          id="knowledge-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={4}
          maxLength={500}
          placeholder="Ej.: ¿Qué garantía incluye el servicio de headhunting?"
          className="mt-2 w-full rounded-xl border border-slate-300 px-4 py-3 text-slate-900 outline-none transition focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
        />
        <div className="mt-3 flex flex-wrap gap-2" aria-label="Preguntas de ejemplo">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setQuestion(example)}
              className="rounded-full border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-brand-500 hover:text-brand-700"
            >
              {example}
            </button>
          ))}
        </div>
        <button
          type="submit"
          disabled={loading}
          className="mt-5 rounded-xl bg-brand-600 px-5 py-3 text-sm font-bold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {loading ? "Consultando fuentes…" : "Consultar"}
        </button>
      </form>

      {loading && (
        <div role="status" aria-live="polite" className="rounded-2xl border border-brand-100 bg-brand-50 p-5 text-brand-900">
          Recuperando los fragmentos más relevantes y preparando una respuesta…
        </div>
      )}
      {error && (
        <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-red-800">
          <p>{error}</p>
          <button type="button" onClick={() => setError("")} className="mt-3 text-sm font-bold underline">
            Corregir o reintentar
          </button>
        </div>
      )}
      {answer && (
        <article aria-live="polite" className="rounded-2xl border border-emerald-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-bold uppercase tracking-wider text-emerald-700">Respuesta fundamentada</p>
          <p className="mt-3 whitespace-pre-wrap text-lg leading-8 text-slate-800">{answer}</p>
        </article>
      )}
    </section>
  );
}
