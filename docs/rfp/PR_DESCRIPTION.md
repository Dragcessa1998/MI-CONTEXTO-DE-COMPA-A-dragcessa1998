# PR — Recepción y enrutamiento de RFPs

## Qué cambia

- Añade `POST /api/rfps`, listado y detalle con ticket asíncrono y polling de `analyzing` a `intake_complete` o `discarded`.
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

- 55 pruebas de API aprobadas, incluida ida y vuelta real en PostgreSQL 17 y migración de estados anteriores.
- 18 pruebas del pipeline aprobadas con las tres solicitudes oficiales y aislamiento de contexto por worker.
- Build de producción del backoffice aprobado.
- Vantex activa Selección y Capacitación; NubeSoft activa Soporte; HireStream se descarta.

Salida real resumida de `CONTEXT-nexova-request-1.pdf` (Vantex):

```json
{
  "classification": {"is_rfp": true},
  "client_name": "Vantex Retail Group, S.A.",
  "client_hq": "España",
  "currency": "EUR",
  "volumes": {"roles": 5, "participants": 40},
  "departments_needed": ["seleccion", "capacitacion"],
  "contacts": ["Javier Almeida", "Elena Vargas"],
  "open_question": "Confirmar presupuesto o rango económico disponible."
}
```

## Riesgos y despliegue

- Requiere `DATABASE_URL`; el servicio falla de forma explícita si no apunta a PostgreSQL/Supabase.
- `BackgroundTasks` es adecuado para este primer volumen, pero no sustituye una cola duradera ante reinicios.
- La migración `002_create_rfp_intake.sql` es idempotente y debe aplicarse antes de habilitar la vista a usuarios.
