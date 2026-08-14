# Auditoría de serialización del backend — Nexova

Fecha de cierre: 14/08/2026  
Aplicación auditada: `services/api` (FastAPI 3.0.0)

## Alcance y método

Se inventarió la superficie HTTP directamente desde los decoradores de FastAPI
y se contrastó con `app.routes` mediante una prueba de contrato. El inventario
contiene **22 endpoints de aplicación**; no incluye `/docs`, `/redoc` ni
`/openapi.json`, que son rutas de infraestructura generadas por FastAPI.

Clasificación original:

- ✅ **Serializado**: `response_model` explícito y contrato apropiado.
- ⚠️ **Parcial**: había esquema, pero exponía un campo no necesario.
- ❌ **No serializado**: no existía `response_model` explícito.

## Inventario y resultado

| Método | Ruta | Propósito | Estado original | Respuesta original | Contrato final / cambio |
| --- | --- | --- | --- | --- | --- |
| GET | `/health` | Salud y número de proveedores | ❌ | `dict` sin esquema | ✅ `HealthResponse` |
| POST | `/auth/login` | Login JSON | ✅ | `TokenResponse` | ✅ sin cambios; no devuelve email ni contraseña |
| POST | `/auth/token` | Login OAuth2 para Swagger | ✅ | `TokenResponse` | ✅ sin cambios; no devuelve email ni contraseña |
| GET | `/auth/me` | Usuario autenticado y perfil | ✅ | `UserWithProfile` | ✅ se conserva el email propio; el perfil ya no expone `user_id` redundante |
| POST | `/users` | Registro público | ⚠️ | `UserWithProfile`, incluida la dirección de login | ✅ `RegistrationResponse`, sin email, contraseña ni hash |
| GET | `/users` | Lista administrativa | ✅ | `list[UserOut]` | ✅ proyección plana necesaria para administrar cuentas |
| GET | `/users/{user_id}` | Detalle propio o administrativo | ✅ | `UserWithProfile` | ✅ perfil anidado sin clave foránea redundante |
| PUT | `/users/{user_id}` | Sustituir credenciales/estado autorizados | ✅ | `UserOut`; entrada `UserUpdate` | ✅ entrada y salida separadas |
| DELETE | `/users/{user_id}` | Eliminar usuario y perfil | ❌ | 204 sin declaración explícita | ✅ `response_model=None` explícito, cuerpo vacío por contrato HTTP |
| GET | `/profiles/me` | Leer perfil propio | ✅ | `ProfileOut` | ✅ `ProfileOut` ya no contiene `user_id`; la identidad está en el token |
| PUT | `/profiles/me` | Sustituir perfil propio | ✅ | `ProfileOut`; entrada `ProfileUpdate` | ✅ entrada y salida separadas |
| POST | `/suppliers` | Crear proveedor | ✅ | `SupplierOut`; entrada `SupplierIn` | ✅ campos del sistema sólo en salida |
| GET | `/suppliers` | Listar/filtrar proveedores | ✅ | `list[SupplierOut]` | ✅ coincide con el modelo consumido por la tabla editable del backoffice |
| GET | `/suppliers/{supplier_id}` | Detalle de proveedor | ✅ | `SupplierOut` | ✅ sin cambios |
| PATCH | `/suppliers/{supplier_id}/rate` | Cambiar tarifa | ✅ | `SupplierOut`; entrada `RateUpdate` | ✅ sólo acepta la tarifa writable |
| PATCH | `/suppliers/{supplier_id}/status` | Cambiar estado | ✅ | `SupplierOut`; entrada `StatusUpdate` | ✅ sólo acepta el estado writable |
| DELETE | `/suppliers/{supplier_id}` | Eliminar proveedor | ❌ | `dict` sin esquema | ✅ `DeleteResponse` |
| POST | `/api/incidents` | Crear incidente | ✅ | `IncidentOut`; entrada `IncidentCreate` | ✅ entrada sin ID ni timestamps del sistema |
| GET | `/api/incidents` | Lista filtrable para el gestor | ✅ | `list[IncidentOut]` | ✅ proyección usada por tabla, ciclo de estado y control de frescura |
| GET | `/api/incidents/summary` | Agregados para dashboard | ✅ | `IncidentSummary` | ✅ respuesta agregada, sin objetos anidados |
| GET | `/api/incidents/{incident_id}` | Detalle de incidente | ✅ | `IncidentOut` | ✅ sin cambios |
| PATCH | `/api/incidents/{incident_id}/status` | Avanzar ciclo de estado | ✅ | `IncidentOut`; entrada `IncidentStatusUpdate` | ✅ sólo acepta el campo writable |

Tras los cambios, los 22 endpoints quedan en estado ✅.

## Decisiones de forma y relaciones

- La representación persistida `ProfileRecord` conserva `user_id` para la
  relación TinyDB, pero el contrato HTTP `ProfileOut` lo elimina. En
  `/auth/me` y `/users/{id}` el perfil se anida bajo el usuario; en
  `/profiles/me` el propietario ya queda determinado por el JWT. Exponer la
  clave foránea en cualquiera de esos casos era redundante.
- `GET /users` es una proyección plana y no incluye el perfil: la vista
  administrativa sólo necesita identidad, email, rol, estado y fecha.
- Los proveedores se devuelven planos porque el backoffice consume sus campos
  editables directamente; no existe una relación anidada que justifique más
  objetos.
- `IncidentSummary` devuelve contadores ya agregados. La lista de incidentes
  conserva `updated_at` porque el cliente reemplaza registros tras cambios de
  estado y necesita un contrato compatible con respuestas de escritura.

## Separación de entrada y salida

Los endpoints de escritura no reutilizan el contrato de respuesta como cuerpo:

| Dominio | Entrada | Salida |
| --- | --- | --- |
| Registro | `UserCreate` | `RegistrationResponse` |
| Usuario | `UserUpdate` | `UserOut` |
| Perfil | `ProfileUpdate` | `ProfileOut` |
| Proveedor | `SupplierIn`, `RateUpdate`, `StatusUpdate` | `SupplierOut` |
| Incidente | `IncidentCreate`, `IncidentStatusUpdate` | `IncidentOut` |
| Login JSON | `LoginRequest` | `TokenResponse` |
| Login OAuth2 | `OAuth2PasswordRequestForm` | `TokenResponse` |

Todos los modelos de entrada propios usan `extra="forbid"`; IDs, roles por
defecto, timestamps, hashes y otras propiedades del sistema no son escribibles
por accidente.

## Datos sensibles

- `UserRecord.hashed_password` es exclusivamente interno y nunca se usa como
  `response_model`.
- Registro y login no devuelven email, contraseña ni hash. El registro confirma
  ID, rol, estado, fecha y perfil no sensible.
- `GET /auth/me` sí devuelve el email del propio usuario autenticado, excepción
  necesaria y permitida para la vista de perfil.
- No hay tokens internos en ningún esquema. El `access_token` sólo aparece en
  `TokenResponse`, que es precisamente el resultado esperado del login.

## Verificación

La suite añade `tests/test_serialization.py`, que:

1. compara las 22 parejas método/ruta con el inventario de este documento;
2. falla si una respuesta no vacía carece de esquema explícito;
3. comprueba las formas reales de registro, login y health;
4. verifica que registro y login no eco-serialicen el email o la contraseña.

Además, se volvieron a ejecutar las pruebas existentes de autenticación,
proveedores e incidentes para descartar regresiones. Las comprobaciones
interactivas de Swagger se hicieron sobre `POST /users`, `POST /auth/login` y
`GET /health`; las respuestas visibles coincidieron con los esquemas anteriores.
