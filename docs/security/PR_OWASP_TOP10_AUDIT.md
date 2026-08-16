## Qué entrega este PR

- Auditoría completa de las 10 categorías OWASP por separado para backend, frontend y agentes (30 evaluaciones con evidencia).
- Cierre del acceso anónimo a candidatos/rankings/ATS: Talent API exige JWT `manager/admin`.
- RFP limitado a `manager/admin`; soporte recibe 403.
- JWT WebSocket fuera de la query string y validado antes del handshake.
- CORS/hosts/cabeceras/docs de producción endurecidos.
- Contenedores non-root, servicios internos sin puertos publicados, SSH sin root/password, permisos explícitos y nftables sólo 22/443.
- Migración de las tres UIs a Next.js 16.3.1 y actualización Python/Node hasta dejar `npm audit` y `pip-audit` en cero.

## Dos evidencias críticas solicitadas

1. [Autorización de Talent API y CORS](https://github.com/Dragcessa1998/MI-CONTEXTO-DE-COMPA-A-dragcessa1998/blob/project/23-owasp-top10-audit/services/talent-api/src/security.test.ts): anónimo 401, soporte 403, manager 200, origen atacante 403.
2. [Autorización RFP y configuración web](https://github.com/Dragcessa1998/MI-CONTEXTO-DE-COMPA-A-dragcessa1998/blob/project/23-owasp-top10-audit/services/api/tests/test_web_security.py): soporte no puede abrir RFP, CORS wildcard rechazado y cabeceras presentes.

Evidencia adicional: [hardening reproducible](https://github.com/Dragcessa1998/MI-CONTEXTO-DE-COMPA-A-dragcessa1998/blob/project/23-owasp-top10-audit/scripts/security/validate_hardening.py) y [token WebSocket fuera de URL](https://github.com/Dragcessa1998/MI-CONTEXTO-DE-COMPA-A-dragcessa1998/blob/project/23-owasp-top10-audit/services/api/tests/test_chat_websocket.py).

Informe: [OWASP_TOP10_AUDIT.md](https://github.com/Dragcessa1998/MI-CONTEXTO-DE-COMPA-A-dragcessa1998/blob/project/23-owasp-top10-audit/docs/security/OWASP_TOP10_AUDIT.md).

## Resultado local

- Python/FastAPI/agentes: **111 passed, 2 skipped** (PostgreSQL remoto no configurado).
- Talent API: typecheck + **6 tests**.
- Next.js: builds correctos de backoffice, website y tracker.
- Dependencias: **0 vulnerabilidades** en 4 auditorías npm y 0 conocidas en pip-audit.
- Hardening estático y secret scan: correctos.

## Límite operativo transparente

No existe acceso al servidor productivo ni Docker/Podman en este host. El repo incluye el instalador seguro, configuración, backups y comando `--check`, pero el sign-off del host requiere que el tech lead ejecute/apruebe la aplicación desde consola y adjunte la salida post-cambio. Solicito esa revisión antes del cierre operativo.
