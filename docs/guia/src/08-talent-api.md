# Capítulo 8. La Talent API: el backend que reutiliza la lógica

En los capítulos anteriores construiste la lógica de negocio del Hito 2: un motor de scoring escrito en TypeScript que vive en la carpeta `src/` y que sabe puntuar candidatos, validar datos y generar reportes. Pero esa lógica, por sí sola, solo se puede ejecutar desde un script de consola (`npm run demo`). Para que el panel interno (el backoffice) y, en el futuro, otras aplicaciones puedan usarla, alguien tiene que poner esa lógica detrás de una puerta accesible por la red. Esa puerta es una **API HTTP**: un servidor que escucha peticiones por el protocolo de la web y responde con datos en formato JSON.

En este capítulo construimos exactamente eso. La Talent API es un backend pequeño escrito con **Express** (el framework de servidores web más popular de Node.js) y **TypeScript**, que se ejecuta con **tsx** (un intérprete que corre TypeScript sin compilarlo en un paso aparte). Lo más importante: no reimplementa nada. Toma la lógica del Hito 2 y la expone por HTTP. Es el ejemplo más claro del principio que recorre todo el proyecto Nexova: una sola fuente de verdad para la lógica.

En este capítulo aprenderás:

- Qué es una API HTTP y por qué un servidor Express convierte tu lógica de negocio en un servicio reutilizable.
- Cómo el alias `@logic` permite que el servidor reutilice el código del Hito 2 sin copiarlo.
- El CRUD completo de candidatos, vacantes y procesos de selección, y qué hace cada punto final (endpoint).
- Cómo funciona el endpoint de ranking que aplica el motor de scoring de 100 puntos.
- Qué son los reportes `/reports/summary` y `/reports/fill-rate`.
- Cómo se resuelve el CORS con su petición previa (preflight) para que las apps del navegador puedan consumir la API.
- Cómo arrancar el servidor en el puerto 4000.

## De la lógica al servicio: el papel de Express

Un **endpoint** (o punto final) es una combinación de un método HTTP (como `GET` para leer o `POST` para crear) y una ruta (como `/candidates`). Cuando un cliente, por ejemplo el navegador del backoffice, hace una petición a `GET /candidates`, el servidor ejecuta una función y devuelve una respuesta. Express es la librería que conecta esas rutas con las funciones que las atienden.

El archivo central del servicio es `services/talent-api/src/index.ts`. Su comienzo deja clara la intención del diseño en un comentario del propio código:

```ts
/**
 * Expone candidatos, vacantes, procesos de selección, scoring/ranking y reportes.
 * Toda la lógica de negocio se REUTILIZA desde el módulo del Hito 2 (`/src`) vía el
 * alias @logic; no se duplica aquí.
 */
```

La aplicación se crea en tres líneas y activa el lector de JSON:

```ts
const app = express();
app.use(express.json());
```

`express.json()` es un **middleware**: una función que se ejecuta en medio del flujo de cada petición. Esta en concreto lee el cuerpo de las peticiones que llegan en formato JSON y lo deja disponible en `req.body`, ya convertido en un objeto de JavaScript. Sin ella, los datos que envías al crear un candidato llegarían como texto crudo.

## La reutilización en acción: el alias @logic

Aquí está el corazón del capítulo. Mira las importaciones reales del comienzo de `index.ts`:

```ts
import {
  rankCandidatesForVacancy,
  calculateAverageSalary,
  countCandidatesByStatus,
  findTopSkills,
  calculateVacancyFillRate,
} from "@logic/utils/transformations";
import { validateCandidate, validateVacancy } from "@logic/utils/validations";
import type {
  Candidate,
  Vacancy,
  SelectionProcess,
} from "@logic/types/models";
```

El prefijo `@logic` es un **alias de ruta**: un atajo que apunta a otra carpeta. Está definido en `services/talent-api/tsconfig.json`:

```json
"baseUrl": ".",
"paths": {
  "@logic/*": ["../../src/*"]
}
```

Es decir, `@logic/utils/transformations` se traduce a `../../src/utils/transformations`, que es el código del Hito 2. El servidor no tiene su propia copia del motor de scoring ni de las validaciones: importa las funciones originales. Si mañana corriges la fórmula del scoring en `src/utils/transformations.ts`, la corrección aparece automáticamente en la API. Esto es lo que se conoce como **fuente única de la verdad**: la lógica vive en un solo lugar y todos los consumidores la comparten.

::: {.callout .note}
**Nota:** el alias `@logic` no es magia de Express, sino una capacidad de TypeScript. Como el servicio se ejecuta con tsx, que entiende `tsconfig.json`, el alias se resuelve en tiempo de ejecución sin un paso de compilación previo. Por eso el script de arranque es tan directo: `tsx watch src/index.ts`.
:::

## El almacén en memoria sembrado

Un backend necesita datos sobre los que operar. En este hito todavía no hay una base de datos real; en su lugar, los datos viven en variables de JavaScript dentro de `services/talent-api/src/store.ts`. El propio archivo lo advierte: "En un hito posterior se sustituirá por una base de datos real".

El almacén se siembra (es decir, se rellena con datos iniciales) reutilizando, de nuevo vía `@logic`, los datos de ejemplo del Hito 2:

```ts
import {
  sampleCandidates,
  sampleVacancy,
  sampleProcesses,
} from "@logic/data/sampleData";

export const candidates: Candidate[] = [...sampleCandidates];
export const vacancies: Vacancy[] = [sampleVacancy];
export const processes: SelectionProcess[] = [...sampleProcesses];
```

El operador `...` (spread) copia los elementos del array de ejemplo en uno nuevo, para que la API trabaje sobre su propia copia y no sobre el array original del Hito 2.

El mismo archivo genera identificadores con el formato del dominio de Nexova. Por ejemplo, `nextCandidateId()` produce cadenas como `C-2024-1451`, las vacantes usan el prefijo `V-2024-` y los procesos, `SP-2024-`. Mantener ese formato hace que los datos creados por la API sean indistinguibles de los sembrados.

::: {.callout .warning}
**Aviso:** al ser un almacén en memoria, todo lo que crees o borres se pierde cuando reinicias el servidor. Es perfecto para desarrollar y demostrar, pero no es persistente. Si necesitas datos que sobrevivan a un reinicio, ese es el papel de la otra API del proyecto, el Supplier Directory, que sí usa una base de datos.
:::

## El CRUD de candidatos, vacantes y procesos

CRUD es el acrónimo de las cuatro operaciones básicas sobre datos: crear (Create), leer (Read), actualizar (Update) y borrar (Delete). La Talent API las expone con los métodos HTTP convencionales. Esta es la tabla completa de endpoints:

| Método | Ruta | Qué hace |
|--------|------|----------|
| GET | `/health` | Comprueba que la API responde; devuelve conteos. |
| GET | `/candidates` | Lista candidatos, con filtros `?seniority=` y `?availability=`. |
| GET | `/candidates/:id` | Devuelve un candidato por su id (404 si no existe). |
| POST | `/candidates` | Crea un candidato (valida; 201 si va bien). |
| PUT | `/candidates/:id` | Reemplazo completo de un candidato. |
| PATCH | `/candidates/:id` | Actualización parcial de un candidato. |
| DELETE | `/candidates/:id` | Borra un candidato (204 sin contenido). |
| GET | `/vacancies` | Lista todas las vacantes. |
| GET | `/vacancies/:id` | Devuelve una vacante por su id. |
| POST | `/vacancies` | Crea una vacante (valida). |
| DELETE | `/vacancies/:id` | Borra una vacante. |
| GET | `/vacancies/:id/ranking` | Puntúa y ordena candidatos para esa vacante. |
| GET | `/processes` | Lista los procesos de selección. |
| POST | `/processes` | Crea un proceso (valida candidato, vacante y etapa). |
| PATCH | `/processes/:id` | Avanza la etapa o actualiza score y notas. |
| GET | `/reports/summary` | Resumen agregado de candidatos. |
| GET | `/reports/fill-rate` | Porcentaje de procesos cerrados como contratados. |

Fíjate en cómo el alta de un candidato delega la validación en la función del Hito 2. Este es el endpoint real `POST /candidates`:

```ts
app.post("/candidates", (req: Request, res: Response) => {
  const candidate = buildCandidate(req.body ?? {}, nextCandidateId());
  const validation = validateCandidate(candidate);
  if (!validation.valid) return res.status(400).json({ errors: validation.errors });
  candidates.push(candidate);
  res.status(201).json(candidate);
});
```

El flujo es transparente. La función auxiliar `buildCandidate` arma un objeto `Candidate` a partir del cuerpo de la petición y le asigna un id nuevo. Luego se llama a `validateCandidate`, la misma función pura del Hito 2: si los datos no son válidos, responde con el código **400** (petición incorrecta) y la lista de errores; si lo son, guarda el candidato y responde con **201** (creado). El servidor no sabe nada de las reglas de validación; solo orquesta. Las reglas viven en `@logic`.

Los códigos HTTP que verás en estas rutas siguen la convención del dominio: **201** al crear, **204** al borrar (operación correcta sin contenido que devolver), **400** cuando la validación falla y **404** cuando el recurso no existe.

## El endpoint de ranking: scoring explicable

El endpoint más interesante para Nexova es `GET /vacancies/:id/ranking`, porque es el que pone el motor de scoring al servicio del negocio. Su código es breve:

```ts
app.get("/vacancies/:id/ranking", (req: Request, res: Response) => {
  const vacancy = vacancies.find((item) => item.id === req.params.id);
  if (!vacancy) return res.status(404).json({ error: "Vacante no encontrada" });

  const ranking = rankCandidatesForVacancy(candidates, vacancy).map((entry) => ({
    candidateId: entry.candidate.id,
    fullName: entry.candidate.fullName,
    seniority: entry.candidate.seniority,
    score: entry.score,
  }));

  res.json({ vacancyId: vacancy.id, title: vacancy.title, ranking });
});
```

La función `rankCandidatesForVacancy` (de `src/utils/transformations.ts`) puntúa a cada candidato frente a la vacante y los devuelve ordenados de mayor a menor. La puntuación es la suma de cinco componentes que totalizan **100 puntos**, tal y como están definidos en el código del Hito 2:

- Habilidades (skills): hasta **40** puntos.
- Experiencia: hasta **20** puntos.
- Seniority: hasta **15** puntos.
- Nivel de inglés: hasta **15** puntos.
- Salario: hasta **10** puntos.

Con los datos sembrados verás puntuaciones como **100**, **82** y **10**: un candidato que encaja en todo, otro que encaja casi en todo y otro que apenas cumple. Cada número es trazable hasta sus componentes, lo que cumple el reto estrella de Nexova: un scoring explicable, no una caja negra. La API no inventa la puntuación; la transporta tal cual la calcula la lógica reutilizada.

## Los reportes: agregados para el panel

Dos endpoints producen datos agregados, pensados para alimentar el Dashboard del backoffice. `GET /reports/summary` reúne en un solo objeto el total de candidatos, el salario esperado promedio, el conteo por estado y las cinco habilidades más frecuentes:

```ts
app.get("/reports/summary", (_req: Request, res: Response) => {
  res.json({
    totalCandidates: candidates.length,
    averageExpectedSalary: calculateAverageSalary(candidates),
    byStatus: countCandidatesByStatus(candidates),
    topSkills: findTopSkills(candidates, 5),
  });
});
```

`GET /reports/fill-rate` devuelve el porcentaje de procesos que terminaron en la etapa "Hired" (contratado), calculado por `calculateVacancyFillRate`. Es la "tasa de cobertura": de todos los procesos abiertos, cuántos acabaron en una contratación efectiva. De nuevo, cada cálculo es una función del Hito 2 invocada desde la ruta.

## CORS: dejar entrar al navegador

Cuando una página web intenta llamar a una API en otro origen, el navegador aplica una política de seguridad llamada **CORS** (Cross-Origin Resource Sharing). Por defecto, bloquea esas llamadas a menos que el servidor declare explícitamente que las permite. La Talent API compara el origen con una allowlist explícita:

```ts
app.use((req: Request, res: Response, next: NextFunction) => {
  const origin = req.header("Origin");
  if (!origin || !allowedOrigins.includes(origin)) {
    if (req.method === "OPTIONS") return res.sendStatus(403);
    return next();
  }
  res.header("Access-Control-Allow-Origin", origin);
  res.header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
  res.header("Access-Control-Allow-Headers", "Authorization,Content-Type");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});
```

El middleware refleja únicamente un origen autorizado, permite `Authorization` y resuelve la **petición previa** (preflight) con **204**. Un origen desconocido recibe 403 en el preflight y nunca obtiene cabeceras CORS. Además, todas las rutas con datos exigen un Bearer JWT con rol `manager` o `admin`.

::: {.callout .important}
**Importante:** no uses `Access-Control-Allow-Origin: *` en este servicio. Incluso en local se usa una allowlist (`localhost:3001`/`127.0.0.1:3001` por defecto), de modo que desarrollo y producción comparten el mismo modelo seguro.
:::

## Cómo arrancar la Talent API

El servicio se levanta con dos comandos desde `services/talent-api`:

```bash
npm install
npm run dev
```

El script `dev` está definido en `services/talent-api/package.json` como `tsx watch src/index.ts`. La palabra `watch` indica que tsx vigila los archivos y reinicia el servidor en cuanto guardas un cambio, lo que agiliza el desarrollo. El puerto se fija en `index.ts` con `Number(process.env.PORT ?? 4000)`: por defecto **4000**, salvo que definas la variable de entorno `PORT`. Al arrancar verás en consola:

```
Nexova Talent API escuchando en http://localhost:4000
```

Para una comprobación rápida sin escribir código, visita `http://localhost:4000/health` en el navegador: la API responde con su estado y los conteos de candidatos, vacantes y procesos. Es la forma más sencilla de confirmar que el servidor está vivo y sembrado.

::: {.callout .tip}
**Tip:** el backoffice (capítulo siguiente) espera encontrar la Talent API en el puerto 4000. Arranca primero la API y luego el frontend; si inviertes el orden, el panel mostrará estados de error de carga hasta que la API esté disponible.
:::

## Resumen

- La Talent API es un backend Express + TypeScript, en `services/talent-api/src/index.ts`, que se ejecuta con tsx y expone por HTTP la lógica de negocio del Hito 2.
- Gracias al alias `@logic`, definido en `tsconfig.json` como `../../src/*`, el servidor importa y reutiliza las funciones originales de scoring, validación y reportes en lugar de copiarlas: una sola fuente de la verdad.
- Ofrece un CRUD completo de candidatos, vacantes y procesos, con los códigos HTTP del dominio (201, 204, 400, 404), sobre un almacén en memoria sembrado desde los datos de ejemplo.
- `GET /vacancies/:id/ranking` aplica el motor de 100 puntos (40 + 20 + 15 + 15 + 10) y devuelve candidatos ordenados con puntuaciones explicables como 100, 82 y 10.
- Los reportes `/reports/summary` y `/reports/fill-rate` entregan agregados listos para el panel, y un middleware de CORS con respuesta a la petición previa `OPTIONS` permite que las apps del navegador consuman la API.
- Se arranca con `npm install` y `npm run dev` en el puerto 4000, verificable al instante en `/health`.
