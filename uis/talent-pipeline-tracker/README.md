# Talent Pipeline Tracker — Nexova (Hito 3)

Herramienta interna del equipo de **People & Talent de Nexova** para gestionar las candidaturas del proceso de selección (puesto activo: _Asistente de Dirección_). Construida con **Next.js (App Router) + React + TypeScript** sobre la API REST del curso.

## Funcionalidades

- **Listado** de candidaturas (`/`) con nombre, puesto, estado y etapa.
- **Filtros** por estado y por etapa, y **búsqueda** por nombre o email — todo vía query params, sin recargar la página.
- **Detalle** (`/candidates/[id]`) con todos los campos; permite **cambiar estado y etapa** (`PATCH`).
- **Notas internas**: listar, añadir y eliminar (`GET/POST/DELETE /records/:id/notes`).
- **Alta** de candidaturas (`/candidates/new`, `POST`) y **edición** (`/candidates/[id]/edit`, `PUT`) con validación.
- **Borrado** de candidaturas (`DELETE /records/:id`) desde el detalle, con confirmación previa. Completa el CRUD de records (Create/Read/Update/Delete).
- Estados de **carga / éxito / error** visibles en cada operación asíncrona.

## Cómo ejecutar

```bash
cd uis/talent-pipeline-tracker
cp .env.example .env.local      # define NEXT_PUBLIC_API_URL
npm install
npm run lint
npm run typecheck
npm test
npm run build
npm run dev                     # http://localhost:3000
```

> La URL de la API se lee de `NEXT_PUBLIC_API_URL`. Si no defines `.env.local`, la app usa por defecto `https://playground.4geeks.com/tracker/api/v1`.

## Estructura

```
src/
├── app/                      # App Router (rutas y páginas)
│   ├── page.tsx              # listado (envuelto en Suspense)
│   └── candidates/
│       ├── new/page.tsx      # alta (POST)
│       └── [id]/
│           ├── page.tsx      # detalle
│           └── edit/page.tsx # edición (PUT)
├── components/               # UI: listado, filtros, detalle, notas, formulario, estados
├── lib/                      # api.ts (acceso a datos) y labels.ts (etiquetas del dominio)
└── types/                    # tipos TypeScript de la API
```

Las etiquetas de estado/etapa se muestran siempre legibles (p. ej. `in_progress` → **En proceso**); los valores crudos de la API nunca aparecen en la interfaz.

Las pruebas unitarias cubren la serialización y los errores del servicio HTTP, además de la combinación de filtros por estado, etapa, nombre y email.
