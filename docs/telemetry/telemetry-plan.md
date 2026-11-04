# Plan de telemetría de Nexova

Versión: 1.0.0
Fecha: 12/08/2026
Responsables: Tecnología e Infraestructura (Sergio Molina), L&D (Elena Vargas)
y RRHH (Patricia Solís)

## 1. Objetivo y alcance

Este plan define qué debe emitir el sistema de inventario de materiales de
formación, certificación y onboarding, y qué señales transversales debe capturar
el backoffice de Nexova. Es un contrato previo a la instrumentación: no cambia
stock ni contiene código de captura.

El catálogo tiene **18 eventos**: **5 obligatorios** del contexto oficial y
**13 oportunidades identificadas**. Cubre negocio/inventario, autenticación,
rendimiento, errores y navegación. Las señales permiten operar en tiempo real
cuando existe riesgo inmediato y analizar tendencias en batch cuando la
decisión tolera demora.

### Reglas de negocio que el diseño preserva

- `Product` es material `training_kit`, `certification` u
  `onboarding_equipment`, vinculado a un programa o área.
- Todo movimiento de stock procede de `InboundOrder` u `OutboundOrder` y queda
  trazado a un usuario; una edición directa siempre se rechaza.
- `office` sólo admite `valencia` o `miami`; la moneda correspondiente es EUR o
  USD. Telemetría registra la moneda original y no hace conversión.
- `programme_id` y `office` son dimensiones obligatorias de los cinco eventos
  base para alimentar el dashboard de Elena y el informe semanal de Laura.
- No se capturan nombres, emails, teléfonos ni identificadores de candidatos,
  clientes, consultores o destinatarios de kits.

## 2. Event Envelope

Todos los productores envían exactamente este envelope; los campos son
obligatorios aunque `sessionId` o `userId` sean `null` en un proceso autónomo:

| Campo | Tipo | Regla |
| --- | --- | --- |
| `eventId` | string UUID | Se genera una vez en origen; clave de deduplicación. |
| `timestamp` | string ISO 8601 UTC | Momento de ocurrencia, no de ingestión. |
| `sessionId` | string o null | ID opaco y rotatorio; nunca cookie/token. Null en jobs. |
| `userId` | string o null | ID interno opaco. Null sólo si no existe actor humano. |
| `event_type` | string | Taxonomía `entity_action`, minúscula y snake_case. |
| `schemaVersion` | string semver | Empieza en `1.0.0`; cambios incompatibles suben major. |
| `requestId` | string | Correlación frontend → API → logs; jobs crean uno propio. |
| `properties` | object | Sólo las claves permitidas para ese `event_type`. |

`event-schemas.json` es la especificación ejecutable draft-07. Cada variante
usa `additionalProperties: false`: un productor que añade una clave no
permitida falla antes de enviar el evento. El collector rechaza versiones major
desconocidas, registra el contador técnico sin el payload y responde sin
reintento para evitar una tormenta.

## 3. Flujo de inventario e instrumentación

1. El usuario se autentica: `login_succeeded` o `login_failed`.
2. Abre inventario: `section_viewed`; las consultas relevantes pueden emitir
   `stock_level_viewed` con muestreo.
3. Crea una entrada o salida. Antes de persistir, un error genera
   `order_validation_failed`.
4. Tras la transacción confirmada se emite `inbound_order_created` u
   `outbound_order_created`; nunca antes del commit.
5. El nuevo saldo se compara con el umbral y puede emitir
   `stock_threshold_triggered`.
6. En una entrada, el coste se compara con el histórico del mismo
   material/proveedor; una desviación superior al umbral emite
   `kit_cost_variance_detected`.
7. Si alguien intenta evitar la orden y alterar stock, la API rechaza primero y
   emite `direct_stock_edit_rejected` en la misma frontera autorizadora.
8. Latencia y fallos se correlacionan con el mismo `requestId` mediante
   `api_latency_recorded` o `backend_error_captured`.

Esto proporciona más de los cinco puntos mínimos y mantiene el principio
transaccional: la telemetría describe lo que ocurrió, nunca provoca el
movimiento de inventario.

## 4. Catálogo: negocio e inventario

La columna “Por qué → decisión” completa la regla de oro para cada evento.
“Allowlist” enumera todas las propiedades admitidas; ninguna otra se envía.

| Evento | Clase | Cuándo | Por qué → decisión | Allowlist de `properties` | Entrega |
| --- | --- | --- | --- | --- | --- |
| `inbound_order_created` | Obligatorio | Commit de una entrada | Capturamos el lote porque necesitamos saber cuánto material se compra, para qué programa y a qué coste → Elena ajusta producción según demanda. | `office`, `product_id`, `product_category`, `programme_id`, `quantity`, `currency`, `order_id`, `supplier_id`, `unit_cost` | Batch horario; la planificación tolera demora y se agrega por programa/sede. |
| `outbound_order_created` | Obligatorio | Commit de una salida | Capturamos la entrega porque necesitamos saber qué programas consumen material y a qué ritmo → Elena anticipa reposición antes de matrículas. | `office`, `product_id`, `product_category`, `programme_id`, `quantity`, `currency`, `order_id`, `recipient_type` | Stream para recalcular disponibilidad y luego compactación batch. |
| `stock_threshold_triggered` | Obligatorio | Saldo ≤ mínimo tras una salida | Capturamos el umbral porque necesitamos saber cuándo un programa corre riesgo de quedarse sin kits → Operaciones repone o ajusta el mínimo. | `office`, `product_id`, `product_category`, `programme_id`, `quantity`, `currency`, `threshold`, `available_quantity` | Stream; una alerta tardía puede bloquear una entrega. |
| `direct_stock_edit_rejected` | Obligatorio | La API bloquea edición directa | Capturamos el rechazo porque necesitamos saber dónde se intenta saltar la trazabilidad → Patricia cambia permisos o capacitación. | `office`, `product_id`, `product_category`, `programme_id`, `quantity`, `currency`, `attempted_operation`, `actor_role`, `reason_code` | Stream; repetición puede ser abuso o formación urgente. |
| `kit_cost_variance_detected` | Obligatorio | Coste unitario varía por encima del umbral | Capturamos la variación porque necesitamos detectar subidas anómalas del proveedor → Elena/Laura renegocian o cambian proveedor. | `office`, `product_id`, `product_category`, `programme_id`, `quantity`, `currency`, `supplier_id`, `previous_unit_cost`, `current_unit_cost`, `variance_percent`, `threshold_percent` | Stream; la orden debe revisarse antes de nuevas compras. |
| `order_validation_failed` | Oportunidad | Entrada/salida rechazada por dominio | Capturamos el fallo porque necesitamos saber qué reglas bloquean más al equipo → Producto mejora el formulario o la capacitación. | `office`, `order_type`, `product_id`, `programme_id`, `error_code`, `field_name`, `actor_role` | Batch cada hora; no exige intervención individual inmediata. |
| `stock_level_viewed` | Oportunidad | Operador consulta detalle de stock | Capturamos la consulta porque necesitamos saber qué materiales generan más incertidumbre → Elena prioriza vistas y alertas útiles. | `office`, `product_id`, `product_category`, `programme_id`, `view_source`, `below_threshold` | Batch diario, muestreado; no es señal urgente. |
| `inventory_export_requested` | Oportunidad | Usuario solicita CSV/PDF | Capturamos exportaciones porque necesitamos saber qué equipos siguen dependiendo de trabajo fuera del sistema → Tecnología prioriza reportes nativos. | `office`, `export_format`, `filters_count`, `row_count_bucket`, `actor_role` | Batch diario; se analiza como tendencia. |

`recipient_type` sólo admite categorías (`client`, `candidate`, `consultant`,
`support_agent`); no identifica a la persona. `supplier_id`, `order_id` y
`product_id` son IDs internos opacos.

## 5. Catálogo: autenticación y autorización

| Evento | Clase | Por qué → decisión | Allowlist | Entrega |
| --- | --- | --- | --- | --- |
| `login_succeeded` | Oportunidad | Capturamos éxitos porque necesitamos comparar uso por sede/rol sin identificar personas → Operaciones ajusta soporte y capacidad. | `office`, `actor_role`, `auth_method` | Batch horario. |
| `login_failed` | Oportunidad | Capturamos fallos porque necesitamos detectar credenciales problemáticas o ataques → Seguridad bloquea patrones y mejora recuperación. | `office`, `actor_role`, `auth_method`, `reason_code`, `attempt_count_bucket` | Stream; ráfagas requieren respuesta rápida. |
| `session_expired` | Oportunidad | Capturamos expiraciones porque necesitamos saber si interrumpen tareas activas → Producto ajusta TTL o renovación. | `office`, `actor_role`, `section`, `session_age_bucket`, `had_unsaved_changes` | Batch horario; se alerta sólo por subida agregada. |
| `permission_denied` | Oportunidad | Capturamos denegaciones porque necesitamos distinguir permisos mal diseñados de abuso → Seguridad corrige RBAC o investiga. | `office`, `actor_role`, `resource_type`, `action`, `reason_code` | Stream para patrones repetidos; detalle se agrega en batch. |

No se envían email, contraseña, hash, JWT, cookie, IP completa ni texto libre de
credenciales. `userId` es el ID interno del envelope; los análisis generales
usan rol y sede.

## 6. Catálogo: rendimiento, errores y navegación

| Evento | Categoría · clase | Por qué → decisión | Allowlist | Entrega |
| --- | --- | --- | --- | --- |
| `api_latency_recorded` | Rendimiento · oportunidad | Capturamos latencia porque necesitamos localizar rutas que amenazan el SLA → Tecnología prioriza consultas/capacidad. | `route_template`, `method`, `status_class`, `duration_ms`, `office`, `sample_rate` | Stream agregado en ventanas de 1 min; muestras crudas batch. |
| `page_load_recorded` | Rendimiento · oportunidad | Capturamos Web Vitals porque necesitamos saber qué sección degrada la experiencia real → Frontend prioriza LCP/CLS/INP por impacto. | `section`, `device_class`, `navigation_type`, `ttfb_ms`, `lcp_ms`, `cls`, `inp_ms`, `sample_rate` | Batch cada 15 min; no alerta por una sesión aislada. |
| `frontend_error_captured` | Errores · oportunidad | Capturamos errores no controlados porque necesitamos saber qué vistas quedan inutilizables → Ingeniería corrige por frecuencia e impacto. | `section`, `error_fingerprint`, `release`, `handled`, `office` | Stream para regresión tras release; sin stack ni mensaje. |
| `backend_error_captured` | Errores · oportunidad | Capturamos 5xx porque necesitamos correlacionar fallos con rutas y releases → On-call revierte o mitiga. | `route_template`, `method`, `error_fingerprint`, `release`, `office`, `retryable` | Stream; el impacto operativo es inmediato. |
| `section_viewed` | Navegación · oportunidad | Capturamos vistas porque necesitamos saber qué módulos usan realmente los operadores → Producto prioriza mantenimiento y formación. | `section`, `previous_section`, `office`, `actor_role` | Batch diario; debounced por sesión/sección. |
| `flow_abandoned` | Navegación · oportunidad | Capturamos abandono porque necesitamos localizar pasos que impiden completar órdenes → Producto simplifica el paso problemático. | `flow_name`, `last_step`, `elapsed_ms_bucket`, `validation_error_count`, `office`, `actor_role` | Batch horario; sólo se emite tras timeout/abandono confirmado. |

### Datos sensibles y sanitización

- `error_fingerprint` es un hash estable de tipo + ubicación normalizada. Nunca
  contiene `message`, stack, path de archivo, cuerpo HTTP o query string.
- `route_template` usa `/products/{id}`, nunca la URL concreta.
- `previous_section` y `section` proceden de un enum; no se registra el título
  escrito por usuarios.
- Duraciones de sesión y abandono se agrupan en buckets cuando identificar un
  valor exacto no cambia la decisión.
- Si la oficina no se conoce, el evento técnico admite `office: unknown`; los
  cinco eventos obligatorios de inventario no lo admiten.

### Diccionario de propiedades

En las tablas anteriores, todas las claves de cada allowlist son **obligatorias**
salvo `inp_ms`, que es opcional/null porque no toda navegación produce una
interacción. Los arrays `required` de `event-schemas.json` son la autoridad
ejecutable. Este diccionario completa tipo y significado sin repetir la misma
definición en cada evento:

| Propiedad | Tipo | Descripción |
| --- | --- | --- |
| `office` | enum | `valencia`/`miami`; `unknown` sólo en señales técnicas. |
| `product_id`, `programme_id`, `order_id`, `supplier_id` | string opaco | Identificador interno, nunca nombre o dato de contacto. |
| `product_category` | enum | `training_kit`, `certification` u `onboarding_equipment`. |
| `quantity` | integer | Unidades del movimiento/saldo; positiva salvo saldo o intento de decremento. |
| `currency` | enum | EUR para Valencia, USD para Miami; sin conversión. |
| `unit_cost`, `previous_unit_cost`, `current_unit_cost` | number ≥ 0 | Coste unitario en `currency`. |
| `threshold`, `available_quantity` | integer ≥ 0 | Mínimo configurado y saldo tras la transacción. |
| `recipient_type` | enum | Categoría del receptor; no identifica a una persona. |
| `attempted_operation` | enum | Edición directa `set`, `increment` o `decrement`. |
| `actor_role` | enum | Rol RBAC, nunca cargo en texto libre. |
| `reason_code`, `error_code` | enum | Motivo seguro y estable; no contiene mensaje/excepción. |
| `variance_percent`, `threshold_percent` | number | Variación observada y umbral que la disparó. |
| `order_type` | enum | Orden `inbound` u `outbound`. |
| `field_name` | enum | Campo de orden que no superó validación, sin su valor. |
| `view_source` | enum | Vista controlada desde la que se consultó stock. |
| `below_threshold` | boolean | Indica si el saldo consultado estaba bajo mínimo. |
| `export_format` | enum | Formato `csv` o `pdf`; no incluye el archivo. |
| `filters_count` | integer ≥ 0 | Número de filtros, no valores filtrados. |
| `row_count_bucket`, `attempt_count_bucket` | enum bucket | Volumen aproximado que reduce granularidad identificable. |
| `auth_method` | enum | Método `password`, `sso` o `magic_link`, sin credencial. |
| `section`, `previous_section` | enum | Módulo normalizado del backoffice. |
| `session_age_bucket` | enum bucket | Edad aproximada de sesión al expirar. |
| `had_unsaved_changes` | boolean | Había un formulario con cambios locales al expirar. |
| `resource_type`, `action` | enum | Recurso y operación que RBAC denegó, sin ID de registro. |
| `route_template` | string de ruta | Plantilla como `/products/{id}`, nunca URL concreta/query. |
| `method`, `status_class` | enum | Verbo HTTP y familia de estado (`2xx`…`5xx`). |
| `duration_ms`, `ttfb_ms`, `lcp_ms`, `inp_ms` | number ≥ 0 | Duraciones en milisegundos; INP admite null/ausencia. |
| `cls` | number ≥ 0 | Cumulative Layout Shift sin unidad. |
| `sample_rate` | number (0,1] | Probabilidad efectiva para corregir agregaciones. |
| `device_class`, `navigation_type` | enum | Clase de dispositivo y tipo Navigation Timing. |
| `error_fingerprint` | string opaco | Hash de error normalizado, sin stack/message. |
| `release` | string | ID/version de despliegue, sin ruta del host. |
| `handled`, `retryable` | boolean | Error capturado por boundary y posibilidad segura de retry. |
| `flow_name`, `last_step` | enum | Flujo y último paso normalizados. |
| `elapsed_ms_bucket` | enum bucket | Tiempo aproximado antes del abandono. |
| `validation_error_count` | integer ≥ 0 | Número de fallos vistos, nunca sus valores. |

## 7. Estrategia de entrega y fiabilidad

### Stream

Se envían inmediatamente alertas de stock, variaciones de coste, ediciones
directas, patrones de login/permisos y errores backend/frontend. Su decisión
caduca en minutos: reposición, bloqueo, rollback o mitigación. El producer usa
outbox transaccional para los eventos de órdenes; el collector deduplica por
`eventId`. Se reintenta con backoff y jitter sólo ante timeout/5xx; un 4xx de
schema va a dead-letter sin payload sensible.

### Batch

Planificación, navegación, validaciones, consultas, exportaciones y experiencia
agregada se procesan en ventanas de 15 minutos, horarias o diarias según la
tabla. La demora no cambia la decisión y reduce coste/ruido. Los eventos stream
también se compactan en batch para tendencias semanales.

### Throttle, debounce y muestreo

- `api_latency_recorded`: 10% de éxitos, 100% de 5xx y de solicitudes sobre el
  umbral; agregación local por ruta/minuto con p50/p95/p99 antes de exportar.
- `page_load_recorded`: máximo uno por navegación, 20% de sesiones; 100% si
  LCP > 2.5 s, CLS > 0.1 o INP > 200 ms.
- `section_viewed`: debounce 5 s y máximo una combinación sesión/sección cada
  30 min para que refrescos no parezcan uso nuevo.
- `stock_level_viewed`: máximo una consulta producto/usuario cada 15 min y 10%
  de vistas normales; 100% si está bajo umbral.
- `login_failed`, `permission_denied`, errores y eventos obligatorios nunca se
  muestrean. Las alertas se agrupan por fingerprint/rol/sede durante 5 min para
  evitar fatiga, sin descartar los contadores.
- `flow_abandoned` se cancela si el flujo termina en otra pestaña o si el usuario
  vuelve dentro de 30 min; sólo se emite una vez.

## 8. Calidad, ownership y evolución

- Backend es fuente de verdad de órdenes, umbrales, variación de coste,
  autorización y 5xx. Frontend sólo emite navegación, Web Vitals, abandono y
  errores de render.
- CI valida ejemplos contra `event-schemas.json`; producción valida el 100% de
  eventos obligatorios/seguridad y una muestra de telemetría de alta frecuencia.
- SLO de ingestión stream: 99% en <60 s. Batch horario: disponible en <90 min.
- Retención: crudos 30 días; agregados sin identificador 13 meses para
  estacionalidad. `userId` se seudonimiza al entrar al almacén analítico.
- El owner de schema es Tecnología; L&D aprueba cambios de inventario. Añadir
  propiedades opcionales incrementa minor; quitar/cambiar significado sube
  major. Productores y consumidores soportan dos majors durante migración.
- Monitores: tasa de rechazo por schema, duplicados, retraso, eventos sin
  `requestId`, cardinalidad y caída súbita por productor.

## 9. Riesgos y exclusiones

| Considerado | Decisión | Motivo |
| --- | --- | --- |
| Nombres/emails/teléfonos de destinatarios | Excluido | No son necesarios para reposición; elevarían riesgo RGPD. |
| Password, JWT, cookie o credencial | Excluido | Secreto sin valor analítico; una filtración comprometería cuentas. |
| Cuerpo HTTP, query string, stack y mensaje libre | Excluido | Pueden contener PII, tokens o rutas internas; se usa fingerprint y template. |
| IP completa y geolocalización precisa | Excluido | `office` responde la pregunta de sede con mucha menos intrusión. |
| Keystrokes, texto de notas o reproducción de sesión | Excluido | Vigilancia desproporcionada y posible captura de datos personales. |
| Evento por cada render/click/hover | Excluido | Alta cardinalidad/coste y sin decisión concreta; se conservan vistas y abandono. |
| Conversión EUR↔USD en telemetría | Excluido | Cambiaría el dato fuente; la conversión pertenece a la capa analítica con tipo de cambio versionado. |
| Alertar por cada latencia o validación | Excluido | Produce fatiga; se usan percentiles y tendencias, salvo umbral/5xx. |

Riesgos residuales: cardinalidad no controlada de IDs, pérdida entre commit y
emisión, duplicados por reintentos y sesgo de muestreo. Se mitigan con enums,
outbox, `eventId` idempotente, `sample_rate` explícito y tests de contrato. El
plan no pretende medir desempeño individual de empleados; cualquier uso de
`userId` para disciplina está fuera de propósito y requiere evaluación legal y
laboral independiente.

## 10. Checklist de instrumentación

1. Publicar `event-schemas.json` como artefacto versionado.
2. Generar SDKs tipados y validadores desde el contrato; no construir JSON ad
   hoc en componentes.
3. Implementar request ID en el edge y propagarlo a Next, FastAPI, outbox y logs.
4. Instrumentar primero los cinco eventos obligatorios y probar agregaciones
   por `office` + `programme_id`.
5. Añadir señales de seguridad/errores, después rendimiento y comportamiento.
6. Ejecutar pruebas con Valencia/EUR y Miami/USD, ediciones directas, dos
   umbrales y una variación de coste.
7. Validar que payloads rechazados no llegan al bus y que ningún fixture contiene
   PII o secretos.
8. Revisar dashboards, alertas, muestreo y coste a los 30 días; retirar eventos
   que no estén habilitando la decisión documentada.

## 11. Verificación del entregable

- `Draft7Validator.check_schema` acepta `event-schemas.json`.
- Conteo estructural: 18 eventos, 5 obligatorios, 13 oportunidades y 8
  categorías técnicas/de negocio.
- Todas las variantes tienen allowlist cerrada, entrega y política de datos
  sensibles.
- Un evento válido de entrada Valencia/EUR fue aceptado; la misma entrada con
  USD, una clave `candidate_email` o sin `requestId` fue rechazada.
