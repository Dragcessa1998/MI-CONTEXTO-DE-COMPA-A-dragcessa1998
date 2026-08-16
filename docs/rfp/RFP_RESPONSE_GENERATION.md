# RFP Response Generation — Parte 2

La Parte 2 consume el ticket persistido por la Parte 1 (`ticket_id`, metadatos y
`key_aspects`). No lee ni vuelve a interpretar el PDF. El grafo vive en
`data/pipelines/rfp_intake/proposal.py` y ejecuta, por cada departamento activo:

```text
generator → readability ┐
          → relevance   ├─ en paralelo → pass / retry
          → compliance  ┘                 └─ límite → needs_human_review
```

El límite predeterminado es de tres iteraciones. Cada evaluación conserva su
iteración, los tres resultados estructurados y feedback accionable. Si se agota
el límite, el último borrador no se pierde: se persiste junto al historial y el
ticket pasa a `needs_human_review` para la Parte 3.

## Reglas de cumplimiento

- `G-90`: garantía de satisfacción de 90 días.
- `CUR-01`: España → EUR; Miami/US → USD.
- `SEL-15`: una búsqueda ejecutiva nunca promete menos de 15 días laborables.
- `SUP-24`: soporte explicita el SLA de respuesta de 24 horas.
- `REF-ANON`: las referencias a clientes actuales se anonimizan.

## API y persistencia

`POST /api/rfps/{ticket_id}/draft` devuelve `202`, cambia el ticket a `drafting`
y ejecuta la generación en background. Durante la evaluación usa
`under_evaluation`; sólo un agotamiento automático termina en
`needs_human_review`. PostgreSQL conserva `draft_content`,
`evaluation_results` y `generation_iteration` en la misma sección creada por la
Parte 1. La migración es `services/api/migrations/003_create_rfp_generation.sql`.

## Evidencia reproducible

Ejemplo que supera los evaluadores:

```json
{
  "section_id": "seleccion",
  "readability": {"pass": true, "score": 100.0},
  "relevance": {"pass": true, "missing_aspects": []},
  "compliance": {"pass": true, "rule_ids": ["G-90", "CUR-01", "REF-ANON", "SEL-15"], "violations": []},
  "overall_pass": true,
  "iteration": 1
}
```

Ejemplo de fallo anclado al contexto:

```json
{
  "section_id": "soporte",
  "compliance": {
    "pass": false,
    "rule_ids": ["G-90", "CUR-01", "REF-ANON", "SUP-24"],
    "violations": ["SUP-24: soporte debe mencionar explícitamente el SLA de respuesta de 24 horas."]
  },
  "overall_pass": false,
  "actionable_feedback": ["SUP-24: soporte debe mencionar explícitamente el SLA de respuesta de 24 horas."]
}
```

Comandos de aceptación:

```bash
uv run --project services/api --group dev pytest -q services/api/tests tests/pipelines
cd uis/backoffice && npm run build
```

El test PostgreSQL real se activa con `TEST_POSTGRES_DATABASE_URL`; sin esa
variable se omite de forma explícita y el resto de la suite permanece local.
