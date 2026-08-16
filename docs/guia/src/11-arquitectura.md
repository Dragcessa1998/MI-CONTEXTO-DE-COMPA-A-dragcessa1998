# Capítulo 11. Arquitectura y decisiones de diseño

Hasta ahora has recorrido cada hito de Nexova por separado: la web pública, la lógica de scoring en TypeScript, el tracker de candidatos, el panel interno y las dos APIs. En este capítulo subes un nivel de abstracción. Vas a mirar el proyecto como lo haría una persona arquitecta de software: dejando de lado los detalles de cada archivo para entender cómo encajan las piezas, qué decisiones se tomaron y, sobre todo, por qué. Un sistema no se juzga solo por lo que hace, sino por lo barato que resulta cambiarlo. Ese es el hilo conductor de todo lo que sigue.

Antes de continuar conviene fijar un término. Una *arquitectura* es el conjunto de decisiones estructurales difíciles de revertir: qué partes existen, qué responsabilidad tiene cada una y cómo se comunican entre sí. Las decisiones de arquitectura no se prueban con un test unitario; se evalúan comparando *compromisos* (en inglés, *trade-offs*): lo que ganas frente a lo que pagas.

En este capítulo aprenderás:

- A leer el sistema completo de Nexova como un único diagrama y a nombrar cada componente y cada flujo de datos.
- Por qué la lógica de negocio vive en un solo lugar (`src/`) y se reutiliza mediante el alias `@logic` en lugar de copiarse.
- Por qué el panel interno (backoffice) habla con los backends por HTTP en vez de importar su lógica directamente, y qué desacople gana con ello.
- Cómo está organizada cada API en capas (tipos, utilidades, datos, rutas) y por qué esa separación facilita el cambio.
- Por qué se eligieron herramientas ligeras como TinyDB y Pydantic, y cómo se logra un manejo de errores uniforme (400, 422, 404).

## El sistema de un vistazo

Nexova es un *monorepo*: un único repositorio que contiene varias aplicaciones y servicios independientes, en lugar de un repositorio por proyecto. Conviven tres aplicaciones de interfaz (Next.js 16, React 18, Tailwind), dos backends (uno en TypeScript con Express, otro en Python con FastAPI) y un módulo de lógica de negocio compartido. El siguiente diagrama muestra los componentes con contenido real y cómo fluyen los datos entre ellos:

```text
                         ┌──────────────────────────────────────────────┐
                         │   src/  (Hito 2 · lógica de negocio en TS)    │
                         │  types/models.ts · utils/{scoring,search,     │
                         │  validations,...} · data/sampleData.ts        │
                         │     FUENTE ÚNICA DE LA LÓGICA Y LOS TIPOS      │
                         └──────────────────────────────────────────────┘
                              ▲ import @logic           ▲ import @logic
                              │ (lógica + tipos)        │ (SOLO tipos)
        ┌─────────────────────┴───────┐      ┌──────────┴──────────────────┐
        │  services/talent-api  :4000 │      │  uis/backoffice       :3000 │
        │  Express + tsx              │      │  Next.js · panel interno    │
        │  CRUD candidatos/vacantes/  │◄─────┤  / · /processes · /suppliers│
        │  procesos · /ranking ·      │ HTTP │  fetch + CORS               │
        │  /reports · CORS            │ fetch └──────────┬──────────────────┘
        └─────────────────────────────┘                 │ HTTP fetch
                                                         ▼
        ┌─────────────────────────────┐      ┌─────────────────────────────┐
        │ uis/talent-pipeline-tracker │      │  services/api         :8000 │
        │ Next.js  :3000              │ HTTP │  FastAPI + Pydantic         │
        │ CRUD de records + notas     ├─────►│  Directorio de proveedores  │
        └─────────────────────────────┘      │  routes/suppliers.py        │
                  │ HTTP                      └──────────┬──────────────────┘
                  ▼                                      ▼
        playground.4geeks.com/tracker         suppliers.db.json  (TinyDB)
                  (API del curso)                  database.py · persistente

        uis/website  (Hito 1 migrado a React: landing + /apply, estático)
```

::: {.note}
**Nota:** las carpetas `agents/`, `data/`, `packages/`, `scripts/`, `infra/`, `internal/`, `mcps/`, `shared/`, `skills/` y `workflows/` forman parte del andamiaje de la plantilla 4Geeks. Solo contienen archivos `README` de referencia (por ejemplo `packages/README.es.md`) y no tienen lógica activa. No las confundas con componentes del sistema: están ahí como puntos de extensión previstos para el futuro.
:::

Tres ideas se repiten en el diagrama y articulan toda la arquitectura. La primera: existe un único origen de la lógica de negocio (`src/`). La segunda: el backoffice no importa esa lógica, sino que llama a las APIs por la red. La tercera: cada backend está organizado en capas con responsabilidades nítidas. Veamos cada una.

## Decisión 1: una sola fuente para la lógica, reutilizada vía `@logic`

El motor de scoring (el cálculo explicable que puntúa de 0 a 100 a un candidato frente a una vacante) se escribió una sola vez, en `src/utils/transformations.ts`. Suma cinco componentes con topes fijos que totalizan 100: habilidades (40), experiencia (20), seniority (15), inglés (15) y salario (10). Junto a él viven los tipos de dominio en `src/types/models.ts` (`Candidate`, `Vacancy`, `SelectionProcess`, `ValidationResult`, `ScoredCandidate`) y las utilidades de búsqueda y validación.

La decisión clave es que nadie copia ese código. Quien lo necesita lo *importa* mediante un alias llamado `@logic`. Un alias de importación es un atajo que el compilador resuelve a una ruta concreta. En `services/talent-api/tsconfig.json` está configurado así:

```json
"paths": {
  "@logic/*": ["../../src/*"]
}
```

El mismo alias aparece en `uis/backoffice/tsconfig.json`. Gracias a él, la talent-api escribe importaciones limpias como estas, sin rutas relativas frágiles del tipo `../../../src/...`:

```ts
import { rankCandidatesForVacancy } from "@logic/utils/transformations";
import type { Candidate, Vacancy } from "@logic/types/models";
```

El compromiso es claro. La alternativa ingenua sería copiar las funciones de scoring dentro de cada servicio. Ganarías que cada componente fuera autónomo, pero pagarías un precio enorme: el día que el negocio decida que el inglés vale 20 puntos en vez de 15, tendrías que tocar varios archivos y rezar para no olvidar ninguno. Con la fuente única, ese cambio ocurre en un solo lugar y todo el sistema queda consistente al instante. Esa propiedad tiene nombre: en diseño de software se llama principio DRY (*Don't Repeat Yourself*, no te repitas).

::: {.tip}
**Tip:** la regla práctica para decidir si algo merece vivir en `src/` es preguntarte si su definición debe ser idéntica en todos los consumidores. La fórmula del scoring y la forma de un `Candidate` sí lo son; la presentación visual de una tabla, no. Lo primero se comparte; lo segundo se queda en cada aplicación.
:::

## Decisión 2: el backoffice consume HTTP, no importa la lógica

Aquí está la decisión arquitectónica más sutil y, probablemente, la más madura del proyecto. El backoffice podría, en teoría, importar `rankCandidatesForVacancy` desde `@logic` y calcular los rankings en el propio navegador. No lo hace. En su lugar, llama a la talent-api por la red. El archivo `uis/backoffice/src/lib/api.ts` lo documenta sin ambigüedad en su cabecera: «el backoffice ya NO importa la lógica del Hito 2 de forma estática: ahora consume la API real por la red (con CORS)».

¿Qué significa esto en la práctica? El backoffice solo toma de `@logic` los *tipos* (las interfaces de TypeScript), nunca las *funciones*:

```ts
import type { Candidate, Vacancy } from "@logic/types/models";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:4000";
```

Los tipos desaparecen al compilar; no son código que se ejecute. Sirven para que el editor y el compilador verifiquen que las respuestas de la API encajan con la forma esperada, pero el cálculo real ocurre del otro lado de la red. El backoffice pide datos con `fetch` y el backend responde con JSON.

Para que un navegador en `localhost:3000` pueda llamar a un backend en otro puerto hace falta CORS (*Cross-Origin Resource Sharing*, intercambio de recursos entre orígenes distintos): un permiso que el servidor declara explícitamente. La talent-api lo concede a mano en `services/talent-api/src/index.ts` (incluyendo la respuesta `204` a la petición preflight `OPTIONS`), y la supplier API lo hace con el middleware de FastAPI en `services/api/main.py`.

El compromiso vale la pena entenderlo bien:

| Aspecto | Importar la lógica (estático) | Consumir por HTTP (esta decisión) |
|---|---|---|
| Acoplamiento | Cliente y lógica viajan juntos | Cliente y servidor evolucionan por separado |
| Datos | El cliente necesita los datos en bruto | El servidor es dueño de los datos |
| Despliegue | Todo se redespliega junto | El backend cambia sin tocar el frontend |
| Latencia | Cero (cálculo local) | Coste de una llamada de red |
| Realismo | Funciona offline, pero artificial | Refleja una arquitectura cliente-servidor real |

Al elegir HTTP, Nexova paga el coste de la latencia de red y de gestionar errores de conexión a cambio de un *desacople* genuino entre cliente y servidor. El backend es el único dueño de los datos y de la lógica; el frontend es un consumidor que podría reescribirse en otra tecnología sin tocar una sola línea del cálculo de scoring. Es exactamente el patrón que encontrarás en cualquier sistema de producción.

Hay un detalle elegante que confirma la madurez de la decisión. El backoffice habla con *dos* backends distintos —la talent-api (Express) y la supplier API (FastAPI)— y cada uno devuelve los errores en un formato propio. Por eso hay dos clientes separados: `lib/api.ts` para la talent-api y `lib/suppliers.ts` para la supplier API. Este último incluye una función `extractFastApiError` que traduce el formato `{"detail": [...]}` de FastAPI a un mensaje legible. El cliente se adapta al servidor, no al revés.

## Decisión 3: separación en capas dentro de cada backend

Cada backend está dividido en capas con una única responsabilidad. No es un accidente; es lo que permite cambiar una pieza sin romper las demás. En la supplier API la separación es nítida:

| Capa | Archivo | Responsabilidad |
|---|---|---|
| Modelos / validación | `services/api/models.py` | Definir la forma de los datos y las reglas |
| Rutas | `services/api/routes/suppliers.py` | Traducir peticiones HTTP en operaciones |
| Datos | `services/api/database.py` | Abrir y exponer el almacén persistente |
| Composición | `services/api/main.py` | Montar la app, CORS y manejo de errores |

La capa de rutas nunca decide cómo se valida un dato ni cómo se guarda; delega lo primero en los modelos de Pydantic y lo segundo en la capa de datos. Fíjate en `database.py`: encapsula TinyDB tras dos funciones (`get_db` y `suppliers_table`) y su propio comentario anticipa el futuro: «Se migrará a Postgres cuando el ORM esté listo». Como nadie fuera de esa capa sabe que por debajo hay un archivo JSON, esa migración tocará un solo archivo. Eso es el valor concreto de separar capas.

La talent-api sigue el mismo espíritu: `src/store.ts` guarda los datos en memoria y `src/index.ts` solo orquesta rutas, apoyándose siempre en `@logic` para la lógica de verdad.

## Decisión 4: herramientas ligeras y errores uniformes

La supplier API es el proyecto oficial «Lightweight Storage API», y el adjetivo no es casual. Combina FastAPI (un framework web de Python centrado en velocidad y validación automática), Pydantic (una biblioteca que valida y modela datos a partir de anotaciones de tipo) y TinyDB (una base de datos documental que persiste en un único archivo JSON). Se gestiona con `uv`, un gestor de dependencias y entornos de Python.

¿Por qué este conjunto y no, por ejemplo, PostgreSQL con un ORM completo? Porque el problema lo permite. El directorio de proveedores son unas pocas decenas de registros con un esquema estable. Pagar la complejidad operativa de una base de datos relacional (servidor, conexiones, migraciones) sería desproporcionado. TinyDB persiste en `suppliers.db.json` y sobrevive a los reinicios, que es todo lo que el requisito pide. El compromiso es deliberado: se renuncia a consultas complejas y a concurrencia alta a cambio de cero infraestructura y un arranque inmediato con `uv run seed` y `uv run uvicorn main:app --port 8000`.

::: {.important}
**Importante:** Pydantic no es solo documentación. En `services/api/models.py`, un proveedor de España con moneda distinta de EUR se rechaza con un `model_validator`; una tarifa que no sea mayor que cero (incluso `Infinity` o `NaN`, gracias a `allow_inf_nan=False`) se rechaza, y una categoría fuera de las nueve válidas también. La validación ocurre *antes* de tocar TinyDB: los datos sucios nunca llegan al almacén.
:::

El manejo de errores también es una decisión de diseño, y aquí es uniforme y predecible. Ambos backends hablan el mismo idioma de códigos HTTP:

| Código | Significado | Dónde se decide |
|---|---|---|
| `201` | Creado con éxito | `POST /suppliers` y `POST /candidates` |
| `400` | Entrada inválida (regla de negocio) | `validateCandidate` en la talent-api |
| `422` | Entrada inválida (forma o tipo) | Pydantic / `RequestValidationError` |
| `404` | El recurso no existe | `_get_or_404` en la supplier API |

La supplier API centraliza el «no encontrado» en una sola función, `_get_or_404`, que cada ruta invoca. Y `main.py` registra un manejador de `RequestValidationError` que convierte cualquier entrada malformada en un `422` consistente, incluso cuando contiene valores no finitos que romperían la serialización JSON por defecto (la función `_sanitize_non_finite` los transforma en texto). El resultado es que el cliente siempre recibe el mismo formato de error para el mismo tipo de fallo, sin sorpresas. Esa previsibilidad es lo que permite que el frontend tenga un único punto donde traducir errores a mensajes para la persona usuaria.

## Resumen

- Nexova es un monorepo con tres interfaces (Next.js), dos backends (Express y FastAPI) y un núcleo de lógica compartida en `src/`; el resto de carpetas son andamiaje de la plantilla sin lógica activa.
- La lógica de negocio y los tipos viven una sola vez en `src/` y se reutilizan mediante el alias `@logic`, evitando la duplicación y manteniendo todo el sistema consistente ante cualquier cambio de regla.
- El backoffice consume las APIs por HTTP con `fetch` y CORS, e importa de `@logic` solo los tipos; así desacopla cliente y servidor, que pueden evolucionar y desplegarse por separado.
- Cada backend separa responsabilidades en capas (tipos/validación, rutas, datos, composición), de modo que cambiar el almacén o una regla afecta a un único archivo.
- Se eligieron herramientas ligeras (TinyDB, Pydantic, FastAPI con `uv`) acordes al tamaño del problema, y un manejo de errores uniforme con códigos `201`, `400`, `422` y `404` predecibles en ambos servicios.