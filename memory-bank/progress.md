# Progress — Estado del desarrollo

> Banco de memoria · **estado actual y próximos pasos**. Es el archivo que más
> cambia: actualízalo en cada sesión (qué se completó, qué decisiones se tomaron,
> qué sigue). Un banco de memoria desactualizado deja de ser útil en días.

## Completado

- **Hito 0 — Elige tu empresa** ✅ — `company-choice.md` + `CONTEXT.md` (Nexova). Empresa bloqueada: **Nexova**. Departamentos foco: Operaciones de Selección y Soporte externalizado. _Entregado a `main`._
- **Hito 1 — Web pública** ✅ — `index.html`, `application.html`, `validation.js` (HTML5 + Tailwind + Schema.org + validación JS). _Entregado a `main`._
- **Hito 2 — Lógica de negocio (TS)** ✅ — `src/` con interfaces (Candidate/Vacancy/SelectionProcess), filtros, búsqueda lineal/binaria, **motor de scoring 0-100**, agregaciones y validaciones. `tsc --noEmit` limpio; demo correcta (scores 100/82/10). _Rama `hito-2-fundamentos-programacion` + PR._
- **Hito 3 — Talent Pipeline Tracker** ✅ — `uis/talent-pipeline-tracker` (Next.js 14) sobre la API del curso: listado con filtros/búsqueda, detalle con PATCH, notas CRUD, alta/edición. `next build` OK. _Rama `hito-3-talent-pipeline-tracker` + PR._
- **Hito 4 — Ingeniería impulsada por IA** ✅ — `memory-bank/` + `AGENTS.md` + `.agents/rules` + `.agents/skills`; `uis/website` (web del Hito 1 → componentes React) y `uis/backoffice` (layout propio que **importa** la lógica del Hito 2 vía alias `@logic`, output visible: KPIs + ranking). `next build` OK en ambas. _Rama `milestone-4` + PR._
- **Hito 5 — Backend (proactivo)** ✅ — `services/talent-api` (Express + TS). API central que **reutiliza** la lógica del Hito 2 (alias `@logic`): CRUD completo de candidatos (GET/POST/PUT/PATCH/DELETE), vacantes (GET/POST/DELETE), procesos de selección (GET/POST), `GET /vacancies/:id/ranking` (scoring), `GET /reports/summary` y `GET /reports/fill-rate`, con CORS. Almacenamiento en memoria sembrado del Hito 2. Verificado levantando la API. _Rama `milestone-5` + PR._ Nota: construido según la definición del README; reconciliar con la rúbrica oficial del Hito 5 cuando se publique.
- **Sales Forecasting with a Regression Model (17/08/2026)** ✅ — dataset oficial de 120 meses en `data/raw/nexova_sales.csv`; validación estricta y split cronológico 2016–2023 / 2024–2025 sin fuga. `scripts/train_sales_forecast.py` entrena Random Forest con seed 42, calcula MSE, PSI, Gini normalizado y K2/R², guarda modelo/predicciones/informe y genera una línea real vs predicción con banda P10–P90. Resultado de prueba: RMSE **59.966,20 USD** (**6,25 %** del ingreso medio), Gini **0,8939**, K2/R² **0,5179**; 4 pruebas pasan y la gráfica fue inspeccionada a resolución original.

## Decisiones recientes

- La lógica de negocio del Hito 2 queda como **fuente única en `/src`**; `uis/backoffice` y `services/talent-api` la **importan** mediante alias de TS (`@logic`), sin copiar.
- `uis/website` y `uis/backoffice` tienen **layouts independientes**.
- Cada rama de entrega incluye su propia copia de `/src` para que **compile de forma aislada**; se reconcilia al mergear los PRs en orden (**2 → 3 → 4 → 5**).
- **Unificación en `main`** (junio 2026, a petición del usuario): se fusionaron las 4 ramas de Hito en `main` (sin conflictos de código; `CONTEXT.md` → briefing general de Nexova), de modo que la rama por defecto muestra el **proyecto completo**. Las ramas por Hito permanecen para la entrega.

## Integración full-stack (Hito 4 ↔ Hito 5)

- **Backoffice conectado a la API real** ✅ — `uis/backoffice` ya NO importa la lógica del Hito 2 de forma estática: consume la **Nexova Talent API** en vivo por HTTP (con CORS). Cliente tipado en `src/lib/api.ts`; panel cliente en `src/components/Dashboard.tsx` (KPIs desde `/reports/*`, ranking desde `/vacancies/:id/ranking`, conteos, **alta de candidato** con validación 400 y **recálculo en vivo**, estados carga/error/sin-conexión). Solo reutiliza ya los **tipos** de `@logic`. `tsc --noEmit` limpio + `next build` OK. Verificado de punta a punta contra la API (GET reports/ranking, preflight OPTIONS 204, POST 201 / 400, summary y ranking cambian tras crear).
- **Vista de Procesos (pipeline)** ✅ — backend: nuevo `PATCH /processes/:id` en la talent-api (avanzar etapa, valida `stage`). Frontend: `uis/backoffice` añade la ruta `/processes` (`PipelineBoard.tsx`) — tablero de procesos por etapa que mueve candidatos con `PATCH` y recarga en vivo; navegación lateral con `NavLinks` (resalta ruta activa) y `ApiErrorState` compartido. `tsc` limpio + `next build` OK (5 rutas). Verificado e2e: PATCH 200 + persistencia, stage inválido 400, id inexistente 404.

## Proyecto avanzado: Supplier Directory (FastAPI) — oficial del syllabus

- **Supplier Directory — Lightweight Storage API** ✅ — primer proyecto del track Python: `services/api` (**FastAPI + TinyDB + Pydantic**, gestionado con **uv**). Modelo `Supplier` calcado del CONTEXT oficial de Nexova (Spain/USA, 9 categorías, `active`/`suspended`, regla **moneda↔país**, `rate_updated_at` generado por el sistema). Seeder `uv run seed` idempotente con los 15 proveedores del CONTEXT. Endpoints: POST/GET(+filtros país/categoría)/GET:id/PATCH rate/PATCH status/DELETE, errores 404/422 consistentes, CORS. Frontend: página **/suppliers** del backoffice (tabla, filtros sin recarga, alta con 422 inline, tarifa inline, activar/suspender, badge de estado y aviso de renovación <60 días). Verificado: seeder ×2, 22 checks de endpoints con curl, persistencia tras reinicio, `tsc` + `next build` OK.

## Próximos pasos previstos

- Track oficial Python/FastAPI restante: **#22-24 Autenticación** (JWT sobre la Supplier API → flujos frontend → reset de contraseña) · **#25 Incident Analyzer** (`incidents-nexova.csv`) · **#27 Architecture Proposal**.
- Posible mejora pendiente: conectar también el **tracker standalone** (app del Hito 3) a la API real (el backoffice ya tiene su propia vista de pipeline en `/processes`).

## Tareas del usuario pendientes (no automatizables por el agente)

- Verificar Codespaces y **entregar en la plataforma 4Geeks** la URL/PR de cada hito (cada rama por Hito sigue disponible para su entrega).
- _Ya hecho por el agente:_ `main` unificado con el proyecto completo (Hitos 0-5 + integración + vista de procesos); no es necesario mergear los PRs salvo que la plataforma lo pida.

Relacionado: [[projectbrief]] · [[techContext]]
