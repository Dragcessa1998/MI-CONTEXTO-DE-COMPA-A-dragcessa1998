# DEV-53 — Nightly Telemetry Script

## Decisión de ejecución

Nexova ejecuta el job con **cron del sistema**, fuera de FastAPI. La definición
versionada está en `infra/cron/nightly-telemetry.crontab`:

```cron
CRON_TZ=UTC
15 1 * * * cd /workspace && /usr/local/bin/python scripts/nightly_export.py >> /var/log/nexova-nightly.log 2>&1
```

`15 1 * * *` inicia el proceso cada día a las 01:15 UTC. Se eligió cron porque el
trabajo es diario, no necesita un scheduler distribuido adicional y debe tener
un ciclo de vida independiente del servidor HTTP. El proceso de FastAPI no
importa, registra ni ejecuta este job.

## Responsabilidades separadas

| Componente | Persistencia | Responsabilidad |
| --- | --- | --- |
| `scripts/nightly_export.py` + `services/job_runner/` | `orchestration.job_runs` | lock, idempotencia diaria, export CSV y ejecución del subprocess |
| `services/reporting/weekly_pipeline.py` | `reporting.pipeline_runs` | extracción desde `telemetry_events`, deduplicación, quality gate y upsert del agregado semanal |
| `data/raw/telemetry_YYYY-MM-DD.csv` | archivo inmutable | copia de auditoría/recuperación; nunca es el input del pipeline |

El estado `processing` de `job_runs` es el único lock distribuido. El índice
parcial `uq_job_runs_one_processing` vuelve atómica la regla sin añadir una
tabla, columna ni fichero de bloqueo. Otro índice parcial impide más de un
`completed` por `(job_name, target_date)`.

La máquina de estados es:

```text
pending -> processing -> completed
                      \-> failed
```

Antes de adquirir un nuevo ciclo, una ejecución `processing` más antigua que
`JOB_STALE_AFTER_MINUTES` se recupera como `failed`. Esto permite recuperarse de
una terminación no capturable del proceso sin introducir un segundo mecanismo
de lock.

## Instalación y ejecución

Aplicar las migraciones PostgreSQL una vez:

```bash
psql "$DATABASE_URL" -f services/job_runner/migrations/001_create_job_runs.sql
psql "$DATABASE_URL" -f services/reporting/migrations/001_create_weekly_reporting.sql
```

Instalar las dependencias del servicio y ejecutar un backfill controlado:

```bash
python -m pip install -r services/job_runner/requirements.txt
DATABASE_URL='postgresql://…' TARGET_DATE=2026-08-10 python scripts/nightly_export.py
```

Sin `TARGET_DATE`, el script usa el día natural anterior en UTC. La orden del
pipeline por defecto es:

```bash
python -m services.reporting.weekly_pipeline
```

`PIPELINE_COMMAND_JSON` permite sustituir el argv completo en pruebas de
integración sin ejecutar un shell. No debe configurarse en producción.

## Evidencia reproducida localmente

La siguiente ejecución real se hizo el 12/08/2026 sobre una base SQLite
temporal con cinco filas sintéticas para `2026-08-10` (incluida una reentrega
con el mismo `event_id`). PostgreSQL es el destino de producción; SQLite sólo
ofrece un entorno determinista para las pruebas multiproceso.

```text
2026-08-12T14:07:27Z level=INFO job=nightly_export status=pending target_date=2026-08-10 acquiring
2026-08-12T14:07:27Z level=INFO job=nightly_export status=processing run_id=4026a161-fec5-4030-b50d-6db75ee62db4 started
2026-08-12T14:07:27Z level=INFO job=nightly_export status=processing csv=telemetry_2026-08-10.csv rows=5 action=created
2026-08-12T14:07:27Z level=INFO job=nightly_export status=processing pipeline=pipeline_run_id=00ea4378-2260-42d8-aa01-86672fed0294 target_week=2026-08-10 status=completed
2026-08-12T14:07:27Z level=INFO job=nightly_export status=completed run_id=4026a161-fec5-4030-b50d-6db75ee62db4 finished
```

La segunda ejecución para la misma fecha no volvió a exportar ni a iniciar el
pipeline:

```text
2026-08-12T14:07:39Z level=INFO job=nightly_export status=pending target_date=2026-08-10 acquiring
2026-08-12T14:07:39Z level=INFO job=nightly_export status=completed skipped reason=duplicate target_date=2026-08-10
```

Un subprocess que terminó con código 7 dejó el job en `failed`, con
`finished_at` y sin ningún registro `processing` (la ruta absoluta local del
intérprete se normaliza en este extracto):

```text
2026-08-12T14:08:11Z level=INFO job=nightly_export status=pending target_date=2026-08-11 acquiring
2026-08-12T14:08:11Z level=INFO job=nightly_export status=processing run_id=f2be15b5-d1c7-421a-866d-78f28d216f7a started
2026-08-12T14:08:11Z level=INFO job=nightly_export status=processing csv=telemetry_2026-08-11.csv rows=0 action=created
2026-08-12T14:08:11Z level=ERROR job=nightly_export status=failed run_id=f2be15b5-d1c7-421a-866d-78f28d216f7a error=Command returned non-zero exit status 7.
```

Primeras filas del CSV realmente generado (los valores son fixtures, no datos
de personas reales):

```csv
event_id,event_timestamp,session_id,user_id,event_type,schema_version,request_id,properties,ingested_at
event-cost,2026-08-10T12:00:00Z,session-test,user-test,kit_cost_variance_detected,1.0.0,request-4,"{""currency"":""EUR"",""office"":""valencia"",""product_category"":""training_kit"",""product_id"":""kit-1"",""programme_id"":""ventas-b2b"",""quantity"":4}",2026-08-10T12:00:04Z
event-in,2026-08-10T12:00:00Z,session-test,user-test,inbound_order_created,1.0.0,request-0,"{""currency"":""EUR"",""office"":""valencia"",""product_category"":""training_kit"",""product_id"":""kit-1"",""programme_id"":""ventas-b2b"",""quantity"":10,""unit_cost"":12.5}",2026-08-10T12:00:00Z
```

El agregado producido fue Valencia / `ventas-b2b` / semana `2026-08-10`, con
coste de material `125.0 EUR`, una entrega, una rotura y una variación. La
reentrega fue conservada en el CSV de auditoría y deduplicada por el pipeline.

## Pruebas

```bash
python -m pytest services/job_runner/tests -q
```

La suite cubre fecha UTC y override, ejecución completa con subprocess real,
idempotencia, fallo, dos procesos concurrentes y recuperación de un
`processing` obsoleto. Resultado verificado: `5 passed`.
