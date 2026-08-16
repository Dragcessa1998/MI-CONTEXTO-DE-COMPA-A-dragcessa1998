# Capítulo 10. Pon todo en marcha: operación y resolución de problemas

Hasta aquí has recorrido pieza por pieza el monorepo de Nexova Solutions, la consultoría de recursos humanos y selección de talento con sedes en Valencia y Miami cuya CEO, Laura Mendoza, impulsó el reto estrella del proyecto: un pipeline de scoring de currículums explicable. Un *monorepo* es un único repositorio que aloja varias aplicaciones y servicios que comparten código. Ahora toca lo más satisfactorio: arrancarlo entero en tu propia máquina y verlo funcionar. Este capítulo es una guía operativa práctica y copiable. No introduce conceptos nuevos: te enseña a levantar cada servicio, a comprobar que responde y a salir del paso cuando algo se rompe, en especial los problemas típicos de macOS cuando trabajas dentro de carpetas del Escritorio o de iCloud.

En este capítulo aprenderás:

- Qué servicios componen el sistema completo, en qué puerto vive cada uno y con qué comando se arranca.
- El orden recomendado para levantarlos sin que unos dependan de otros que aún no existen.
- Cómo verificar que cada servicio está vivo (Swagger, el punto final `/health` y las páginas del backoffice).
- Cómo resolver los fallos más habituales: el flag oculto del entorno virtual de Python en macOS, la caché de npm con permisos rotos, puertos ocupados y las variables de entorno mal configuradas.

## El mapa de servicios

El sistema de Nexova lo forman cinco procesos independientes. Tres son interfaces de usuario construidas con Next.js 16 (un framework de React para construir aplicaciones web) y dos son backends, es decir, servidores que exponen una API. Una *API* (interfaz de programación de aplicaciones) es el contrato de URL que un programa ofrece para que otros le pidan datos.

| Servicio | Carpeta | Puerto | Comando de arranque |
| --- | --- | --- | --- |
| Supplier API (FastAPI) | `services/api` | `8000` | `uv run uvicorn main:app --port 8000` |
| Talent API (Express) | `services/talent-api` | `4000` | `npm run dev` |
| Backoffice (Next.js) | `uis/backoffice` | `3000` | `npm run dev` |
| Talent Pipeline Tracker | `uis/talent-pipeline-tracker` | `3000` | `npm run dev` |
| Website (Next.js) | `uis/website` | `3000` | `npm run dev` |

Fíjate en un detalle importante: el backoffice, el tracker y el website usan por defecto el puerto `3000`. No puedes arrancar dos a la vez sin reasignar puertos; lo veremos en la sección de problemas. En el flujo de desarrollo normal levantarás las dos APIs y el backoffice, que es la pieza que las consume.

::: {.callout .note}
**Nota:** las carpetas `agents/`, `data/`, `packages/`, `scripts/`, `infra/`, `internal/`, `mcps/`, `shared/`, `skills/` y `workflows/` son andamiaje intencional de la plantilla de 4Geeks: solo contienen un README de relleno. El contenido real vive en `src/`, `services/` y `uis/`.
:::

## Orden recomendado de arranque

Levanta los servicios de abajo hacia arriba: primero los backends, después las interfaces que los consultan. Así, cuando abras el navegador, las APIs ya estarán respondiendo y no verás errores de conexión.

### 1. Supplier API (FastAPI + TinyDB)

Esta es la única pieza en Python. Se gestiona con `uv`, un instalador de dependencias de Python que, además, descarga el propio Python la primera vez. *TinyDB* es una base de datos ligera que guarda los datos en un archivo JSON; aquí persiste en `services/api/suppliers.db.json`.

```bash
cd services/api
uv run seed                          # carga inicial idempotente
uv run uvicorn main:app --port 8000  # API + Swagger en /docs
```

El primer comando ejecuta `seed.py`, que inserta los 15 proveedores de ejemplo. Es *idempotente*, es decir, puedes lanzarlo varias veces sin duplicar datos: comprueba el nombre antes de insertar. Al terminar imprime un resumen que confirma el conteo:

```text
Seeder del directorio de proveedores de Nexova
  Insertados: 15
  Omitidos (ya existían): 0
  Total en la base de datos: 15
```

El segundo comando arranca *uvicorn*, el servidor que sirve la aplicación FastAPI definida en `services/api/main.py`.

### 2. Talent API (Express + TypeScript)

Es la API central del dominio de talento: candidatos, vacantes, procesos de selección y el ranking por scoring. Reutiliza la lógica de negocio de `src/` mediante el alias `@logic` (no la copia). Corre con *tsx*, una herramienta que ejecuta TypeScript directamente sin compilar en un paso aparte.

```bash
cd services/talent-api
npm install
npm run dev        # http://localhost:4000  (recarga en caliente)
```

`npm install` baja las dependencias declaradas en `package.json` (Express y los tipos). `npm run dev` lanza `tsx watch src/index.ts`, que recarga al guardar cambios. En consola verás `Nexova Talent API escuchando en http://localhost:4000`. El puerto se lee de la variable `PORT`, con `4000` por defecto (`services/talent-api/src/index.ts`).

### 3. Backoffice (Next.js)

El panel interno consume las DOS APIs por HTTP: la Talent API para candidatos y procesos, y la Supplier API para el directorio de proveedores. Solo importa los TIPOS de `@logic`, nunca la lógica de cálculo; los números los aporta el backend.

```bash
cd uis/backoffice
npm install
npm run dev        # http://localhost:3000
```

### 4. Website y Talent Pipeline Tracker

El website es la web pública corporativa, migrada del Hito 1 a componentes de React, con la ruta `/apply` para el formulario de talento. El tracker es la aplicación del Hito 3 que opera sobre la API del curso (`https://playground.4geeks.com/tracker/api/v1`). Ninguno depende de tus backends locales, así que puedes arrancarlos cuando quieras, pero recuerda que ambos quieren el puerto `3000`.

```bash
cd uis/website                  # o uis/talent-pipeline-tracker
npm install
npm run dev -- -p 3001          # reasigna el puerto si el 3000 está ocupado
```

## Cómo verificar que cada servicio responde

Arrancar no es lo mismo que funcionar. Comprueba cada pieza antes de seguir.

**Supplier API.** Abre `http://localhost:8000/docs` en el navegador. Es *Swagger UI*, una página interactiva que FastAPI genera automáticamente con todos los endpoints documentados y un botón para probarlos. También puedes consultar el punto final de salud desde la terminal:

```bash
curl localhost:8000/health
# {"status":"ok","suppliers":15}
```

El campo `suppliers` debe coincidir con lo que imprimió el seeder. Prueba además un par de filtros reales:

```bash
curl "localhost:8000/suppliers?country=Spain"
curl "localhost:8000/suppliers?category=ats_software"
```

**Talent API.** Su `/health` devuelve estado y conteos. Verifica también un ranking, que es donde se nota la lógica de scoring:

```bash
curl localhost:4000/health
curl localhost:4000/vacancies/V-2024-0892/ranking
curl localhost:4000/reports/summary
```

**Backoffice.** Abre `http://localhost:3000`. Verás el Dashboard en `/`. Navega a `/processes` (el tablero del pipeline, que envía un `PATCH /processes/:id` al avanzar etapas) y a `/suppliers` (la tabla con filtros por país y categoría, edición de tarifa y botón de activar/suspender). Si en `/suppliers` no aparece nada, casi siempre es que la Supplier API no está levantada o que la variable de entorno apunta a otro sitio.

::: {.callout .tip}
**Tip:** si el backoffice no consigue datos, el componente `uis/backoffice/src/components/ApiErrorState.tsx` muestra en pantalla los comandos exactos para arrancar la API que falta y un botón de reintentar. Léelo: te dice qué backend está caído sin tener que adivinar.
:::

## Resolución de problemas

### El flag oculto del entorno virtual en macOS

Es el fallo número uno y desconcierta a todo el mundo. Si `uv run seed` revienta con `ModuleNotFoundError: No module named 'seed'`, no es que falte código: es macOS. En carpetas sincronizadas (Escritorio, iCloud) el sistema marca los archivos del entorno virtual `.venv` con el flag `UF_HIDDEN` (oculto), y Python ignora los archivos `.pth` ocultos que enlazan el proyecto. La solución es quitar ese flag:

```bash
cd services/api
chflags -R nohidden .venv && uv run seed
```

`chflags -R nohidden` recorre recursivamente `.venv` retirando la marca de oculto. Si prefieres no tocar el entorno, ejecuta el script directamente, lo que evita el paquete editable:

```bash
uv run python seed.py
```

::: {.callout .warning}
**Aviso:** este problema reaparece si mueves o regeneras `.venv`. Si vuelve el `ModuleNotFoundError` tras un `uv sync` o tras copiar la carpeta, vuelve a aplicar `chflags -R nohidden .venv`. No es un error de tu código: es la interacción entre iCloud y los entornos virtuales.
:::

### Caché de npm con permisos rotos

Si `npm install` falla con errores de `EACCES` o de permisos sobre `~/.npm`, la caché global de npm quedó con dueños incorrectos (típico tras usar `sudo` por error). En vez de pelearte con los permisos del sistema, usa una caché temporal y desechable:

```bash
npm install --cache /tmp/npm-cache-nexova
```

Apuntar la caché a `/tmp` evita la carpeta dañada por completo y deja la instalación limpia.

### Usa `./node_modules/.bin/` en vez de `npx`

Si `npx` se queda colgado intentando descargar un paquete o usa permisos raros de la caché, llama al binario que `npm install` ya dejó dentro del proyecto. Cada dependencia ejecutable vive en `node_modules/.bin/`:

```bash
./node_modules/.bin/next dev
./node_modules/.bin/tsc --noEmit
```

Es más rápido y determinista: ejecutas exactamente la versión fijada en `package-lock.json`, sin que `npx` intente resolver nada por la red.

### Puertos ocupados

Recuerda que website, backoffice y tracker comparten el `3000`. Si Next.js avisa de que el puerto está en uso, o reasignas el nuevo proceso, o liberas el puerto. Para reasignar:

```bash
npm run dev -- -p 3001
```

El `--` separa los argumentos de npm de los que recibe `next dev`. Para averiguar qué proceso ocupa un puerto y cerrarlo:

```bash
lsof -i :3000        # muestra el PID que escucha en el 3000
kill -9 <PID>        # ciérralo (sustituye <PID> por el número real)
```

### Variables de entorno: a dónde apunta cada frontend

Los frontends de Next.js leen su URL de backend de variables que empiezan por `NEXT_PUBLIC_`. Ese prefijo es obligatorio: indica a Next.js que la variable puede llegar al navegador. Si una página muestra datos vacíos o errores de red, casi siempre es una de estas:

| Variable | App que la usa | Valor por defecto |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `uis/backoffice` (Talent API) | `http://localhost:4000` |
| `NEXT_PUBLIC_SUPPLIERS_API_URL` | `uis/backoffice` (Supplier API) | `http://localhost:8000` |
| `NEXT_PUBLIC_API_URL` | `uis/talent-pipeline-tracker` | `https://playground.4geeks.com/tracker/api/v1` |

Los valores por defecto están codificados con el operador `??` en `uis/backoffice/src/lib/api.ts`, `uis/backoffice/src/lib/suppliers.ts` y `uis/talent-pipeline-tracker/src/lib/api.ts`. Si arrancas todo con los puertos por defecto, no necesitas configurar nada. Para apuntar a otra dirección, crea un archivo `.env.local` en la carpeta de la app:

```bash
NEXT_PUBLIC_API_URL=http://localhost:4000
NEXT_PUBLIC_SUPPLIERS_API_URL=http://localhost:8000
```

::: {.callout .important}
**Importante:** Next.js lee las variables `NEXT_PUBLIC_*` en el momento de arrancar. Si cambias `.env.local` con el servidor en marcha, detén el proceso (Ctrl+C) y vuelve a lanzar `npm run dev`; en caliente no se recargan. Y como ese valor se incrusta en el código que llega al navegador, no metas ahí ningún secreto.
:::

Si la API responde por `curl` pero el navegador da error de CORS, recuerda que tanto la Supplier API (`main.py`) como la Talent API ya añaden cabeceras CORS con preflight para que las apps de `uis/` puedan llamarlas. Un fallo de CORS suele significar que la app está pidiendo a una URL distinta de la que sirve la API: revisa de nuevo la variable de entorno.

## Resumen

- El sistema completo son cinco procesos: dos backends (Supplier API en `:8000` y Talent API en `:4000`) y tres frontends de Next.js que por defecto piden el puerto `:3000`.
- Arranca de abajo hacia arriba: primero `uv run seed` y `uv run uvicorn main:app --port 8000`, luego la Talent API con `npm run dev`, y por último el backoffice, que consume ambas.
- Verifica con Swagger en `http://localhost:8000/docs`, los puntos finales `/health` y las páginas `/`, `/processes` y `/suppliers` del backoffice.
- En macOS, el fallo más frecuente es `ModuleNotFoundError` por el flag oculto del `.venv`: se arregla con `chflags -R nohidden .venv` o ejecutando `uv run python seed.py`.
- Ante problemas de npm usa `npm install --cache /tmp/...` y llama a los binarios desde `./node_modules/.bin/`; ante puertos ocupados, reasigna con `npm run dev -- -p 3001` o libera el puerto con `lsof` y `kill`.
- Si un frontend no muestra datos, revisa `NEXT_PUBLIC_API_URL` y `NEXT_PUBLIC_SUPPLIERS_API_URL`, y reinicia el servidor tras cambiarlas.