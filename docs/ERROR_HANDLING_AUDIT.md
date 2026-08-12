# Auditoría de manejo de errores — Nexova

Fecha: 12/08/2026
Rama: `project/07-error-handling`
Base auditada: `project/06-incidents` (`1a91866`)

## Alcance

Se revisaron las tres interfaces en `uis/`, las dos APIs en `services/`, los
scripts Python en `scripts/` y `services/api/seed.py`, y el paquete compartido.
La búsqueda cubrió llamadas `fetch`/`await`, bloques `catch`/`except`, handlers
500, salidas de consola y accesos opcionales a respuestas.

## Hallazgos y correcciones

| Severidad | Categoría | Ubicación base | Hallazgo | Corrección aplicada |
| --- | --- | --- | --- | --- |
| CRITICAL | RAW ERROR EXPOSURE | `services/talent-api/src/index.ts:306` | El middleware 500 serializaba `err.message`; una excepción podía revelar rutas, credenciales o PII. | Contrato único `{error:{code,message,details?}}`; 500 siempre genérico y JSON malformado se clasifica como 400. Pruebas puras verifican que ningún secreto implícito se serializa. |
| HIGH | RAW ERROR / MISSING CATCH | `uis/talent-pipeline-tracker/src/lib/api.ts:20-50` | Un fallo de red escapaba del wrapper; errores HTTP mostraban `Error 500`, `statusText` o mensajes JSON externos; una respuesta 2xx no JSON podía romper la UI. | `TrackerApiError`, catch específico de red y parseo, mensajes por estado y traducción limitada de campos 400/422. |
| HIGH | SCRIPT EXIT / FILE I/O | `scripts/seed_incidents.py:31-94` | Lectura CSV/TinyDB sin límite de errores; archivo ausente salía por `argparse` y un CSV/DB corrupto podía imprimir traza. | Cabeceras defensivas, captura específica en el límite CLI, stderr sin PII y códigos 0/1 mediante `SystemExit`. |
| HIGH | SCRIPT EXIT / DATABASE I/O | `services/api/seed.py:184-202` | Fallos de TinyDB o validación abortaban con traza; no había contrato de código de salida. | Captura acotada por validación/operación, stderr genérico y retorno 1; éxito retorna 0. |
| MEDIUM | TECHNICAL UI ERRORS | `uis/backoffice/src/lib/api.ts`, `src/lib/suppliers.ts` | Los fallbacks incluían status, path y URL/comando interno; los formularios podían mostrar cualquier `Error.message`. | Mensajes públicos por estado, 500 ignorando el cuerpo, parseo del contrato controlado y fallback fijo para excepciones desconocidas. |
| MEDIUM | LOADING CLEANUP | Formularios en tracker y backoffice | Varias mutaciones limpiaban `submitting/deleting` solo en `catch`; dependían de desmontarse en éxito. | `finally` en crear/editar/eliminar candidato y altas de candidato/proveedor. |
| MEDIUM | NO CALL TO ACTION | Errores inline y `ApiErrorState` | Algunos errores solo mostraban texto; el detalle de candidatura podía renderizar `null`. | Instrucción explícita de reintento/corrección, enlace al panel/listado y estado vacío informativo. |
| LOW | SAFE DEFAULTS | Listados del tracker | Se asumía que `response.data` y `response.total` siempre existían. | `response?.data ?? []`, `response?.total ?? 0` y notas con fallback vacío. |

## Elementos revisados sin cambio

- La web pública no realiza operaciones asíncronas ni llamadas externas.
- La API FastAPI no llama servicios externos; sus excepciones de frontera ya
  devuelven un 500 genérico y sus rutas usan 400/404/422 explícitos.
- `console.log` en `src/demo.ts` corresponde a una demo local con datos de
  ejemplo; el único log del servicio Express anuncia el puerto. Ninguno imprime
  secretos, tokens o errores.
- El rollback amplio de `auth_service.create_user` cubre únicamente la inserción
  del perfil y vuelve a lanzar el error para que el handler de frontera responda
  de forma segura; no engulle el fallo.

## Verificación

- `40 passed` en FastAPI, incluidos fallos de seeder, 500 sin fuga y
  concurrencia; el único aviso procede de una deprecación de Starlette.
- `3 passed` en el contrato de error de la Talent API y `tsc --noEmit` limpio
  en Talent API, website, backoffice y talent-pipeline-tracker.
- Builds de producción correctas de website, backoffice y
  talent-pipeline-tracker.
- Verificación en navegador con Talent API detenida: mensaje humano, estado
  «Sin conexión», botón «Reintentar» funcional y enlace «Volver al panel», sin
  URL, puerto, comando ni detalle técnico expuesto.
- Búsqueda estática final sin `err.message` serializado, `Error ${status}` ni
  `console.error` con datos internos en código de producción.
