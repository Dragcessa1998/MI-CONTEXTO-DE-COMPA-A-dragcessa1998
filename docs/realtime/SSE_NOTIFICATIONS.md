# Real-Time Systems — Parte 1: notificaciones SSE

El backoffice de Marcos Ibáñez abre un único stream autenticado en
`GET /api/rfps/events`. Cuando `POST /api/rfps` persiste el ticket en estado
`analyzing`, publica inmediatamente un evento nombrado:

```text
id: 42
event: rfp_ticket_created
data: {"ticket_id":"...","rfp_id":"...","status":"analyzing","created_at":"..."}
```

No hay llamadas a modelos ni agentes en esta capa. Cada conexión tiene su propia
cola, mientras el productor publica una sola vez. Para una instancia FastAPI es
suficiente el broker en memoria; varias réplicas requerirían sustituirlo por un
backplane compartido sin cambiar el contrato SSE.

## Recuperación y deduplicación

El servidor conserva los últimos 100 eventos. El cliente recuerda el `id` y lo
envía como `Last-Event-ID` al reconectar, por lo que recibe sólo lo ocurrido
durante el corte. Además vuelve a consultar la lista una sola vez por reconexión
para cubrir un reinicio del proceso. La UI deduplica por `ticket_id`; un evento
no provoca una recarga completa de la lista, sólo la consulta de su ticket.

El backoff es progresivo: 1, 2, 4, 8, 16 y máximo 30 segundos. Un evento válido
reinicia el contador. Los keep-alive `: keep-alive` evitan cierres por inactividad.

## Verificación

```bash
uv run --project services/api --group dev pytest -q services/api/tests tests/pipelines
cd uis/backoffice && npm run build
```

Prueba manual de caída: abrir `/rfps`, crear una RFP, detener temporalmente la
API, crear otro ticket desde un cliente autorizado y levantar la API. El estado
visual debe pasar por `Reconectando`, recuperar la lista y no duplicar el ticket.

## Decisiones de diseño

- SSE es adecuado porque esta notificación sólo fluye servidor→panel, funciona
  sobre HTTP y su framing/reconexión son simples. Para reaccionar por el mismo
  canal se necesita WebSocket, que corresponde a la Parte 2.
- Varias personas reciben el mismo evento mediante colas independientes; el
  productor no repite el trabajo por consumidor. Con 50 usuarios se mantiene
  una cola acotada por conexión.
- Se eligió replay corto con `Last-Event-ID`, deduplicación por `ticket_id` y
  refetch único al recuperar la conexión para cubrir también reinicios.
