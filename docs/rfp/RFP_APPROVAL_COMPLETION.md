# RFP Approval & Completion — Parte 3

La Parte 3 continúa el mismo ticket de las Partes 1 y 2. Cada departamento
activo obtiene una rama LangGraph propia y durable:

```text
prepare → fixed-arbitrator → interrupt(human) → decision
                              ▲                  │
                              └──── revise ──────┘

seleccion      thread_id = rfp-{ticket_id}:seleccion
capacitacion   thread_id = rfp-{ticket_id}:capacitacion
soporte        thread_id = rfp-{ticket_id}:soporte
```

El nodo `human_approval` llama a `interrupt(...)`. `resume_branch` usa
`Command(resume=...)`, por lo que no reinicia `prepare` ni los nodos anteriores.
`SqliteSaver` persiste el estado en `data/checkpoints/` y permite reanudar tras
cerrar y volver a abrir el runtime. SQLite almacena sólo los checkpoints de
LangGraph; PostgreSQL/Supabase sigue siendo la fuente de verdad de tickets,
secciones, decisiones y documento final.

## Decisiones humanas

- `approve`: aprueba únicamente la rama del departamento actual.
- `request_changes`: exige feedback, revisa sólo esa sección y vuelve a pausar.
- `reject`: exige feedback y termina esa rama como rechazada.

El límite es de tres revisiones. Al alcanzarlo, la rama termina rechazada en
lugar de quedar en un loop infinito. Una nueva generación de Parte 2 es el punto
de reentrada previsto para un rechazo definitivo.

## Arbitraje Nexova

El nodo `fixed-arbitrator` no usa un LLM. Detecta y aplica exactamente los
triggers del contexto:

| Trigger | Árbitro fijo | Resolución |
| --- | --- | --- |
| `ttc-vs-training-window` | Marcos Ibáñez | Secuenciar capacitación después de un cierre realista de selección (mín. 15 días laborables). |
| `support-sla-missing` | Roberto Díaz | Bloquear hasta explicitar el SLA de respuesta de 24 horas. |
| `currency-mismatch` | Marcos Ibáñez | Reescribir según sede: España→EUR, Miami/US→USD. |

Una respuesta humana `approve` no puede saltarse un conflicto: el árbitro la
convierte de forma determinista en revisión y vuelve a interrumpir.

## Persistencia y API

- `POST /api/rfps/{ticket_id}/approvals/start`: crea las interrupciones por rama
  y cambia el ticket a `waiting_for_approval`.
- `POST /api/rfps/{ticket_id}/approvals/{department_id}/resume`: valida y reanuda
  una rama con `approve`, `reject` o `request_changes`.
- `GET /api/rfps/{ticket_id}/approvals/trace`: muestra por rama `agent`, `input`,
  `output` y `timestamp` de todos los nodos ejecutados.
- `GET /api/rfps/{ticket_id}/final`: devuelve el Markdown consolidado. Antes de
  que todas las secciones estén aprobadas responde `409`.

PostgreSQL añade `approval_iteration`, `approval_feedback` y
`rfp_final_documents` mediante
`services/api/migrations/004_create_rfp_approval.sql`. El ticket permanece en
`waiting_for_approval` mientras cualquier rama esté pendiente o rechazada; sólo
el synthesizer final lo cambia a `done`.

## Recorrido E2E reproducible

El script genera una RFP PDF sintética, ejecuta intake, generación/evaluación,
interrumpe ambas ramas, aprueba capacitación mientras selección sigue pausada y
finalmente consolida el documento:

```bash
uv run --project services/api python scripts/run_rfp_workflow_e2e.py --workdir /tmp/nexova-rfp-e2e
```

Salida esencial esperada:

```json
{
  "states": ["intake_complete", "under_evaluation", "waiting_for_approval", "done"],
  "approval_order": ["capacitacion", "seleccion"],
  "thread_ids": ["rfp-e2e-vantex:seleccion", "rfp-e2e-vantex:capacitacion"],
  "all_approved": true
}
```

La aceptación automatizada cubre reanudación después de reabrir el runtime,
ramas independientes, límite de iteraciones, los árbitros fijos, guardia del
documento final y el recorrido completo Partes 1→3.
