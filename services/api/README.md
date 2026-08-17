# Nexova — Authenticated Supplier Directory API

Registro oficial y único de los **proveedores externos** de Nexova (job boards, ATS,
formación, nóminas, oficinas…), en sustitución de la hoja de cálculo que Patricia Solís
(HR Manager) compartía por email. Proyecto del syllabus **"Supplier Directory — Lightweight
Storage API"**, solicitado por el CTO Sergio Molina.

**Stack:** FastAPI + TinyDB + Pydantic + JWT, gestionado con [`uv`](https://docs.astral.sh/uv/).
El modelo, las categorías, los estados y los datos del seeder replican **exactamente**
[CONTEXT.md](CONTEXT.md) (CONTEXT-nexova · supplier-directory).

## Ejecutar

```bash
cd services/api
cp .env.example .env                 # sustituye JWT_SECRET por un secreto aleatorio
uv run seed                          # carga inicial (idempotente, confirma el conteo)
uv run uvicorn main:app --port 8000  # API + Swagger UI en http://localhost:8000/docs
uv run --group dev pytest -q         # pruebas de aceptación en TinyDB aislada
```

> `uv` instala Python y las dependencias automáticamente la primera vez.

Genera un secreto local seguro, por ejemplo con `openssl rand -hex 32`, y no lo
subas al repositorio. `ACCESS_TOKEN_EXPIRE_MINUTES` controla la vida del token.

Para recuperación de contraseña, configura `RESEND_API_KEY`,
`PASSWORD_RESET_FROM_EMAIL` y `PASSWORD_RESET_FRONTEND_URL`. El token dura 30
minutos por defecto (`PASSWORD_RESET_EXPIRE_MINUTES`, permitido: 15–60), sólo se
guarda hasheado en TinyDB y se invalida después del primer uso. En desarrollo,
el remitente de onboarding de Resend permite probar sin dominio propio dentro
de las restricciones de la cuenta.

## Autenticación

1. Registra una cuenta con `POST /users`; siempre nace con rol `user` y su perfil
   uno-a-uno se crea en la misma operación.
2. Inicia sesión con `POST /auth/login` y copia `access_token`.
3. En Swagger, pulsa **Authorize** y pega el token. Las seis operaciones del
   directorio `/suppliers` requieren `Authorization: Bearer <token>`.

Rutas principales:

- `POST /users` público; listado y CRUD de credenciales protegidos. Un usuario
  solo accede a su cuenta, salvo administradores.
- `POST /auth/login` (JSON), `POST /auth/token` (formulario OAuth2 de Swagger) y
  `GET /auth/me`.
- `POST /auth/forgot-password`, `POST /auth/reset-password` y el endpoint
  autenticado `POST /auth/change-password`.
- `GET /profiles/me` y `PUT /profiles/me`; nombre, teléfono y dirección nunca
  viven en la tabla de credenciales.
- `/suppliers`: alta, listado, detalle, cambios de tarifa/estado y borrado,
  todos protegidos por la dependencia compartida `get_current_user`.

Las respuestas nunca incluyen la contraseña ni su hash. Token ausente,
malformado, expirado o perteneciente a un usuario inactivo devuelve `401`; un
intento de acceder a credenciales ajenas devuelve `403`.

### Solución de problemas (macOS)

Si `uv run seed` falla con `ModuleNotFoundError: No module named 'seed'`: en carpetas
sincronizadas (iCloud/Desktop), macOS puede marcar los archivos del venv con el flag
`hidden` y Python ignora los `.pth` ocultos. Arréglalo con:

```bash
chflags -R nohidden .venv && uv run seed
# alternativa que no depende del venv editable:
uv run python seed.py
```

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | `/users` | Registro público; crea credenciales y perfil enlazado |
| GET/PUT/DELETE | `/users`, `/users/{id}` | CRUD protegido con control de propiedad/admin |
| POST | `/auth/login` | Valida credenciales y entrega un JWT firmado |
| POST | `/auth/token` | Adaptador OAuth2 para **Authorize** en Swagger |
| GET | `/auth/me` | Usuario y perfil autenticados |
| POST | `/auth/forgot-password` | Respuesta neutra y envío del enlace con Resend |
| POST | `/auth/reset-password` | Consume un token corto y de un solo uso |
| POST | `/auth/change-password` | Cambio autenticado tras verificar la contraseña actual |
| GET/PUT | `/profiles/me` | Consulta y actualización del perfil propio |
| POST | `/suppliers` | Alta protegida (422 si la entrada es inválida) |
| GET | `/suppliers?country=&category=` | Lista protegida; filtra por país y/o categoría |
| GET | `/suppliers/{id}` | Detalle protegido por ID (404 si no existe) |
| PATCH | `/suppliers/{id}/rate` | Actualiza tarifa; protegida |
| PATCH | `/suppliers/{id}/status` | Activa/suspende; protegida |
| DELETE | `/suppliers/{id}` | Elimina; protegida |
| GET | `/health` | Estado del servicio |

### Validaciones (Pydantic → 422 antes de tocar TinyDB)

- `status` solo `active` / `suspended` · `monthly_rate` > 0 · `categories` ⊆ lista válida (mín. 1).
- **Moneda por país** (restricción del CONTEXT): `Spain → EUR`, `USA → USD`; combinaciones inconsistentes se rechazan.
- `rate_updated_at` lo **genera el sistema** (no se acepta del cliente): modelos de entrada (`SupplierIn`) y respuesta (`SupplierOut`) separados; los campos desconocidos también producen `422`.

### Ejemplos

```bash
TOKEN="pega-aqui-el-access-token"
curl -H "Authorization: Bearer $TOKEN" "localhost:8000/suppliers?country=Spain"
curl -H "Authorization: Bearer $TOKEN" "localhost:8000/suppliers?category=ats_software"
curl -X PATCH localhost:8000/suppliers/4/rate -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"monthly_rate": 325.0}'
curl -X PATCH localhost:8000/suppliers/5/status -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"status": "active"}'
```

## Estructura (la que pide la rúbrica)

```text
services/api/
  main.py           ← aplicación FastAPI (+ CORS para uis/backoffice)
  models.py         ← contratos Pydantic del directorio
  auth_models.py    ← contratos separados de credenciales y perfil
  auth_service.py   ← CRUD TinyDB sin acoplarlo a HTTP
  security.py       ← bcrypt, JWT y get_current_user
  database.py       ← tablas suppliers/users/profiles en TinyDB
  routes/
    auth.py         ← login y usuario autenticado
    users.py        ← registro y CRUD protegido
    profiles.py     ← perfil propio protegido
    suppliers.py    ← seis operaciones protegidas del directorio
  seed.py           ← carga inicial (uv run seed)
```

El frontend está en `uis/backoffice` → página **/suppliers** (tabla, filtros por país y
categoría sin recargar, alta con errores 422 inline, edición de tarifa, activar/suspender
con badge de color y aviso de renovaciones en <60 días).
