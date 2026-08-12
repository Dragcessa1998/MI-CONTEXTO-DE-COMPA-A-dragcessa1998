# Nexova — Backoffice interno (Hito 4 · integrado con la API del Hito 5)

App interna de Nexova (Next.js + TypeScript) con **layout propio** (sidebar), separada
de la web pública. Su panel consume **datos en vivo** de la **Nexova Talent API** (Hito 5)
por HTTP (con CORS), demostrando el stack completo de punta a punta:

```
[ Backoffice :3000 ]  ──fetch (CORS)──►  [ Talent API :4000 ]  ──@logic──►  [ /src lógica Hito 2 ]
```

> Antes (Hito 4) el panel importaba la lógica del Hito 2 de forma **estática** en build.
> Ahora la obtiene **en tiempo de ejecución desde la API real**, que a su vez reutiliza
> esa misma lógica. El backoffice ya solo reutiliza los **tipos** de `@logic` para tipar
> las respuestas (misma fuente de verdad que el backend).

## Qué muestra el panel (`/`)

- **KPIs en vivo** desde `GET /reports/summary` y `GET /reports/fill-rate`: nº de candidatos,
  salario esperado medio, cobertura (% de procesos terminados en *Hired*) y mejor match.
- **Candidatos por estado** y **top de habilidades**.
- **Ranking** de candidatos para la vacante vía `GET /vacancies/:id/ranking` (scoring 0-100 del Hito 2).
- **Alta de candidato** (botón *Nuevo candidato*) → `POST /candidates`. Las validaciones de
  negocio del Hito 2 que devuelve la API (400) se muestran inline; al crear con éxito, el
  panel **se recalcula al instante** (KPIs, ranking y conteos).
- Estados de **carga / error / sin conexión** (con instrucciones para arrancar la API) y botón **Refrescar**.

## Vista de procesos (`/processes`)

Tablero (pipeline) de los **procesos de selección** agrupados por etapa, en vivo desde
`GET /processes`. Mover a un candidato de etapa hace `PATCH /processes/:id` y recarga el
tablero al instante. Las etiquetas de etapa se muestran en español (nunca el valor crudo).

## Vista de proveedores (`/suppliers`)

**Directorio de Proveedores** de Nexova (proyecto *Supplier Directory — Lightweight Storage API*),
en vivo desde la **Supplier API** (FastAPI + TinyDB, `services/api`, puerto `8000`,
configurable con `NEXT_PUBLIC_SUPPLIERS_API_URL`):

- Tabla con nombre, país, categorías (etiquetas en español), tarifa + moneda, renovación y estado.
- **Filtros por país y categoría** vía query params de la API, sin recargar la página.
- **Alta de proveedor** (`POST /suppliers`) con validación en cliente y errores **422** de Pydantic inline.
- **Editar tarifa** inline (`PATCH /suppliers/:id/rate`) y **activar/suspender** (`PATCH /suppliers/:id/status`),
  reflejados en la lista al instante con la respuesta de la API.
- Distinción visual activo (verde) / suspendido (rojo + fila atenuada) y aviso de
  **renovación de contrato en <60 días** (ámbar) o vencida (rojo).

```bash
cd services/api
uv run seed                          # carga los 15 proveedores del CONTEXT
uv run uvicorn main:app --port 8000
```

## Gestor de incidentes (`/incidents`)

Vista autenticada contra la API FastAPI acumulativa:

- Login JWT local y cierre de sesión; el token se conserva en `localStorage` y
  también habilita las llamadas del directorio de proveedores.
- Resumen independiente con totales por estado, categoría, origen y las cuatro
  sedes exactas del CONTEXT de Nexova.
- Formulario con validación inline, carga/disabled, confirmación, errores
  legibles y sede resaltada cuando el origen es **Sede**.
- Listado con filtros, estados loading/error/empty/data, reintento y avance del
  ciclo de vida. Si un PATCH falla, restaura visualmente el estado anterior.

La URL se configura con `NEXT_PUBLIC_PLATFORM_API_URL` (por defecto
`http://localhost:8000`). El seeder histórico se ejecuta desde la raíz:

```bash
services/api/.venv/bin/python scripts/seed_incidents.py
```

## Ejecutar (API + backoffice)

El panel necesita la API corriendo. En **dos terminales**:

```bash
# Terminal 1 — API (Hito 5)
cd services/talent-api
npm install
npm run dev            # http://localhost:4000

# Terminal 2 — Backoffice
cd uis/backoffice
npm install
npm run dev            # http://localhost:3000
```

### Configuración

La URL de la API se toma de `NEXT_PUBLIC_API_URL` (por defecto `http://localhost:4000`).
Para apuntar a otra instancia, crea `uis/backoffice/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:4000
```

Si la API no está arrancada, el panel muestra un estado de error con los pasos para levantarla
(no rompe el build: `next build` no llama a la API).

## Reutilización sin duplicar

`tsconfig.json` mantiene el alias `@logic/* → ../../src/*`, pero ahora **solo para tipos**:

```ts
import type { Candidate, Vacancy } from "@logic/types/models";
```

La capa de acceso vive en [`src/lib/api.ts`](src/lib/api.ts) (cliente tipado, manejo de
errores de red y de negocio) y el panel en [`src/components/Dashboard.tsx`](src/components/Dashboard.tsx).
