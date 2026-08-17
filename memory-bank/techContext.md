# Tech Context — Monorepo de Nexova

> Banco de memoria · contexto **técnico**. Léelo al inicio de cada sesión.
> Actualízalo cuando se tomen nuevas decisiones de arquitectura o cambie el stack.

## Estructura del monorepo

```
/                         Raíz del monorepo de la empresa
├── CONTEXT.md            Contexto de la empresa para el hito en curso
├── company-choice.md     Decisión de empresa (Hito 0) — NO modificar
├── AGENTS.md             Protocolo de trabajo de los agentes de código
├── memory-bank/          Contexto persistente (negocio + técnico + progreso)
├── .agents/              Config de agentes de código (reglas + skills)
├── src/                  Lógica de negocio en TS (Hito 2) — fuente única, se importa
├── uis/                  Frontends (Next.js)
│   ├── website/          Web pública corporativa (Hito 4)
│   ├── backoffice/       App interna / dashboards (Hito 4)
│   └── talent-pipeline-tracker/  Tracker de candidaturas (Hito 3)
├── services/            APIs y workers de backend (a partir del Hito 5)
├── packages/shared/     Tipos/utilidades compartidas (@repo/shared-types)
├── data/ · docs/ · infra/ · mcps/ · workflows/ · skills/ · agents/
```

> `.agents/` (config de la herramienta de desarrollo) **no** es lo mismo que `/agents` y `/skills` (producto de la empresa). No los mezcles.

## Stack y decisiones de arquitectura

- **Lenguaje:** TypeScript en modo `strict` en todo el repo. Evitar `any`. Tipos explícitos en funciones exportadas.
- **Frontend:** **Next.js (App Router) + React + Tailwind CSS**. Estado a nivel de componente con hooks; sin librerías externas de estado (Redux/Zustand) salvo justificación.
- **Lógica de negocio:** vive una sola vez en `/src` (Hito 2: scoring/matching de candidatos). Las apps la **importan**, no la copian (evita duplicación).
- **APIs/Backend:** todo lo de servidor va en `/services` (desde el Hito 5).
- **Web pública** → `uis/website`; **lógica interna/dashboards** → `uis/backoffice`, con **layouts separados**.
- **Config por entorno:** variables vía `.env.local` (NO se commitea); cada app incluye `.env.example`.
- **Despliegue reproducible endurecido:** Docker Compose construye website+backoffice, FastAPI, Talent API y Qdrant; Next actúa como proxy same-origin. Sólo las UIs se enlazan a loopback para el reverse proxy; APIs/Qdrant quedan en la red interna. Las imágenes arrancan producción sin reload y como `nexova`/`node`, nunca root.
- **Contrato de telemetría:** envelope JSON Schema 1.0.0 en `docs/telemetry/` con `requestId`, allowlists estrictas por evento, outbox para negocio y separación stream/batch por urgencia.
- **Procesos nocturnos:** cron del sistema ejecuta `scripts/nightly_export.py` fuera de FastAPI. PostgreSQL separa `orchestration.job_runs` (lock/idempotencia/export) de `reporting.pipeline_runs` (ETL). `processing` es el único lock; el CSV es sólo backup y el pipeline lee `telemetry_events`.
- **RAG comercial:** los documentos Nexova se fragmentan en `data/process/rag.py`, se vectorizan con `text-embedding-3-small` y se almacenan en la colección Qdrant `nexova_knowledge`. `data/pipelines/rag.py` mantiene separados retrieval y generación mediante Responses API (`gpt-5.6-luna` por defecto). La API y el backoffice sólo consumen `query()`; no duplican embeddings ni retrieval.
- **RFP intake:** `data/pipelines/rfp_intake/` contiene un grafo dedicado PDF→Markdown→clasificador→orchestrator/workers→synthesizer. El backend existente crea tickets async y PostgreSQL/Supabase es la única fuente de verdad de tickets, metadatos y secciones; `uis/backoffice/rfps` hace polling.
- **RFP response generation:** la Parte 2 reutiliza el handoff persistido de intake y añade un grafo por sección `generator → parallel_evaluators → retry/limit`. Los evaluadores deterministas verifican legibilidad, relevancia y las cinco reglas Nexova; PostgreSQL conserva borrador, historial estructurado e iteración. No se añade otro proceso HTTP ni se vuelve a leer el PDF.
- **RFP approval/completion:** cada departamento activo usa una rama LangGraph `prepare → fixed-arbitrator → interrupt → decision`, identificada como `rfp-{ticket_id}:{department_id}`. `SqliteSaver` persiste checkpoints locales; PostgreSQL conserva las decisiones y el documento final. `Command(resume=...)` reanuda desde el interrupt, un límite de tres revisiones cierra loops y el documento Markdown sólo se genera cuando todas las secciones están aprobadas.
- **RFP real-time / SSE:** el backend publica `rfp_ticket_created` justo después de persistir un ticket `analyzing`. `GET /api/rfps/events` reutiliza el JWT del backoffice, mantiene una cola por conexión, replay corto de 100 eventos y `Last-Event-ID`; la UI consume con `fetch`/`ReadableStream`, backoff 1→30 s, refetch sólo al recuperar y deduplicación por `ticket_id`.
- **Chat WebSocket de soporte:** `/agent/ws/{session_id}` autentica el handshake con el JWT existente y vincula `session_id`, `user_id`, `client_id` y `agent_id=first_line_support`. `ChatHub` conserva historial y un pub/sub por sesión; el productor usa el routing/tools existentes y deltas reales de Responses API. Cancelar la task cierra el stream, marca el mensaje parcial `interrupted` y abre un turno nuevo; reconectar reenvía `session_snapshot`.
- **Seguridad de IA / NIST:** todo punto HTTP que invoca modelos exige JWT y un rate limit por usuario+ruta. `agent/guardrails.py` normaliza y valida prompts directos, y `data/pipelines/rag.py` delimita, escapa y neutraliza contenido documental no confiable antes de pasarlo como datos separados de `instructions`. Los eventos de guardrail sólo conservan metadatos agregables, nunca prompts ni PII. La tool del agente sigue siendo read-only y el documento RFP final mantiene aprobación humana por cada departamento.
- **Seguridad web / OWASP:** JWT incluye `iss`, `aud`, `jti`, expiración y rol. Talent API y RFP exigen `manager/admin`; el token WebSocket viaja como subprotocolo. CORS/hosts/cabeceras usan allowlists; Next 16.3.1 y las dependencias auditadas quedan sin findings. El baseline de host fija `nexova-deploy`, SSH por clave sin root, permisos separados y nftables 22/443.
- **MCP del agente:** `mcps/nexova_tools` es un resource server remoto Streamable HTTP. `mcpauth` publica metadata OAuth y valida bearer tokens OIDC contra `MCP_AUTH_ISSUER`/`MCP_AUTH_AUDIENCE`; scopes de MCP y de dominio se comprueban por tool. `NexovaBackendClient` consume Incidents Manager e Inventory mediante un token de servicio separado. El agente accede exclusivamente por `langchain-mcp-adapters`; no conserva una ruta directa al backend.
- **Memoria del agente:** `agent/memory_store.py` persiste propuestas, decisiones auditables y memorias aprobadas en `data/agent_memory.sqlite3`, nunca en `nexova_knowledge`. `MemoryCoordinator` envuelve turnos del mismo agente de soporte, clasifica confirmaciones cerradas, recupera por términos y consolida con límites de edad/cantidad. La clave `(business_line, memory_key)` deduplica correcciones y `business_line=support` evita mezclar headhunting o formación.
- **Harness del agente:** `agent/system_prompt.py` fija identidad, jerarquía, alcance y límites multi-tenant; `agent/guardrails.py` separa validación estructural, clasificación de ámbito/abuso, aislamiento de texto externo y validación de salida. El endpoint y el stream WebSocket aplican el harness antes/después del mismo agente. Los streams se validan completos antes de emitir y los eventos sólo agregan `action`, `failure_type`, `source` y `rule_id`.
- **CONTEXT por hito:** `CONTEXT.md` se reemplaza con el contexto del hito actual (`content/contexts/<NN>/CONTEXT-nexova.es.md` del syllabus).

## Estado del stack por hito

- **Hito 1** (web estática): HTML5 + Tailwind (Play CDN) + JS de validación — en la raíz.
- **Hito 2** (`/src`): utilidades TS puras (colecciones, búsqueda lineal/binaria, scoring, agregaciones, validaciones). Verificación: `tsc --noEmit` + `tsx src/demo.ts`.
- **Hito 3** (`uis/talent-pipeline-tracker`): Next.js 16.3.1 + React 18 sobre la API del curso `https://playground.4geeks.com/tracker/api/v1`. Filtros/búsqueda por query params; PATCH estado/etapa; notas CRUD; alta/edición.
- **Hito 4** (`uis/website`, `uis/backoffice`): web y app interna en Next.js 16.3.1; backoffice **importa** la lógica del Hito 2.

## Convenciones

- `camelCase` para variables/funciones, `PascalCase` para componentes/tipos/interfaces.
- Funciones puras donde sea posible; manejar casos límite (arrays vacíos, nulos, no encontrado).
- Etiquetas de dominio legibles (ver [[projectbrief]]); nunca mostrar valores crudos de API.
- **Entrega:** Hitos 0-1 push a `main`; **Hito 2+ por rama + Pull Request**.

## Notas de tooling (entorno de desarrollo)

- **Node v24**, npm 11. Hay red.
- ⚠️ La caché npm local puede dar `EACCES`: usar `npm install --cache /tmp/npmcache`.
- Ejecutar binarios locales (`./node_modules/.bin/tsc|tsx|next`), **no** `npx tsc` (instala un paquete viejo erróneo).

Relacionado: [[projectbrief]] · [[progress]]
