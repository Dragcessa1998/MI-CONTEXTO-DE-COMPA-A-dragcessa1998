# Apéndice A. Referencia rápida de comandos

Este apéndice condensa, en formato de tarjeta de consulta, todos los comandos que necesitas para arrancar, comprobar y entregar el monorepo de Nexova. Está pensado para tenerlo abierto en una segunda pantalla: localiza la pieza que vas a tocar, copia el comando y sigue adelante. Cada bloque indica desde qué carpeta se ejecuta y qué herramienta usa: `npm` (gestor de paquetes de Node.js) para la lógica y las aplicaciones JavaScript, y `uv` (gestor de proyectos de Python, sucesor rápido de `pip`) para la API de Python.

En este capítulo aprenderás:

- A correr la lógica del Hito 2 con `npm run typecheck` y `npm run demo`.
- A levantar cada aplicación Next.js y cada API con sus comandos exactos.
- A gestionar la Supplier API en Python con `uv`.
- A entregar tu trabajo con Git y a resolver el problema de `.venv` en macOS.

## Lógica del Hito 2 (raíz del repositorio)

La capa de negocio en TypeScript vive en `src/` y se ejecuta desde la raíz del monorepo. El archivo `package.json` raíz solo define dos guiones (scripts).

| Comando | Qué hace |
| --- | --- |
| `npm install` | Instala `tsx` y `typescript` (dependencias de desarrollo). |
| `npm run typecheck` | Ejecuta `tsc --noEmit`: valida tipos con `strict:true`, sin generar archivos. |
| `npm run demo` | Ejecuta `tsx src/demo.ts`: corre el motor de scoring sobre los datos de ejemplo. |

```bash
npm install
npm run typecheck
npm run demo
```

::: {.callout .note}
**Nota:** `typecheck` no produce salida si todo está correcto; el silencio es buena señal. `demo` sí imprime el resultado del scoring (componentes que suman 100) en la consola.
:::

## Aplicaciones Next.js

Las tres aplicaciones (`uis/website`, `uis/backoffice`, `uis/talent-pipeline-tracker`) comparten exactamente los mismos guiones de Next.js 16. Entra en cada carpeta y ejecuta:

```bash
npm install     # instala dependencias (la primera vez)
npm run dev     # servidor de desarrollo con recarga en caliente
npm run build   # compilación de producción
npm run start   # sirve la compilación de producción
```

| Aplicación | Carpeta | Puerto por defecto |
| --- | --- | --- |
| Web pública | `uis/website` | 3000 |
| Backoffice | `uis/backoffice` | 3000 |
| Talent Pipeline Tracker | `uis/talent-pipeline-tracker` | 3000 |

::: {.callout .warning}
**Aviso:** las tres usan `next dev`, que toma el puerto 3000 por defecto. No las levantes a la vez sin cambiar el puerto: `npm run dev -- -p 3001`. El tracker además lee `NEXT_PUBLIC_API_URL` (en `uis/talent-pipeline-tracker/src/lib/api.ts`) y el backoffice usa `NEXT_PUBLIC_API_URL` (talent-api, `:4000`) y `NEXT_PUBLIC_SUPPLIERS_API_URL` (supplier API, `:8000`).
:::

## Talent API (Express + TypeScript)

Está en `services/talent-api`, corre con `tsx` (sin compilar) y escucha en el puerto 4000.

```bash
cd services/talent-api
npm install
npm run dev        # tsx watch src/index.ts (recarga al guardar)
```

Puntos finales (endpoints) destacados: `GET /vacancies/:id/ranking` (ranking por scoring), `GET /reports/summary` y `GET /reports/fill-rate`. Reutiliza la lógica de `src/` mediante el alias `@logic`; no la copia.

## Supplier API (FastAPI + TinyDB, gestionada con uv)

Está en `services/api`. Aquí no se usa `npm`, sino `uv`, que crea y gestiona el entorno virtual de Python (`.venv`) y resuelve dependencias.

```bash
cd services/api
uv run seed                           # carga 15 proveedores (idempotente)
uv run uvicorn main:app --port 8000   # API en :8000, Swagger UI en /docs
```

El guion `seed` está declarado en `services/api/pyproject.toml` (`seed = "seed:main"`) y apunta a la función `main()` de `seed.py`. Si prefieres no depender de ese alias, ejecuta el archivo directamente:

```bash
uv run python seed.py
```

| Comando | Qué hace |
| --- | --- |
| `uv run seed` | Inserta los 15 proveedores en `suppliers.db.json` (omite los que ya existen). |
| `uv run python seed.py` | Equivalente al anterior, invocando el archivo a mano. |
| `uv run uvicorn main:app --port 8000` | Levanta la API; explora y prueba en `http://localhost:8000/docs`. |

## Git (clonar, registrar y entregar)

El flujo de entrega usa un fork privado y `push` por SSH. La plataforma 4Geeks recibe el trabajo mediante un Pull Request; `gh` (CLI de GitHub) no está instalado, así que el PR se abre desde la web.

```bash
git clone git@github.com:4GeeksAcademy/MI-CONTEXTO-DE-COMPA-A-dragcessa1998.git
git status                      # ver qué ha cambiado
git add .                       # preparar todos los cambios
git commit -m "feat: descripción del cambio"
git push                        # subir (por SSH) a tu fork
```

::: {.callout .tip}
**Tip:** trabaja con una rama por hito y unifica en `main`. Lo que ignora el repositorio está en `.gitignore` (`node_modules/`, `dist/`, `.DS_Store`) y en `services/api/.gitignore` (`.venv/`, `__pycache__/`, `suppliers.db.json`): no fuerces su subida.
:::

## Soluciones rápidas

### `uv run seed` falla con `ModuleNotFoundError` en macOS

En carpetas dentro del Escritorio o sincronizadas con iCloud, macOS puede marcar `.venv` con el atributo oculto `UF_HIDDEN`, y entonces `uv` no encuentra los módulos instalados. La solución es quitar ese atributo y reintentar:

```bash
cd services/api
chflags -R nohidden .venv
uv run seed
```

::: {.callout .important}
**Importante:** si el problema persiste, usa la vía alternativa `uv run python seed.py`, que invoca el intérprete directamente y suele esquivar el atributo oculto.
:::

## Resumen

- La lógica del Hito 2 se valida y demuestra desde la raíz con `npm run typecheck` y `npm run demo`.
- Las tres aplicaciones Next.js comparten `npm install`, `npm run dev` y `npm run build`; cuidado con el puerto 3000 compartido.
- La Talent API (Express) corre en `:4000` con `npm run dev`; la Supplier API (FastAPI), en `:8000` con `uv run seed` y `uv run uvicorn main:app --port 8000`.
- La entrega es por Git con `push` SSH a tu fork y un Pull Request abierto desde la web.
- Si `uv run seed` falla en macOS, aplica `chflags -R nohidden .venv` o ejecuta `uv run python seed.py`.