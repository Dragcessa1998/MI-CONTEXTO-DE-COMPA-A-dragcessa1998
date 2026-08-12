# RAG comercial de Nexova — diseño y operación

## Objetivo y contrato

El asistente ayuda a los 18 account managers y SDRs de Marcos Ibáñez a
responder con seguridad sobre líneas de servicio, tarifas, SLA y objeciones.
La única interfaz de aplicación es `query(question) -> str`; el endpoint
`POST /knowledge/query` devuelve exclusivamente `{ "answer": "…" }`.

La respuesta nunca es un fragmento crudo de Qdrant. `query()` ejecuta
literalmente `retrieve()` y después `generate_answer(question, context)`.

```text
docs/company-knowledge-base/*.md
          │ setup() · chunks semánticos · embed()
          ▼
Qdrant: nexova_knowledge
          │ retrieve(question, k, min_score)
          ▼
payloads filtrados ──► prompt comercial ──► Responses API ──► answer
```

## Corpus y chunking

Se versionan los cuatro documentos en español definidos por el CONTEXT:

- `nexova-service-lines.es.md`
- `nexova-pricing-model.es.md`
- `nexova-hiring-process-sla.es.md`
- `nexova-objection-handling.es.md`

El parser conserva cada bloque Markdown separado por un blanco como unidad
semántica. Una línea introductoria corta se fusiona con el bloque siguiente;
nunca se corta una condición, una lista de precio ni la respuesta asociada a
una objeción. El título se antepone a cada fragmento para mantener su contexto.
Cada documento produce al menos tres chunks.

Cada payload conserva `source_document`, `section`, `company=nexova`,
`language=es`, `chunk_index` y `text`. Los IDs UUID5 dependen de fuente,
posición y contenido. `setup()` usa además una estrategia clara de
**clear-and-reload**: recrea la colección completa antes del upsert, por lo que
una segunda ejecución no duplica puntos ni deja chunks antiguos.

## Embeddings y recuperación

- Modelo de embeddings: `text-embedding-3-small`.
- Dimensión predeterminada: 1536.
- Distancia: coseno en Qdrant.
- Colección exacta: `nexova_knowledge`.
- `k` por defecto: 5.
- `min_score` inicial: 0,35, configurable mediante `RAG_MIN_SCORE`.

La misma función `embed()` se usa al indexar y al consultar. El modelo de
embeddings es distinto del generador. El texto sólo normaliza espacios antes
de enviarse; no se traducen ni eliminan cifras o condiciones comerciales.

`retrieve()` pasa `score_threshold` a Qdrant y puede devolver menos de `k`,
incluido cero. Entrega diccionarios de payload, no objetos del SDK ni scores a
la capa HTTP. El umbral se valida con el conjunto versionado de 11 preguntas;
el gate del CONTEXT es Recall@3 ≥ 80 %.

## Generación y guardrails

El generador es `gpt-5.6-luna` mediante Responses API. Se eligió la variante de
alto volumen por coste/latencia, manteniendo `text-embedding-3-small` como
modelo independiente. El prompt ordena:

- responder en español y desde la perspectiva comercial de Nexova;
- usar exclusivamente los chunks recuperados;
- no ofrecer descuentos sobre el 22 % sin aprobación humana;
- presentar plazos como promedios;
- reconocer sólo la garantía contractual de reemplazo de seis meses;
- ser transparente respecto a competidores;
- admitir falta de información y ofrecer escalado humano.

Los modelos se configuran por entorno para poder fijar otra variante tras
evals, sin mezclar sus responsabilidades. La clave sólo vive en `.env.local`
o en el gestor de secretos del despliegue.

## Ejecución

```bash
source /ruta/segura/.env.local
uv run --project services/api python scripts/setup_rag.py
uv run --project services/api python scripts/evaluate_rag.py
uv run --project services/api python scripts/query_knowledge.py \
  "¿Qué pasa si la terna no me convence?"
uv run --project services/api pytest tests/pipelines/test_rag.py services/api/tests/test_knowledge.py
```

Sin `QDRANT_URL`, el cliente usa almacenamiento Qdrant local persistente en
`data/qdrant/` (ignorado por Git). Compose levanta Qdrant como servicio separado
y configura `QDRANT_URL=http://qdrant:6333`.

## Pruebas y fuentes técnicas

Las pruebas unitarias simulan OpenAI y Qdrant: verifican chunking, metadatos,
modelo separado, umbral, ausencia de objetos crudos, orden retrieve→generate,
respuesta sin contexto y contrato HTTP. `evaluate_rag.py` es la comprobación
real del retriever sobre la colección indexada.

Fuentes primarias:

- OpenAI, [Vector embeddings](https://developers.openai.com/api/docs/guides/embeddings): mismo modelo en indexación/consulta, similitud coseno y dimensión 1536.
- OpenAI, [Text generation](https://developers.openai.com/api/docs/guides/text): uso de Responses API y `output_text`.
- OpenAI, [Model guidance](https://developers.openai.com/api/docs/guides/latest-model): familia GPT-5.6 y variantes por coste/capacidad.
- Qdrant, [Python client](https://python-client.qdrant.tech/): colecciones, upsert y búsqueda vectorial.
