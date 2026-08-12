# Nexova Support Agent — LangGraph base

## Alcance

El grafo convierte el RAG comercial existente en un flujo explícito sin duplicar `embed`, `retrieve`, `query` ni `generate_answer`. El endpoint `POST /agent/query` es un adaptador fino y `GET /agent/traces/{run_id}` permite consultar el orden y la salida de cada nodo.

## Estado y rutas

El estado conserva únicamente `run_id`, `question`, `context`, `answer` y `route`; no arrastra historial de conversación.

```text
START → receive_question
  ├─ pregunta vacía → invalid_question → END
  └─ pregunta válida → retrieve_context
       ├─ sin contexto → insufficient_context → END
       └─ con contexto → generate_response → END
```

- `retrieve_context` llama una sola vez a `data.pipelines.rag.retrieve`.
- `generate_response` recibe los chunks recuperados y llama una sola vez a `generate_answer(question, context)`.
- El grafo se valida y compila al importar el módulo.
- `InMemorySaver` guarda checkpoints por `thread_id`; es apropiado para esta entrega local. En producción se sustituiría por `PostgresSaver` sin cambiar los nodos.
- La traza estructurada conserva hasta 200 corridas recientes en memoria y nunca se imprime en logs.

## Ejecutar

```bash
cd services/api
PYTHONPATH=../.. uv run uvicorn main:app --reload
```

```bash
curl -s http://localhost:8000/agent/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"¿Qué garantía ofrece Nexova?"}'

curl -s http://localhost:8000/agent/traces/<run_id>
```

## Evaluación verificable

```bash
PYTHONPATH=.:services/api services/api/.venv/bin/pytest tests/pipelines -q
cd services/api && PYTHONPATH=../.. uv run pytest -q
```

Los evals cubren la pregunta vacía, contexto insuficiente y una respuesta anclada en el CONTEXT (garantía contractual de seis meses), además de comprobar que el checkpoint final es consultable.
