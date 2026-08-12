# Nexova RFP Intake — Parte 1

## Arquitectura

- `POST /api/rfps` vive en el backend FastAPI existente, guarda el PDF en `data/raw/rfps/`, crea el ticket `analizando`, responde **202** y programa el trabajo en background.
- `data/pipelines/rfp_intake/` contiene el grafo dedicado: conversión PDF→Markdown → clasificador → extracción → orquestador → workers paralelos → synthesizer.
- `GET /api/rfps/{ticket_id}` permite polling; el resultado termina en `analisis_completo` o `descartado`.
- `uis/backoffice/rfps` implementa subida, lista de tickets, polling y desglose por departamento.
- `rfp_tickets`, `rfp_metadata` y `rfp_department_sections` se persisten exclusivamente en PostgreSQL/Supabase mediante la migración `002_create_rfp_intake.sql`. TinyDB no participa.

## Contexto Nexova aplicado

| ID | Responsable | Activación |
| --- | --- | --- |
| `seleccion` | Javier Almeida | Búsqueda ejecutiva, headhunting, roles o posiciones |
| `capacitacion` | Elena Vargas | Formación, training, liderazgo o participantes |
| `soporte` | Roberto Díaz | Soporte externalizado, agentes, 24/7 o SLA |

Los workers reciben metadatos compartidos y sólo extractos relacionados con su departamento. Si falta presupuesto, fecha o volumen, añaden una pregunta abierta; nunca inventan cifras. El handoff de Parte 2 es el conjunto persistido de `DepartmentSection.key_aspects` y `open_questions` asociado al mismo `rfp_id`.

## Evidencia sobre los PDF oficiales

- Vantex Retail Group: aceptada; España/EUR; 5 roles y 40 participantes; `seleccion` + `capacitacion`.
- NubeSoft: aceptada aunque sea un correo informal; Miami/USD; 12 agentes 24/7; sólo `soporte`.
- HireStream: descartada como pitch de proveedor.

Estas expectativas se ejecutan en `tests/pipelines/test_rfp_intake.py` y a través del endpoint multipart en `services/api/tests/test_rfps.py`.

## Configuración

```bash
DATABASE_URL=postgresql://postgres:...@db.example.supabase.co:5432/postgres
cd services/api
PYTHONPATH=../.. uv run uvicorn main:app --reload
```

La base PostgreSQL debe ser accesible al arranque; el repositorio aplica la migración idempotente. Para un smoke local sin HTTP:

```bash
PYTHONPATH=. services/api/.venv/bin/python scripts/process_rfp.py /ruta/documento.pdf
```

La suite encuentra los PDF oficiales en el repositorio hermano `course-syllabus` o en
`RFP_TEST_SAMPLES_DIR`. El contrato de persistencia puede ejecutarse contra una base
PostgreSQL desechable con `TEST_POSTGRES_DATABASE_URL`; sin esa variable sólo se omite
esa prueba de integración, nunca se sustituye PostgreSQL por SQLite o TinyDB.

## Verificación realizada

El 12/08/2026 se ejecutaron las suites con los tres PDF oficiales y PostgreSQL 17 real:

- API y persistencia: **54 pruebas aprobadas**.
- Pipeline y routing: **17 pruebas aprobadas**.
- Backoffice Next.js: compilación de producción aprobada.

## Decisiones y recuperación

- Un departamento desconocido no se activa; queda fuera de la allowlist y debe tratarse como pregunta abierta en una ampliación.
- Un falso negativo conserva PDF, ticket y razón de clasificación para revisión.
- Si un worker falla, el ticket conserva `analizando` más `processing_error=processing_failed`, lo que distingue un job interrumpido de uno activo.
- La Parte 1 usa `BackgroundTasks` porque el volumen inicial es bajo; para producción, el contrato de ticket permanece igual al mover el runner a una cola duradera.
