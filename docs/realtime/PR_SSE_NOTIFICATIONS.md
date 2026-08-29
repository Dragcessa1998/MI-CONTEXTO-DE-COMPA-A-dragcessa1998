# Real-Time Systems: SSE Notifications (Part 1/2)

## Qué implementa

- `rfp_ticket_created` se publica al crear el ticket `analyzing`, antes de iniciar
  el trabajo en background.
- `GET /api/rfps/events` exige el mismo JWT del backoffice y entrega SSE real con
  `id:`, `event:` y `data:` JSON, keep-alive y cabeceras anti-buffering.
- una cola independiente por conexión desacopla el productor de los paneles;
  los últimos 100 eventos permiten replay mediante `Last-Event-ID`.
- el backoffice usa `fetch` + `ReadableStream`, nunca `EventSource`, con backoff
  1/2/4/8/16/30 s, recuperación de lista y deduplicación por `ticket_id`.
- una bandeja `aria-live` muestra las RFP nuevas y el estado de conexión sin
  recargar la página. No hay ninguna llamada a modelo o agente.

Ejemplo de wire real cubierto por prueba:

```text
id: 1
event: rfp_ticket_created
data: {"ticket_id":"tkt_0341","rfp_id":"rfp_0127","status":"analyzing","created_at":"2026-07-24T14:32:00Z"}
```

## Recuperación elegida

El cliente conserva el último `id`, lo envía como `Last-Event-ID` y el servidor
reproduce sólo eventos posteriores. Al recuperar una conexión también se hace
un único refetch de la lista para cubrir reinicios del proceso. Tanto la lista
como la bandeja se deduplican por `ticket_id`.

## Respuestas de diseño

1. **¿Conexiones independientes?** Sí. El productor publica una sola vez y cada
   panel tiene una cola acotada. Con 50 usuarios no se repite el procesamiento;
   en varias réplicas el broker en memoria se sustituiría por Redis/Postgres.
2. **¿Por qué SSE?** La notificación sólo viaja servidor→panel, por lo que SSE
   ofrece framing HTTP y recuperación simples. Si el usuario tuviera que actuar
   por el mismo canal usaríamos WebSocket, que corresponde a la Parte 2.
3. **¿Cómo se evitan pérdidas/duplicados?** Replay `Last-Event-ID`, refetch sólo
   al reconectar y clave estable `ticket_id`.

## Verificación

```bash
uv run --project services/api --group dev pytest -q services/api/tests tests/pipelines
cd uis/backoffice && npm run build
```

Resultado: `91 passed, 2 skipped`; las omisiones exigen
`TEST_POSTGRES_DATABASE_URL`. Next.js compila y genera 10 rutas. La prueba de
endpoint comprueba autenticación, `text/event-stream`, evento nombrado, JSON del
CONTEXT y replay sin duplicados.
