# Entorno de desarrollo con Docker Compose

La plataforma de Nexova se ejecuta en dos contenedores sobre la red explícita
`nexova-dev`:

- `ui`: una imagen Node Alpine que arranca website en `3000` y backoffice en
  `3001` desde `uis/start.sh`.
- `backend`: una imagen Python que instala las dependencias con `uv pip install
  -r requirements.txt` y arranca FastAPI en `8000` con `--reload`.

Los contextos de build parten de la raíz porque ambas imágenes reutilizan
código compartido fuera de su carpeta (`/src` para Next y `/packages/shared`
para FastAPI). Los Dockerfiles siguen viviendo en `/uis` y `/services`, y no se
duplica esa lógica.

## Arranque

```bash
cp .env.example .env
# Sustituir JWT_SECRET por: openssl rand -hex 32
docker compose up --build
```

Una vez saludables:

| Componente | URL en el host |
| --- | --- |
| Website | `http://localhost:3000` |
| Backoffice | `http://localhost:3001` |
| FastAPI / Swagger | `http://localhost:8000/docs` |

`.env` está ignorado por Git y nunca se copia a las imágenes. El Compose sólo
inyecta el secreto JWT en `backend`; el proceso UI no lo recibe.

## Comunicación y hot reload

El navegador solicita `/platform-api/*` al backoffice. El rewrite de Next,
dentro del contenedor `ui`, reenvía esas peticiones a
`http://backend:8000/*`. Así, la comunicación entre servicios usa el nombre
DNS de Compose y no expone un hostname Docker imposible de resolver desde el
navegador.

Los bind mounts de `/uis`, `/src`, `/services` y `/packages/shared` reflejan los
cambios del host. Los volúmenes separados de `node_modules` conservan las
dependencias instaladas en la imagen aunque `/uis` esté montado.

## Comprobaciones

```bash
docker compose config
docker compose up --build
docker compose ps
curl --fail http://localhost:8000/health
```

Cambiar un texto en cada aplicación y una respuesta del backend debe provocar
la recarga sin reconstruir la imagen. Antes de publicar, revisar que
`docker compose config` no contenga secretos versionados y adjuntar a la PR la
captura solicitada de `docker compose ps`.

### Validación realizada el 12/08/2026

- Docker Compose `v5.1.4`: `config --quiet` correcto con `.env.example`; expone
  exactamente `backend`, `ui` y la red `nexova-dev`.
- `services/requirements.txt` instalado desde cero en un entorno Python 3.13;
  reutiliza `packages/shared` en editable y respeta las versiones del lockfile.
- `tsc --noEmit` y build de producción correctos en website y backoffice.
- `uis/start.sh` validado con POSIX `sh`: levanta simultáneamente website en
  `3000` y backoffice en `3001`; ambas rutas `/` respondieron `200`.
- Prueba viva local: FastAPI respondió `200` en `/health` y el mismo JSON llegó
  a través de `http://127.0.0.1:3001/platform-api/health`.

El host de validación no dispone de Docker Engine, Podman ni otro daemon de
contenedores. Por tanto, el build real de imágenes, `docker compose up`, la
comprobación de bind mounts dentro de contenedores y la captura de
`docker compose ps` quedan pendientes para un equipo con Docker. No se declara
esa evidencia como completada.
