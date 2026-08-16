# Capítulo 3. Prepara tu entorno y conoce el terreno

Antes de escribir una sola línea de código sobre el proyecto Nexova necesitas dos cosas: que tu ordenador tenga instaladas las herramientas correctas y que tengas un mapa mental del repositorio. Nexova no es una aplicación suelta, sino un *monorepo*: un único repositorio de Git que reúne varias aplicaciones y servicios que se desarrollan juntos pero se ejecutan por separado. Si nunca has trabajado con uno, no te preocupes; este capítulo te lleva de la mano desde la instalación de las herramientas hasta dejar cada pieza con sus dependencias listas. No vamos a arrancar ningún servidor todavía (eso es materia del capítulo de operación); aquí solo dejamos el terreno preparado.

En este capítulo aprenderás:

- Qué herramientas necesitas y cómo comprobar que están instaladas.
- Cómo clonar tu fork del repositorio por SSH o por HTTPS.
- Cómo está organizado el monorepo y qué carpetas son código real y cuáles son andamiaje de la plantilla.
- Qué es el alias `@logic` y por qué evita duplicar la lógica de negocio.
- Cómo instalar las dependencias de cada aplicación de frontend y del backend de Python con `uv`.
- Un *footgun* (trampa) clásico de macOS con el entorno virtual `.venv` y cómo solucionarlo.

## Requisitos previos

El monorepo de Nexova mezcla dos mundos: TypeScript/JavaScript (las webs y una de las APIs) y Python (la API de proveedores). Por eso necesitas dos *runtimes* (entornos de ejecución) distintos.

| Herramienta | Versión mínima | Para qué se usa |
| --- | --- | --- |
| Node.js | v20 o superior | Ejecutar las apps Next.js (`uis/*`), la talent-api (Express con `tsx`) y la lógica del Hito 2. |
| Python | 3.11 o superior | Ejecutar la Supplier Directory API en `services/api`. Lo exige `pyproject.toml` (`requires-python = ">=3.11"`). |
| uv | Última estable | Gestor de paquetes y entornos de Python; instala Python y dependencias por ti. |
| Git | Cualquiera reciente | Clonar el repositorio y entregar tu trabajo. |
| VS Code | Última estable | Editor recomendado (cualquier editor sirve). |

`uv` es un gestor de proyectos de Python escrito en Rust, extremadamente rápido, que sustituye a la combinación tradicional de `pip` y `venv`. Su ventaja es que, la primera vez que lo invocas en un proyecto, descarga el intérprete de Python adecuado y todas las dependencias automáticamente, sin que tengas que crear entornos a mano.

Comprueba lo que ya tienes instalado:

```bash
node --version    # debería imprimir v20.x.x o superior
python3 --version # debería imprimir 3.11.x o superior
git --version
uv --version
```

Si te falta Node.js, descárgalo desde su web oficial o instálalo con un gestor de versiones como `nvm`. Para `uv`, en macOS y Linux el instalador oficial es una sola orden:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

::: {.callout .note}
**Nota:** no necesitas instalar Python a mano si vas a usar `uv`; el comando `uv run` descarga el intérprete que pide `pyproject.toml` la primera vez. Tener `python3` del sistema es útil solo para comprobaciones rápidas.
:::

## Clona tu fork

Trabajarás sobre un *fork* (una copia personal) del repositorio de la academia. El fork de referencia es privado y se aloja en `4GeeksAcademy/MI-CONTEXTO-DE-COMPA-A-dragcessa1998`. La entrega final se hace mediante un *Pull Request* en la plataforma de 4Geeks (ten en cuenta que la herramienta de línea de comandos `gh` de GitHub no está instalada en este entorno; usarás el `git` clásico).

Hay dos formas de clonar. Si tienes una clave SSH configurada en tu cuenta de GitHub, usa SSH (no te pedirá usuario y contraseña en cada operación):

```bash
git clone git@github.com:4GeeksAcademy/MI-CONTEXTO-DE-COMPA-A-dragcessa1998.git
```

Si prefieres HTTPS o aún no has configurado SSH:

```bash
git clone https://github.com/4GeeksAcademy/MI-CONTEXTO-DE-COMPA-A-dragcessa1998.git
```

::: {.callout .tip}
**Tip:** evita clonar el proyecto dentro de carpetas sincronizadas con la nube como `Desktop` o `Documents` cuando estas estén bajo iCloud Drive. Más adelante verás por qué esto puede romper el entorno de Python en macOS. Si puedes, clona en una ruta sencilla como `~/code/nexova`.
:::

El proyecto se organiza con **ramas por hito** y una rama `main` unificada que contiene el proyecto completo. Tras clonar, estarás en `main` con todo integrado.

## Recorrido por la estructura del monorepo

Al entrar en la carpeta del proyecto verás muchas carpetas. La clave para no perderte es saber que solo unas pocas contienen código real del proyecto Nexova; el resto son **andamiaje** intencional de la plantilla de 4Geeks (cada una trae solo un `README` que describe su propósito para futuros hitos).

Esta es la guía de directorios que importa:

| Carpeta o archivo | Qué contiene |
| --- | --- |
| `src/` | Lógica de negocio compartida en TypeScript (Hito 2): tipos de dominio, motor de scoring, búsquedas y validaciones. Es la **fuente única** de la lógica y se importa vía el alias `@logic`. |
| `uis/website/` | Web pública corporativa de Nexova en Next.js 16 (Hito 4), migrada desde la web estática del Hito 1. |
| `uis/backoffice/` | Panel interno en Next.js: KPIs, pipeline de procesos y directorio de proveedores. Consume las APIs reales por HTTP. |
| `uis/talent-pipeline-tracker/` | Tracker de candidatos (Hito 3) en Next.js sobre la API del curso. |
| `services/api/` | Supplier Directory API: FastAPI + TinyDB + Pydantic, gestionada con `uv`. |
| `services/talent-api/` | API de talento (candidatos, vacantes, procesos, reportes) en Express + TypeScript, ejecutada con `tsx`. |
| `memory-bank/` | Banco de memoria del proyecto: `projectbrief.md`, `techContext.md`, `progress.md`. |
| `.agents/` | Reglas y skills para el trabajo asistido por IA (Hito 4). |
| `docs/` | Documentación general del repositorio. |
| `AGENTS.md`, `CONTEXT.md` | Convenciones de trabajo y briefing de empresa, en la raíz. |
| `index.html`, `application.html`, `validation.js` | Web estática original del Hito 1, en la raíz. |
| `agents/`, `data/`, `packages/`, `scripts/`, `infra/`, `internal/`, `mcps/`, `shared/`, `skills/`, `workflows/` | **Andamiaje** de la plantilla; cada carpeta trae un `README` con su propósito, sin código activo. |

Dentro de `src/` encontrarás la columna vertebral lógica del proyecto, con esta forma exacta:

```text
src/
  types/models.ts         ← Candidate, Vacancy, SelectionProcess, ScoredCandidate…
  utils/collections.ts    ← agrupar, ordenar, transformar listas
  utils/search.ts         ← búsquedas (incluida la binaria por salario)
  utils/transformations.ts
  utils/validations.ts
  data/sampleData.ts      ← datos de ejemplo
  demo.ts                 ← demostración ejecutable del motor de scoring
```

::: {.callout .important}
**Importante:** las carpetas de andamiaje (`agents/`, `packages/`, `infra/`, `mcps/`, etc.) no se tocan en este proyecto. Si abres una y solo encuentras un `README`, es lo esperado: están reservadas para hitos futuros y no debes llenarlas para "completar" nada.
:::

## El alias `@logic`: una sola fuente de verdad

Aquí está la idea más importante de la arquitectura. La lógica de negocio (los tipos del dominio, el motor de scoring y las validaciones) vive **una sola vez** en `src/`. Tanto la `talent-api` como el `backoffice` la reutilizan en lugar de copiarla, gracias a un *alias de ruta* de TypeScript llamado `@logic`.

Un alias de ruta es un atajo que mapea un nombre corto a una carpeta real. En `services/talent-api/tsconfig.json` está declarado así:

```json
"paths": {
  "@logic/*": ["../../src/*"]
}
```

Eso permite que el código importe desde la lógica compartida con una ruta limpia, como se ve en `services/talent-api/src/index.ts`:

```ts
import { findCandidateById } from "@logic/utils/search";
import { validateCandidate, validateVacancy } from "@logic/utils/validations";
```

El `backoffice` hace lo mismo, pero con un matiz clave: solo importa **tipos**, no la implementación, porque obtiene los datos por HTTP desde las APIs reales. Lo verás en `uis/backoffice/src/lib/api.ts`:

```ts
import type { Candidate, Vacancy } from "@logic/types/models";
```

El `backoffice` define además un segundo alias, `@/*`, que apunta a su propio `src/`. Así conviven dos atajos: `@/` para lo local de cada app y `@logic/` para la lógica central del monorepo.

::: {.callout .note}
**Nota:** que ambos lados compartan exactamente los mismos tipos significa que, si cambias la forma de un `Candidate` en `src/types/models.ts`, el compilador de TypeScript avisará en todos los puntos del monorepo que dependan de él. Esa es la ventaja real de no copiar la lógica.
:::

## Instala las dependencias del frontend y de la talent-api

Cada aplicación de Node.js declara sus propias dependencias en su `package.json` y se instala por separado. Desde la raíz del repositorio, primero instala las dependencias de la lógica del Hito 2 (que aportan `tsx` y `typescript`):

```bash
npm install
```

Luego, entra en cada app o servicio de Node y repite la instalación. Las tres webs son Next.js 16 con React 18 y Tailwind; la talent-api es Express con TypeScript:

```bash
npm install --prefix uis/website
npm install --prefix uis/backoffice
npm install --prefix uis/talent-pipeline-tracker
npm install --prefix services/talent-api
```

El uso de `--prefix` evita tener que cambiar de directorio en cada paso: instala en la carpeta indicada sin moverte. Si prefieres entrar carpeta a carpeta, también vale; el efecto es el mismo. Tras esto, cada app tendrá su propia carpeta `node_modules` con todo lo necesario.

::: {.callout .tip}
**Tip:** instalar las dependencias no arranca nada. El comando que pone en marcha cada app (`npm run dev`) lo dejaremos para el capítulo de operación. Aquí solo descargas paquetes.
:::

## Prepara el backend de Python con uv

La Supplier Directory API en `services/api` no usa npm: se gestiona con `uv`. No tienes que crear ningún entorno virtual a mano ni instalar Python aparte. La primera vez que ejecutes una orden `uv run` dentro de esa carpeta, `uv` leerá `pyproject.toml`, descargará el intérprete de Python adecuado y las dependencias (FastAPI, Uvicorn, TinyDB y Pydantic), y creará el entorno virtual `.venv` automáticamente.

Para preparar el backend, basta con cargar los datos iniciales (el *seed*). El comando `seed` está declarado como punto de entrada del proyecto en `pyproject.toml` (`seed = "seed:main"`) y carga 15 proveedores de ejemplo de forma idempotente, es decir, lo puedes ejecutar varias veces sin duplicar registros:

```bash
uv run --directory services/api seed
```

Con eso, `uv` deja instalado el entorno y crea el archivo de base de datos `suppliers.db.json` con los proveedores. (El arranque del servidor con Uvicorn lo veremos más adelante.)

### El footgun de macOS con .venv

::: {.callout .warning}
**Aviso:** si clonaste el proyecto en una carpeta del `Desktop` o sincronizada con iCloud, el comando anterior puede fallar con `ModuleNotFoundError: No module named 'seed'`, aunque todo parezca instalado. La causa es que macOS marca los archivos del entorno virtual `.venv` con el flag `UF_HIDDEN` (oculto), y Python ignora los archivos `.pth` ocultos, por lo que no encuentra el paquete editable.
:::

La solución, documentada en el propio `services/api/README.md`, es quitar ese flag oculto y reintentar:

```bash
chflags -R nohidden services/api/.venv
uv run --directory services/api seed
```

Si el problema persiste, hay una alternativa que no depende del paquete editable: ejecutar el script directamente.

```bash
uv run --directory services/api python seed.py
```

La forma más limpia de evitar este problema de raíz es no alojar el proyecto bajo iCloud Drive, tal y como se recomendó al clonar.

## Resumen

- Necesitas Node.js v20+, Python 3.11+, `uv`, Git y un editor como VS Code; verifica cada versión antes de empezar.
- Clona tu fork por SSH (recomendado) o por HTTPS; la entrega final se hace por Pull Request en la plataforma de 4Geeks.
- Solo `src/`, `uis/*`, `services/*`, `memory-bank/`, `.agents/` y `docs/` contienen código real; el resto de carpetas son andamiaje intencional con solo un `README`.
- El alias `@logic` mapea a `../../src` y permite que la talent-api y el backoffice reutilicen la lógica del Hito 2 sin copiarla; el backoffice solo importa tipos.
- Instala las dependencias de cada app de Node con `npm install` por carpeta, y prepara el backend de Python con `uv run --directory services/api seed`.
- En macOS, si el seed falla con `ModuleNotFoundError`, ejecuta `chflags -R nohidden services/api/.venv` y reintenta, o usa `uv run python seed.py`.