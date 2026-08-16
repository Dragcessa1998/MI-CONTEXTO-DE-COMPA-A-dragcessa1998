# PR — Agentic RFP Workflow: Approval & Completion (Part 3/3)

## Qué implementa

- `interrupt` humano real por departamento, checkpoint SQLite durable y
  `Command(resume=...)` explícito.
- ramas aisladas con `rfp-{ticket_id}:{department_id}`; aprobar capacitación no
  desbloquea ni reinicia selección.
- validación estricta de `approve`, `reject` y `request_changes`.
- límite de tres revisiones y arbitraje determinista para los tres triggers de
  Nexova.
- trazas completas por nodo (`agent`, `input`, `output`, `timestamp`).
- UI de aprobación/rechazo y generación automática del documento final sólo al
  aprobar todos los departamentos.

## Ejemplo completo

Input: RFP sintética de Vantex (Madrid) para cinco roles y capacitación de 40
participantes. Parte 1 activa `seleccion` y `capacitacion`; Parte 2 genera dos
secciones en EUR que superan evaluación.

Aprobaciones simuladas:

1. `capacitacion` / Elena Vargas → `approve` mientras `seleccion` sigue
   interrumpida.
2. `seleccion` / Javier Almeida → `approve`.
3. El ticket converge de `waiting_for_approval` a `done` y almacena el Markdown
   final para Marcos Ibáñez.

Reproducción:

```bash
uv run --project services/api python scripts/run_rfp_workflow_e2e.py --workdir /tmp/nexova-rfp-e2e
uv run --project services/api --group dev pytest -q services/api/tests tests/pipelines
cd uis/backoffice && npm run build
```

Prueba/script relevante:

- `scripts/run_rfp_workflow_e2e.py`
- `tests/pipelines/test_rfp_e2e.py`
- `tests/pipelines/test_rfp_approval.py`

Resultado local: 87 tests passed, 2 skipped (PostgreSQL remoto no configurado) y
build de Next.js correcto con 10 rutas.
