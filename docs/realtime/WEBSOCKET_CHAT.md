# Real-Time Systems — Parte 2: chat WebSocket

El agente de soporte de primera línea de Roberto Díaz conserva su routing RAG,
consulta read-only de incidentes y reglas de respuesta. Sólo cambia el canal:

```text
ws://localhost:8000/agent/ws/{session_id}?token={jwt}&client_id={client_id}
```

El servidor rechaza antes de eventos de chat un JWT ausente/inválido. La sesión
usa `agent_id=first_line_support`, el `user_id` del JWT, `client_id` y el mismo
`session_id` como identidad estable de conversación.

## Contrato

Cliente→servidor:

```json
{"event":"user_message","data":{"session_id":"chat_0157","text":"¿Cuál es el SLA?"}}
{"event":"interrupt_requested","data":{"session_id":"chat_0157","new_input":"En realidad necesito ayuda con la factura"}}
```

Servidor→consumidores:

- `session_snapshot`: entidad de sesión e historial completo al conectar.
- `user_message`: turno aceptado.
- `token_chunk`: `session_id`, `message_id`, `token`, `sequence`.
- `generation_interrupted`: el mensaje parcial queda `interrupted`.
- `generation_completed`: fin del turno nuevo o normal.

## Cancelación y pub/sub

`ChatHub` crea una única task productora por sesión y publica sus eventos a una
cola por WebSocket. Dos observadores reciben los mismos tokens sin duplicar la
llamada al agente. `interrupt_requested` cancela y espera esa task: el contexto
asíncrono de Responses API se cierra, no se producen más deltas antiguos, el
contenido parcial se conserva y `new_input` inicia otro mensaje asistente.

Cerrar el socket no borra el historial ni cancela la generación. El cliente
reconecta con backoff 1/2/4/8/16/30 s usando las mismas identidades; el primer
evento es `session_snapshot`, por lo que recupera mensajes completos, parciales
e interrumpidos antes de aceptar tokens nuevos.

## Verificación

```bash
uv run --project services/api --group dev pytest -q services/api/tests tests/pipelines
cd uis/backoffice && npm run build
```

La prueba WebSocket interrumpe después del primer chunk, confirma que no aparece
ningún token posterior del `message_id` antiguo, recibe la respuesta redirigida
como turno nuevo y reconecta para comprobar el historial. Otra prueba abre dos
sockets sobre la misma sesión y verifica una sola llamada al productor.
