# Despliegue endurecido con Docker Compose

La plataforma de Nexova se ejecuta en cuatro servicios sobre la red explícita
`nexova-dev`:

- `ui`: website y backoffice compilados con Next 16 y arrancados en modo
  producción como usuario `node`.
- `backend`: FastAPI sin reload y como usuario `nexova` UID 10001.
- `talent-api`: Express/TS como usuario `node`; exige JWT `manager/admin`.
- `qdrant`: almacén vectorial sólo accesible desde la red interna.

Los contextos de build parten de la raíz porque las imágenes reutilizan código
compartido (`/src` para Next/Talent API y `/packages/shared` para FastAPI). No se
duplica lógica.

## Arranque

```bash
cp .env.example .env
# Sustituir JWT_SECRET por: openssl rand -hex 32
docker compose up --build
```

Sólo las UIs tienen bind en el host y exclusivamente sobre loopback para que el
reverse proxy HTTPS las consuma:

| Componente | Acceso |
| --- | --- |
| Website | `http://127.0.0.1:3000` |
| Backoffice | `http://127.0.0.1:3001` |
| FastAPI | interno `http://backend:8000`; sin puerto público ni Swagger en producción |
| Talent API | interno `http://talent-api:4000`; sin puerto público |
| Qdrant | interno `http://qdrant:6333`; sin puerto público |

`.env` está ignorado por Git y nunca se copia a las imágenes. Compose inyecta el
mismo `JWT_SECRET` sólo en los dos backends; el proceso UI no lo recibe.

## Comunicación

El navegador solicita `/platform-api/*` y `/talent-api/*` al backoffice. Los
rewrites de Next reenvían a `http://backend:8000/*` y
`http://talent-api:4000/*`. WebSocket usa también `/platform-api` same-origin.
Así, APIs y almacenes sólo circulan dentro de la red Compose.

No hay bind mounts de código en el baseline de producción. `platform_data` y
`qdrant_data` son los únicos volúmenes persistentes.

## Comprobaciones

```bash
docker compose config
docker compose up --build
docker compose ps
curl --fail http://127.0.0.1:3001/platform-api/health
uv run python scripts/security/validate_hardening.py
```

Antes de publicar, comprobar que ningún API/Qdrant tiene `ports`, que las UIs se
enlazan a `127.0.0.1` y adjuntar `docker compose ps`.

### Validación del 17/08/2026

- Tres builds Next 16.3.1 correctos.
- 111 tests Python y 6 tests TS correctos.
- Cuatro `npm audit` y `pip-audit` sin vulnerabilidades conocidas.
- Validadores de secretos y hardening correctos.
- El host no dispone de Docker Engine/Podman. El build real de imágenes,
  `docker compose up` y `docker compose ps` quedan pendientes para CI o servidor
  y no se declaran como evidencia completada.
