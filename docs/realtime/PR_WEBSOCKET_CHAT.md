# Real-Time Systems: WebSocket Chat Streaming (Part 2/2)

## Qué implementa

- `/agent/ws/{session_id}` exige el mismo JWT del backoffice en el handshake y
  vincula la conversación a `session_id`, `client_id`, `user_id` y
  `agent_id=first_line_support`.
- el agente existente mantiene su routing RAG/tool; Responses API entrega deltas
  reales mediante stream asíncrono.
- `ChatHub` desacopla un productor por sesión de todos los sockets consumidores.
- `interrupt_requested` cancela y espera la task activa, conserva el mensaje
  parcial como `interrupted` y abre un turno distinto con `new_input`.
- la UI `/support` pinta tokens en vivo, permite interrumpir/redirigir y
  reconecta con backoff usando las mismas identidades; `session_snapshot`
  rehidrata el historial antes de seguir.

## Ejemplo probado

1. El usuario envía `Háblame del SLA` y recibe `token_chunk` para
   `msg_original`.
2. Envía `interrupt_requested` con `Ahora necesito ayuda con la factura`.
3. El servidor emite `generation_interrupted` para `msg_original`; después de
   ese evento no aparece ningún chunk de ese mensaje.
4. Emite un `user_message` nuevo, chunks con la respuesta redirigida y
   `generation_completed` con otro `message_id`.
5. Al reconectar, `session_snapshot` contiene el asistente original con estado
   `interrupted` y el nuevo con estado `completed`.

## Respuestas de diseño

1. **¿Por qué WebSocket y no SSE?** El cliente debe enviar mensajes e
   interrupciones mientras el servidor sigue produciendo tokens. Esa
   bidireccionalidad simultánea no existe en el stream SSE de la Parte 1.
2. **¿Varios consumidores?** Todos se suscriben a `chat.{session_id}` mediante
   colas independientes. La prueba con dos sockets demuestra una sola llamada al
   agente y eventos idénticos para ambos.
3. **¿Abort frente a HITL?** No se usa `interrupt()` como sustituto. El abort
   cancela la task que itera el stream del proveedor y espera su cierre. HITL
   pausa estado de grafo; aquí el requisito es detener deltas. El parcial se
   conserva y la redirección crea un nuevo turno.

## Verificación

```bash
uv run --project services/api --group dev pytest -q services/api/tests tests/pipelines
cd uis/backoffice && npm run build
```

Resultado: `95 passed, 2 skipped`; las omisiones requieren
`TEST_POSTGRES_DATABASE_URL`. Next.js compila y genera 11 rutas, incluida
`/support`.
