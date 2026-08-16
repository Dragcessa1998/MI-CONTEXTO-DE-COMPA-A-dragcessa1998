# Apéndice C. Mapa del repositorio

El proyecto Nexova vive en un único repositorio organizado como **monorepo**: una sola raíz de control de versiones que reúne varias aplicaciones y servicios independientes. Este apéndice es tu mapa de carreteras. Recorre el árbol real del directorio y explica, carpeta por carpeta y archivo por archivo, qué contiene y a qué hito del curso pertenece. Lo usarás para orientarte cuando busques dónde está cada pieza.

En este apéndice aprenderás:

- Cómo está distribuido el monorepo y qué carpetas tienen código real frente a cuáles son simple andamiaje (estructura vacía con un README de ejemplo) heredado de la plantilla de 4Geeks.
- Qué hace cada archivo clave de `src/`, `uis/`, `services/`, `memory-bank/` y `.agents/`.
- Dónde encaja cada archivo raíz (`index.html`, `application.html`, `validation.js`, `company-choice.md`, los README) dentro de los Hitos 0 a 4.

## La raíz del repositorio

En el nivel superior conviven los entregables más tempranos del curso y la configuración global. Los archivos del **Hito 0** (elección y briefing de la empresa) y del **Hito 1** (web pública estática) están aquí, junto al `package.json` que orquesta la lógica del **Hito 2**.

| Archivo raíz | Hito | Qué hace |
|---|---|---|
| `company-choice.md` | 0 | Justifica por qué se elige Nexova como empresa del proyecto. |
| `CONTEXT.md` | 0 | Briefing de la empresa: Nexova Solutions, consultoría de RR. HH. y selección de talento (Valencia y Miami), CEO Laura Mendoza. |
| `index.html` | 1 | Página de aterrizaje (landing) estática de la web pública. |
| `application.html` | 1 | Formulario de postulación de talento. |
| `validation.js` | 1 | Validación de cliente del formulario, con accesibilidad (atributos `aria-*`, `role="alert"`/`role="status"`). |
| `package.json` | 2 | Define los comandos raíz `npm run typecheck` (`tsc --noEmit`) y `npm run demo` (`tsx src/demo.ts`). |
| `tsconfig.json` | 2 | Configuración estricta de TypeScript (`"strict": true`) para la lógica de `src/`. |
| `AGENTS.md` | 4 | Reglas de trabajo para agentes de IA: flujo previo al commit y zonas protegidas. |
| `README.md` / `README.es.md` | — | Documentación general del monorepo (inglés y español). `RUN.md` resume cómo levantar cada pieza. |

::: {.callout .note}
**Nota:** TypeScript es un lenguaje que añade tipos al JavaScript. Un commit es una instantánea guardada de tus cambios en el control de versiones, y un endpoint (o **punto final**) es una dirección a la que una aplicación envía peticiones a un servidor.
:::

## src/ — la lógica del Hito 2

`src/` es la **fuente única de verdad** de la lógica de negocio. Aquí vive el motor de puntuación (scoring) explicable de candidatos, escrito en TypeScript con funciones puras (sin efectos secundarios).

```
src/
├── types/models.ts        # Candidate, Vacancy, SelectionProcess, ValidationResult, ScoredCandidate
├── utils/
│   ├── collections.ts     # agrupar, contar, ordenar colecciones
│   ├── search.ts          # búsqueda binaria por salario
│   ├── transformations.ts # motor de scoring de 5 componentes (40+20+15+15+10 = 100)
│   └── validations.ts     # validaciones de datos de candidatos y vacantes
├── data/sampleData.ts     # datos de ejemplo para la demostración
└── demo.ts                # script que ejecuta la demostración de extremo a extremo
```

El reparto de los 100 puntos se ve directamente en `src/utils/transformations.ts`: habilidades (máximo 40), experiencia (20), seniority (15), nivel de inglés (15) y disponibilidad (10).

::: {.callout .important}
**Importante:** las apps de `uis/` y los servicios de `services/` importan estos tipos mediante el alias `@logic`, configurado en cada `tsconfig.json` como `"@logic/*": ["../../src/*"]`. El backoffice y la talent-api **reutilizan** esta lógica, no la copian. Si tocas `src/`, lo tocas todo.
:::

## uis/ — las interfaces

`uis/` agrupa las tres aplicaciones de interfaz, todas con Next.js 16 (App Router), React 18 y Tailwind CSS.

- **`uis/website/`** (Hito 4): la web pública del Hito 1 migrada a componentes de React. Sus componentes viven en `src/components/website/` (`Hero.tsx`, `Services.tsx`, `ApplyForm.tsx`, etc.), con la ruta `/apply` para el formulario.
- **`uis/talent-pipeline-tracker/`** (Hito 3): aplicación que consume la API del curso (`NEXT_PUBLIC_API_URL`). Implementa el CRUD completo de registros. La función `deleteRecord` está en `src/lib/api.ts`, y el borrado con confirmación en línea (`role="alertdialog"`) en `src/components/CandidateDetail.tsx`. Las etiquetas legibles de dominio están en `src/lib/labels.ts`.
- **`uis/backoffice/`** (Hito 4): panel interno con barra lateral. Consume la talent-api **real** por HTTP (`fetch` con CORS) y solo importa **tipos** de `@logic`. Sus rutas son `/` (panel), `/processes` (tablero del pipeline) y `/suppliers` (proveedores). El cliente tipado de proveedores está en `src/lib/suppliers.ts`, con la vista en `src/components/SuppliersView.tsx` y el alta en `AddSupplierForm.tsx`.

## services/ — los backends

`services/` contiene los dos servidores reales del proyecto.

**`services/talent-api/`** (Hito 4): backend en Express y TypeScript, ejecutado con `tsx`. Todo está en `src/index.ts`, que expone el CRUD de candidatos, vacantes y procesos, además de `GET /vacancies/:id/ranking`, `GET /reports/summary` y `GET /reports/fill-rate`. Maneja CORS con preflight y reutiliza `@logic`.

**`services/api/`** (proyecto oficial "Lightweight Storage API"): el Supplier Directory, hecho con FastAPI, TinyDB y Pydantic, gestionado con la herramienta `uv`.

| Archivo | Qué hace |
|---|---|
| `models.py` | Modelos Pydantic (`SupplierIn`, `SupplierOut`, `RateUpdate`, `StatusUpdate`) y el enum `SupplierStatus`. Valida país↔moneda, fecha real y tarifa positiva. |
| `routes/suppliers.py` | POST (201), GET con filtros `?country=&category=`, GET/{id} (404), PATCH `/{id}/rate`, PATCH `/{id}/status`, DELETE. |
| `main.py` | Arranque y conversión de `RequestValidationError` a 422. |
| `database.py` | TinyDB persistente en `suppliers.db.json`. |
| `seed.py` | Carga idempotente de 15 proveedores; se ejecuta con `uv run seed`. |

::: {.callout .warning}
**Aviso:** en macOS, si el repositorio está en el Escritorio o iCloud, el flag `UF_HIDDEN` sobre `.venv` rompe `uv run seed` con `ModuleNotFoundError`. Solución: `chflags -R nohidden .venv` y reintentar, o usar `uv run python seed.py`.
:::

## memory-bank/ y .agents/ — infraestructura para IA (Hito 4)

- **`memory-bank/`**: contexto persistente para agentes de IA, con `projectbrief.md`, `techContext.md` y `progress.md`.
- **`.agents/`**: reglas y habilidades. `rules/monorepo-conventions.md` (con alcance `scope: always`) y la habilidad `skills/scaffold-ui-app/SKILL.md`.

## docs/ y el andamiaje de la plantilla

`docs/` contiene documentación de apoyo. El resto de carpetas raíz son **andamiaje intencional** de la plantilla de 4Geeks: solo traen un README de ejemplo (a veces algún `_template`), sin lógica del proyecto. No las confundas con componentes activos.

| Carpeta | Estado |
|---|---|
| `agents/`, `data/`, `packages/`, `scripts/` | Andamiaje (README stub; `packages/shared` y `agents/_template` solo traen plantillas vacías). |
| `infra/`, `internal/`, `mcps/`, `shared/`, `skills/`, `workflows/` | Andamiaje (README stub). |

## Resumen

- El monorepo separa lógica (`src/`), interfaces (`uis/`) y backends (`services/`), unidos por el alias `@logic`, que evita duplicar la lógica de negocio.
- Los archivos raíz `index.html`, `application.html`, `validation.js`, `company-choice.md` y `CONTEXT.md` corresponden a los Hitos 0 y 1.
- `services/api` (FastAPI) y `services/talent-api` (Express) son los dos backends reales; `uis/backoffice` consume el segundo por HTTP y solo importa tipos del primero.
- `memory-bank/`, `.agents/` y `AGENTS.md` aportan la infraestructura para agentes de IA del Hito 4.
- Carpetas como `agents/`, `packages/`, `scripts/`, `infra/`, `mcps/`, `shared/`, `skills/` y `workflows/` son andamiaje de plantilla y solo contienen README de ejemplo.