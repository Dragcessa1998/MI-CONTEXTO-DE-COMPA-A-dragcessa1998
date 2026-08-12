# Nexova Support Agent — herramienta de incidentes

La Parte 2 añade una única tool obligatoria y de solo lectura: `lookup_incident`. Usa directamente `incident_service.get_incident`, la misma capa que alimenta `GET /api/incidents/{id}`; no existe un dataset paralelo.

## Contrato y seguridad

- Entrada tipada: `ticket_id` entero positivo.
- Salida tipada: estado, categoría, origen, sede, título y timestamps del modelo real.
- Transporte: llamada en proceso coherente con el backend monolítico existente.
- Autenticación: no se omite una frontera HTTP; la tool ejecuta dentro del mismo proceso y accede a la capa de servicio, por lo que no requiere un JWT de usuario.
- Solo lectura: el módulo importa únicamente `get_incident`, nunca funciones de alta o actualización.
- Timeout explícito: **4,0 segundos**.
- Fallback: ticket ausente, timeout o indisponibilidad producen una respuesta honesta sin inferir el estado.

## Enrutamiento

- Pregunta documental → RAG.
- Pregunta con `ticket`, `incidente` o `incidencia` y un ID → tool.
- Pregunta que combina ticket con SLA/política/procedimiento/garantía/precio/servicio → RAG y después tool.
- Pregunta de ticket sin ID → solicitud explícita del número; no consulta ni inventa.

Cada corrida muestra en su traza `retrieve_context`, `lookup_incident` o ambos, en el orden ejecutado. Los cuatro evals adicionales cubren tool-only, RAG-only, combinación y fallback.
