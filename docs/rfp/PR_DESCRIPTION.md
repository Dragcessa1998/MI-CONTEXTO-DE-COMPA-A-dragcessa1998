# PR — Recepción y enrutamiento de RFPs

## Qué cambia

- Añade `POST /api/rfps`, listado y detalle con ticket asíncrono y polling.
- Convierte PDF a Markdown y ejecuta un grafo LangGraph classifier → orchestrator → workers paralelos → synthesizer.
- Enruta exclusivamente a Selección, Capacitación y Soporte con sus responsables Nexova.
- Persiste tickets, metadatos JSONB y secciones sólo en PostgreSQL/Supabase.
- Añade la vista `/rfps` al backoffice para subir, seguir y revisar solicitudes.

## Por qué

Nexova necesita distinguir solicitudes de clientes de pitches de proveedores, extraer hechos sin inventar datos y entregar a cada departamento únicamente el contexto que le corresponde.

## Cómo verificar

```bash
cd services/api
PYTHONPATH=../.. uv run pytest -q

cd ../..
PYTHONPATH=.:services/api services/api/.venv/bin/python -m pytest tests/pipelines -q

cd uis/backoffice
npm run build
```

Para incluir la persistencia real, define `TEST_POSTGRES_DATABASE_URL` con una base PostgreSQL desechable. Los PDF oficiales se encuentran automáticamente en el repositorio hermano `course-syllabus` o mediante `RFP_TEST_SAMPLES_DIR`.

## Evidencia

- 54 pruebas de API aprobadas, incluida ida y vuelta real en PostgreSQL 17.
- 17 pruebas del pipeline aprobadas con las tres solicitudes oficiales.
- Build de producción del backoffice aprobado.
- Vantex activa Selección y Capacitación; NubeSoft activa Soporte; HireStream se descarta.

## Riesgos y despliegue

- Requiere `DATABASE_URL`; el servicio falla de forma explícita si no apunta a PostgreSQL/Supabase.
- `BackgroundTasks` es adecuado para este primer volumen, pero no sustituye una cola duradera ante reinicios.
- La migración `002_create_rfp_intake.sql` es idempotente y debe aplicarse antes de habilitar la vista a usuarios.
