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
- **Desarrollo reproducible:** Docker Compose orquesta un contenedor UI (website + backoffice) y FastAPI; Next actúa como proxy same-origin hacia `http://backend:8000` en la red `nexova-dev`.
- **Contrato de telemetría:** envelope JSON Schema 1.0.0 en `docs/telemetry/` con `requestId`, allowlists estrictas por evento, outbox para negocio y separación stream/batch por urgencia.
- **Persistencia de telemetría:** tabla Supabase/Postgres append-only de ocho columnas, índices por tiempo/tipo y GIN para tags. FastAPI valida cada evento de un lote y envía los válidos mediante una sola petición REST; la service-role key sólo existe en el entorno backend.
- **Informe técnico de telemetría:** paquete Python instalable en `services/telemetry` (Pandas) con carga PostgREST acotada por periodo/tipo, cuatro métricas operacionales y resultados serialisables. FastAPI sirve `GET /telemetry/report` con una ventana UTC única y caché en memoria de 60 s; el backoffice lo visualiza en `/telemetry`.
- **Pipeline de desempeño de negocio (diseño):** fuente append-only `telemetry_events`; agregado semanal por `office`, `programme_id` y semana ISO; destino separado `reporting.weekly_office_program_performance`. La idempotencia combina `eventId`, reconstrucción completa de ventana y upsert transaccional por la clave natural; Prefect orquesta extracción, validación/deduplicación, transformación Pandas y carga. Los futuros endpoints viven en `services/reporting/`, nunca en telemetría.
- **CONTEXT por hito:** `CONTEXT.md` se reemplaza con el contexto del hito actual (`content/contexts/<NN>/CONTEXT-nexova.es.md` del syllabus).

## Estado del stack por hito

- **Hito 1** (web estática): HTML5 + Tailwind (Play CDN) + JS de validación — en la raíz.
- **Hito 2** (`/src`): utilidades TS puras (colecciones, búsqueda lineal/binaria, scoring, agregaciones, validaciones). Verificación: `tsc --noEmit` + `tsx src/demo.ts`.
- **Hito 3** (`uis/talent-pipeline-tracker`): Next.js 14 + React 18 sobre la API del curso `https://playground.4geeks.com/tracker/api/v1`. Filtros/búsqueda por query params; PATCH estado/etapa; notas CRUD; alta/edición.
- **Hito 4** (`uis/website`, `uis/backoffice`): migración de la web a Next.js + app interna que **importa** la lógica del Hito 2.

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
