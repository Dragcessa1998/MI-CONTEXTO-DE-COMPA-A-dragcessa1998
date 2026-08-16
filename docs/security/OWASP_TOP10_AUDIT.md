# Auditoría OWASP Top 10 y hardening de Nexova

**Fecha de corte:** 17 de agosto de 2026

**Rama auditada:** `project/23-owasp-top10-audit`

**Referencia:** [OWASP Top 10:2021](https://owasp.org/Top10/2021/). Se usa la edición 2021 porque es la enumeración exacta solicitada por el proyecto del syllabus.

## 1. Resultado ejecutivo

La línea base no era apta para exponer a Internet. La API Express de talento entregaba CV, salarios y rankings sin autenticación; cualquier usuario autenticado podía operar RFP; FastAPI y Express aceptaban CORS comodín; el JWT del chat aparecía en la URL; los contenedores ejecutaban como root y backend/Qdrant se publicaban en todas las interfaces. Además, las tres UIs arrastraban 3 vulnerabilidades `high` por aplicación en Next.js 14/PostCSS/Nanoid.

Esta iteración remedia en código los hallazgos críticos:

1. API de talento cerrada con JWT HS256 validado por firma, expiración, issuer, audience y rol; sólo `manager/admin`.
2. Workflow RFP limitado a `manager/admin`; un usuario de soporte obtiene 403.
3. JWT WebSocket movido de query string a `Sec-WebSocket-Protocol` y el formato anterior se rechaza.
4. Contenedores FastAPI/UI/Talent ejecutan con usuarios no-root; backend, Talent API y Qdrant ya no publican puertos al host.
5. Baseline SSH/firewall declarativo: `PermitRootLogin no`, sólo clave para `nexova-deploy`, permisos cerrados y entrada exclusivamente por 22/443.
6. CORS por allowlist, hosts de confianza, documentación FastAPI desactivada en producción y cabeceras defensivas.
7. Next.js 14 → 16.3.1, PostCSS 8.5.26, Express 4.22.2; `npm audit` queda en cero para cuatro proyectos. Python-JOSE/ecdsa se sustituyó por PyJWT y `pip-audit` queda en cero.

No se concede sign-off del **host real** hasta ejecutar el instalador desde la consola del proveedor y adjuntar la salida de `--check`. El repositorio contiene el control aplicable y su validador; este entorno no dispone de la dirección, acceso ni clave del servidor y tampoco tiene daemon Docker/Podman.

## 2. Alcance real

Se auditó lo que existe en el monorepo, separado en tres carriles:

- **Backend:** `services/api` (FastAPI, TinyDB, PostgreSQL/Supabase, Qdrant) y `services/talent-api` (Express/TS, candidatos, scoring, ATS en memoria).
- **Frontend:** `uis/website`, `uis/backoffice`, `uis/talent-pipeline-tracker` y los HTML históricos. Los HTML raíz no forman parte del despliegue Compose endurecido.
- **Agentes:** RAG comercial, agente LangGraph de soporte y tool de incidentes, workflow RFP Partes 1–3, SSE y chat WebSocket.

El RAG completo sobre candidatos, el agente de prospección y MCP de escritura están descritos en el contexto, pero todavía no existen; se anotan como fuera de ejecución y no se les atribuyen controles ficticios.

## 3. Registro de hallazgos

| ID | Severidad inicial | Hallazgo antes | Remediación y estado | Evidencia reproducible |
| --- | --- | --- | --- | --- |
| C-01 | **Crítica** | `GET /candidates`, ranking y mutaciones de ATS eran anónimos | middleware JWT; firma/exp/iss/aud/rol; sólo manager/admin | `services/talent-api/src/security.test.ts` |
| C-02 | **Crítica** | cualquier JWT `user` podía crear/aprobar RFP | dependencia `require_roles(admin, manager)` en todo `/api/rfps` | `test_support_role_cannot_open_privileged_rfp_workflow` |
| C-03 | **Crítica** | FastAPI/UI corrían como root; backend, Talent API y Qdrant quedaban publicados | `USER nexova/node`; servicios internos sin `ports`; UI sólo loopback; nftables sólo 22/443 | `validate_hardening.py`, `test_infrastructure_hardening.py` |
| C-04 | **Crítica** | JWT de chat en `?token=...`, expuesto a logs/historial/proxies | JWT en subprotocolo WebSocket; query token rechazado 4401 | `test_websocket_rejects_legacy_query_string_token` |
| H-01 | Alta | CORS `*` en FastAPI y Talent API | allowlists explícitas; wildcard provoca fallo de configuración | `test_cors_allows_known_backoffice_and_rejects_unknown_origin` y test TS |
| H-02 | Alta | Next 14.2.35/PostCSS/Nanoid: 3 findings high por UI | Next 16.3.1 y PostCSS 8.5.26; las tres auditorías quedan a cero | `npm audit --package-lock-only` |
| H-03 | Alta | Python-JOSE instalaba `ecdsa` con vulnerabilidad sin versión corregida; Starlette vulnerable | PyJWT 2.13.0; Starlette 1.6.0; dependencias vulnerables retiradas | `pip-audit --path ...` |
| M-01 | Media | cabeceras de navegador ausentes y `X-Powered-By` de Express | CSP, nosniff, frame deny, referrer/permissions policy, HSTS en producción | tests HTTP FastAPI/Express y configs Next |
| M-02 | Media | FastAPI exponía `/docs`, `/redoc` y OpenAPI en producción | rutas de documentación anuladas con `APP_ENV=production` | `services/api/main.py` |
| M-03 | Media abierta | login/registro no tienen limitador por IP ni MFA | JWT expira en 30 min y error de login no enumera; añadir rate limit distribuido y MFA | roadmap P1 |
| M-04 | Media abierta | tokens del backoffice viven en `localStorage` | CSP y no uso de HTML peligroso reducen XSS; migrar a cookie HttpOnly same-site exige rediseñar SSE/WS | roadmap P1 |
| M-05 | Media abierta | no hay SIEM/alertas durables ni auditoría de todas las mutaciones ATS | trazas/guardrails existen para agentes; exportar auth/ATS a SIEM | roadmap P1 |
| M-06 | Media abierta | imágenes se fijan por versión, no por digest; sin SBOM/firma | lockfiles y auditorías limpias; añadir digest, SBOM y firma en CI | roadmap P1 |

Para reproducir el “antes” sin alterar la rama:

```bash
git show c2d48f5:services/talent-api/src/index.ts | grep 'Access-Control-Allow-Origin.*,\|app.get("/candidates"'
git show c2d48f5:services/api/main.py | grep 'allow_origins=\["\*"\]'
git show c2d48f5:services/Dockerfile | grep -q '^USER ' || echo 'ANTES: sin USER'
git show c2d48f5:docker-compose.yml | grep -E 'BACKEND_PORT|QDRANT_PORT'
git show c2d48f5:uis/backoffice/src/lib/support-chat.ts | grep 'token: options.token'
```

## 4. Matriz OWASP: 10 categorías × 3 carriles

Cada celda declara si la categoría aplica, el resultado y una evidencia concreta.

### A01:2021 — Broken Access Control

| Carril | Evaluación |
| --- | --- |
| Backend | **Aplica · crítica corregida.** Talent API exige JWT manager/admin; FastAPI mantiene owner/admin para usuarios y RFP exige manager/admin. `services/talent-api/src/security.ts`, `services/api/security.py`, `routes/rfps.py`. Queda P1: aislamiento por tenant/cliente. |
| Frontend | **Aplica · control servidor.** El backoffice adjunta el mismo JWT a `/talent-api`; ocultar botones no se usa como autorización. `uis/backoffice/src/lib/api.ts`. |
| Agentes | **Aplica · pasa.** Chat liga `session_id` a `user_id/client_id`; la tool de incidentes es sólo lectura; soporte no puede invocar RFP/ATS. `routes/chat.py`, `agent/tools.py`, pruebas C-01/C-02. |

### A02:2021 — Cryptographic Failures

| Carril | Evaluación |
| --- | --- |
| Backend | **Aplica · parcial.** bcrypt, secreto mínimo de 32 caracteres y JWT con algoritmo fijo, `iss`, `aud`, `jti`, expiración y rol. Secrets sólo por env; HTTPS termina en reverse proxy. Abierta: cifrado/rotación/vault y garantías at-rest del proveedor. |
| Frontend | **Aplica · parcial.** producción usa proxy same-origin/HTTPS y HSTS del borde; no hay secretos de servidor compilados. Token en `localStorage` es M-04. |
| Agentes | **Aplica · corregida.** clave OpenAI sólo por entorno; token WebSocket ya no está en URL; Qdrant/model APIs no se exponen al host. `check_tracked_secrets.py` y C-04. |

### A03:2021 — Injection

| Carril | Evaluación |
| --- | --- |
| Backend | **Aplica · pasa.** Pydantic `extra=forbid`, cuerpo Express 100 KB, SQL parametrizado, filtros allowlist, PDF con tamaño/magic y nombres UUID. No hay `shell=True`, `eval` ni SQL con entrada libre. |
| Frontend | **Aplica · pasa.** React escapa texto; búsqueda no encuentra `dangerouslySetInnerHTML`, `innerHTML` ni `eval`; CSP limita script/object/frame. |
| Agentes | **Aplica · pasa.** guardrails directos e indirectos, separación `instructions/input`, documentos delimitados y tool tipada/read-only. `test_ai_security.py`. |

### A04:2021 — Insecure Design

| Carril | Evaluación |
| --- | --- |
| Backend | **Aplica · mejora.** fail-closed en auth/config, tamaño de body/PDF, rate limit de modelo, estados válidos y respuestas genéricas. Falta threat model periódico y aislamiento multi-tenant. |
| Frontend | **Aplica · mejora.** proxies same-origin, errores no técnicos, confirmación en borrados y CSP. Queda migrar sesión a cookie HttpOnly. |
| Agentes | **Aplica · pasa para el alcance.** acciones de escritura ausentes o HITL; RFP final requiere todas las aprobaciones; loops limitados a tres y modelo no crea SQL/código. |

### A05:2021 — Security Misconfiguration

| Carril | Evaluación |
| --- | --- |
| Backend | **Aplica · críticas corregidas.** non-root, no reload, docs off en producción, TrustedHost, CORS cerrado, errores genéricos, servicios internos sin puertos. `Dockerfile`, Compose, `app_security.py`. |
| Frontend | **Aplica · corregida.** `poweredByHeader=false`, cabeceras en todas las rutas y builds de producción. CSP conserva `'unsafe-inline'` por hidratación Next: endurecer con nonces en P1. |
| Agentes | **Aplica · pasa.** tool de soporte con esquema/timeout/sólo lectura, sin MCP de escritura y scopes de RFP por rol. |

### A06:2021 — Vulnerable and Outdated Components

| Carril | Evaluación |
| --- | --- |
| Backend | **Aplica · corregida.** Express/tsx y lock actualizados; Python-JOSE/ecdsa retirados, PyJWT/Starlette/pytest actualizados. `npm audit` y `pip-audit`: cero. |
| Frontend | **Aplica · corregida.** tres aplicaciones en Next 16.3.1/PostCSS 8.5.26; tres builds y auditorías a cero. |
| Agentes | **Aplica · corregida.** mismo entorno Python auditado; base image/model/provider requieren vigilancia continua y digest/SBOM P1. |

### A07:2021 — Identification and Authentication Failures

| Carril | Evaluación |
| --- | --- |
| Backend | **Aplica · parcial.** contraseña bcrypt, error uniforme, token corto, usuario activo y 401/403 correctos. M-03: falta rate limit distribuido de login, MFA y revocación inmediata entre servicios. |
| Frontend | **Aplica · parcial.** formularios usan password input y no muestran tokens; sesión compartida. M-04: `localStorage` no es HttpOnly. |
| Agentes | **Aplica · corregida.** HTTP/SSE exigen Bearer; WS valida JWT antes de aceptar y selecciona el subprotocolo firmado. |

### A08:2021 — Software and Data Integrity Failures

| Carril | Evaluación |
| --- | --- |
| Backend | **Aplica · parcial.** lockfiles, versiones exactas en componentes expuestos y dependencia compartida local explícita. Falta SBOM, firma de imagen y digest de base (M-06). |
| Frontend | **Aplica · parcial.** lockfiles versionados, sin scripts CDN en apps Next; auditorías limpias. CI aún debe verificar provenance/build. |
| Agentes | **Aplica · pasa.** output externo se trata como no confiable, las aprobaciones RFP se checkpointan y los documentos finales sólo derivan de ramas aprobadas. |

### A09:2021 — Security Logging and Monitoring Failures

| Carril | Evaluación |
| --- | --- |
| Backend | **Aplica · parcial.** errores de servidor se registran sin serializarlos al cliente; eventos de guardrail agregables sin PII. Falta SIEM y auditoría durable de mutaciones (M-05). |
| Frontend | **Aplica · pendiente media.** estados de error son visibles al usuario, pero no existe reporte CSP ni telemetría central de fallos de sesión. |
| Agentes | **Aplica · parcial.** `run_id`, nodos, routing y outputs estructurados en trace store; resumen blocked/neutralized. Persistencia/alertas quedan P1. |

### A10:2021 — Server-Side Request Forgery (SSRF)

| Carril | Evaluación |
| --- | --- |
| Backend | **Aplica de forma limitada · pasa.** no acepta URLs de usuario. Qdrant/OpenAI/PostgreSQL y rewrites proceden exclusivamente de configuración del despliegue; no hay proxy de destino dinámico. |
| Frontend | **No aplica directamente.** los destinos Next son constantes de entorno compiladas; ninguna Server Action recibe una URL para hacer fetch. Mantener allowlist al añadir importadores. |
| Agentes | **No aplica al alcance activo.** la tool sólo llama una función interna por `ticket_id`; no navega URLs ni ejecuta MCP remoto configurable por prompt. |

## 5. Hardening del servidor

### Estado deseado versionado

- `infra/security/sshd_config.d/99-nexova-hardening.conf`: root y password deshabilitados, sólo clave, usuario `nexova-deploy`, 3 intentos.
- `infra/security/nftables.conf`: política deny por defecto; sólo `22/tcp` y `443/tcp` de entrada, además de loopback/conexiones establecidas e ICMP operativo.
- `scripts/security/apply_server_hardening.sh`: por defecto no muta; `--apply` exige root, una clave pública Ed25519/ECDSA válida y la confirmación literal `I_UNDERSTAND`. Guarda backups, valida antes de recargar y comprueba el estado posterior.
- Código `/opt/nexova/app` `root:nexova-deploy 0750`; logs `nexova-deploy:nexova-deploy 0750`; configuración `root:nexova-deploy 0750`; `runtime.env` `0640`.
- Compose publica únicamente los dos puertos UI en `127.0.0.1`; backend, Talent API y Qdrant sólo están en `nexova-dev`. El reverse proxy del host sirve HTTPS 443.
- Imágenes: FastAPI `USER nexova` UID 10001; UI y Talent API `USER node`; no `--reload`.

### Validación segura en repositorio

```bash
uv run python scripts/security/validate_hardening.py
# OK: root SSH deshabilitado, sólo 22/443 y contenedores non-root

uv run --project services/api --group dev pytest -q \
  services/api/tests/test_infrastructure_hardening.py
```

### Aplicación en el servidor autorizado

```bash
sudo scripts/security/apply_server_hardening.sh --check
sudo scripts/security/apply_server_hardening.sh \
  --apply /ruta/absoluta/id_ed25519.pub I_UNDERSTAND
sudo scripts/security/apply_server_hardening.sh --check
```

Debe ejecutarse desde consola del proveedor o con una segunda sesión abierta. La salida post-aplicación es la evidencia que falta para el sign-off del host.

## 6. Evidencia de pruebas y scans

```bash
# Backend, agentes e infraestructura
uv run --project services/api --group dev pytest -q
# 111 passed, 2 skipped (PostgreSQL remoto no configurado)

# API de talento
cd services/talent-api
npm run typecheck && npm test && npm audit
# 6 passed; 0 vulnerabilities

# UIs
for app in uis/backoffice uis/website uis/talent-pipeline-tracker; do
  (cd "$app" && npm run build && npm audit --package-lock-only)
done
# 3 builds correctos; 0 vulnerabilities en cada uno

# Python ya sincronizado
uvx pip-audit --path services/api/.venv/lib/python3.13/site-packages
# No known vulnerabilities found

uv run python scripts/security/check_tracked_secrets.py
uv run python scripts/security/validate_hardening.py
```

Los dos tests PostgreSQL se omiten deliberadamente sin `TEST_POSTGRES_DATABASE_URL`; no ocultan un fallo local. Docker Compose no se levantó porque este host no tiene Docker/Podman, por lo que el build de imágenes debe ejecutarse en CI o servidor.

## 7. Roadmap y criterio de sign-off

### P0 para sign-off del host

1. Aplicar hardening con clave autorizada y adjuntar salida de `--check`.
2. Construir imágenes y ejecutar smoke test tras reverse proxy TLS.
3. Confirmar que un escaneo externo ve sólo 22/443 y que `/docs`, 4000, 6333 y 8000 no responden públicamente.

### P1 siguiente ciclo

1. Rate limit distribuido y MFA para autenticación; revocación/introspección entre FastAPI y Talent API.
2. Cookie HttpOnly/Secure/SameSite y ticket WebSocket efímero para sustituir `localStorage`.
3. Tenant/cliente en el modelo de autorización de candidatos, incidentes y RFP.
4. SIEM con eventos de login, mutaciones ATS/RFP, alertas de guardrails y `request_id`.
5. Imágenes por digest, SBOM CycloneDX/SPDX, firma y verificación en CI.
6. CSP con nonce/hash sin `'unsafe-inline'` y endpoint de reportes CSP.

El código queda listo para revisión, pero la aceptación operativa del servidor requiere la evidencia P0 externa indicada.
