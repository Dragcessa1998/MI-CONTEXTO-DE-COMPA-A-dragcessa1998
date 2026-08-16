# Apéndice B. Glosario

Este apéndice reúne, en orden alfabético, los términos técnicos que aparecen a lo largo del libro sobre el proyecto Nexova. Cada entrada incluye una definición breve en lenguaje claro y, cuando ayuda, un apunte de dónde se usa ese concepto dentro del repositorio real. La idea es que puedas consultarlo de un vistazo: si te tropiezas con una palabra que no recuerdas, vuelve aquí y sigue leyendo.

En este capítulo aprenderás:

- Qué significa cada término clave usado en los hitos del proyecto Nexova.
- Cómo se relacionan esos conceptos entre sí (por ejemplo, REST con HTTP, o Pydantic con validación).
- Dónde encontrar cada idea materializada en el código del repositorio.

## Definiciones

### API

Siglas de *Application Programming Interface* (interfaz de programación de aplicaciones). Es el contrato que permite que dos programas se comuniquen: una parte ofrece operaciones y la otra las consume. En Nexova hay dos API propias, la Talent API (`services/talent-api`) y la Supplier Directory API (`services/api`).

### App Router

Sistema de enrutado de Next.js basado en carpetas dentro de un directorio `app/`, donde cada carpeta es una ruta. El backoffice lo usa: `uis/backoffice/src/app/processes` y `uis/backoffice/src/app/suppliers` son rutas reales.

### Backend

La parte de una aplicación que se ejecuta en el servidor: gestiona datos, lógica de negocio y validaciones, sin interfaz visual. En Nexova, los backends son FastAPI (`services/api`) y Express (`services/talent-api`).

### Backoffice

Panel interno de administración, usado por el personal de la empresa y no por el público. El backoffice de Nexova (`uis/backoffice`) tiene un diseño con barra lateral y consume la Talent API por HTTP.

### CORS

*Cross-Origin Resource Sharing*. Mecanismo de seguridad del navegador que decide si una página de un origen (dominio y puerto) puede pedir datos a otro. La Talent API habilita CORS con su comprobación previa (*preflight*) para que el backoffice del puerto `:3000` pueda hablar con el puerto `:4000`.

### Commit

Instantánea guardada de los cambios en Git, con un mensaje que la describe. Cada commit registra qué cambió y por qué, formando el historial del proyecto.

### CRUD

Acrónimo de *Create, Read, Update, Delete* (crear, leer, actualizar, borrar): las cuatro operaciones básicas sobre datos. El *tracker* (`uis/talent-pipeline-tracker`) implementa el CRUD completo de registros, incluido `deleteRecord` en `src/lib/api.ts`.

### Endpoint

Punto final o dirección concreta de una API a la que se envían peticiones, por ejemplo `GET /vacancies/:id/ranking`. Cada *endpoint* responde a una ruta y un método HTTP determinados.

### FastAPI

Framework de Python para construir API web rápidas, con validación y documentación automáticas. La Supplier Directory API (`services/api/main.py`) está hecha con FastAPI y se gestiona con la herramienta `uv`.

### Fetch

Función del navegador (y de Node.js moderno) para hacer peticiones HTTP desde JavaScript. Tanto el *tracker* como el backoffice usan `fetch` para pedir datos a sus API.

### Frontend

La parte de una aplicación con la que interactúa la persona usuaria: lo que se ve y se toca en el navegador. En Nexova, los frontends viven en `uis/` (website, backoffice y *talent-pipeline-tracker*).

### Fork

Copia personal de un repositorio ajeno, sobre la que puedes trabajar sin afectar al original. La entrega de Nexova se hace desde un *fork* privado del repositorio de 4Geeks.

### Función pura

Función que, para las mismas entradas, devuelve siempre la misma salida y no altera nada fuera de ella (sin efectos secundarios). El motor de *scoring* del Hito 2, en `src/utils`, está construido con funciones puras, lo que lo hace fácil de probar.

### Git

Sistema de control de versiones que registra el historial de cambios de un proyecto y permite trabajar en ramas. El proyecto se organiza con una rama por hito y una rama `main` unificada.

### HTTP

*HyperText Transfer Protocol*. Protocolo que rige la comunicación entre cliente y servidor en la web, mediante métodos como `GET`, `POST`, `PUT`, `PATCH` y `DELETE` y códigos de estado como `200`, `201`, `404` o `422`.

### JSON

*JavaScript Object Notation*. Formato de texto ligero para intercambiar datos estructurados como pares clave-valor. Es el formato que viaja entre los frontends y las API de Nexova.

### JSON-LD

Variante de JSON pensada para describir datos enlazados y semánticos, usada para marcar contenido de forma comprensible para los buscadores. La web pública del Hito 1 (`index.html`) incluye datos estructurados en JSON-LD.

### Monorepo

Un único repositorio que alberga varios proyectos relacionados (frontends, backends y lógica compartida) en lugar de tener uno por cada uno. Nexova es un monorepo: bajo una sola raíz conviven `src/`, `uis/` y `services/`.

### Next.js

Framework basado en React para crear aplicaciones web con enrutado, renderizado en servidor y optimizaciones incluidas. Las tres apps de `uis/` usan Next.js 16 con App Router.

### Node.js

Entorno que permite ejecutar JavaScript fuera del navegador, por ejemplo en un servidor o en herramientas de línea de comandos. La Talent API y las apps de Next.js se ejecutan sobre Node.js.

### npm

*Node Package Manager*. Gestor de paquetes y ejecutor de scripts del ecosistema Node.js. En el proyecto se usa para instalar dependencias (`npm install`) y lanzar tareas (`npm run dev`, `npm run typecheck`).

### Pull Request

Propuesta formal de incorporar tus cambios de una rama a otra, abierta para su revisión antes de fusionarse. La entrega final de Nexova se realiza mediante un Pull Request en la plataforma de 4Geeks.

### Pydantic

Biblioteca de Python que valida y convierte datos a partir de modelos tipados. En `services/api/models.py` define modelos como `SupplierIn` y `SupplierOut` y rechaza con un error `422` toda entrada inválida.

### Query params

Parámetros que viajan en la URL después del signo `?`, usados para filtrar o ajustar una petición, como `?country=&category=`. El *tracker* filtra registros por `status` y `stage` mediante *query params*.

### React

Biblioteca de JavaScript para construir interfaces a base de componentes reutilizables. Todas las apps de `uis/` usan React 18.

### REST

Estilo de diseño de API que organiza los datos como recursos accesibles por URL y manipulados con los métodos de HTTP. Las API de Nexova siguen convenciones REST: cada recurso (proveedores, vacantes, procesos) tiene sus rutas y métodos.

### Scoring

Asignación de una puntuación a cada candidato según criterios definidos, para poder compararlos y ordenarlos. El motor del Hito 2 reparte 100 puntos entre cinco componentes (40 + 20 + 15 + 15 + 10) de forma explicable.

### Schema.org

Vocabulario estándar y compartido para describir entidades del mundo real (empresas, ofertas de empleo, personas) que los buscadores entienden. La web pública lo aplica mediante JSON-LD.

### Seed

Datos iniciales que se cargan en una base de datos vacía para tener un punto de partida realista. El *script* `services/api/seed.py` inserta 15 proveedores y es idempotente: ejecutarlo dos veces no los duplica.

### SSH

*Secure Shell*. Protocolo que cifra la conexión entre tu equipo y un servidor remoto, usado aquí para subir el código a GitHub de forma segura. El *push* del proyecto se hace por SSH.

### Swagger

Interfaz web que documenta una API y permite probar sus *endpoints* desde el navegador. FastAPI la genera automáticamente; en la Supplier API está disponible en `/docs`.

### Tailwind

Framework de CSS basado en clases utilitarias que se aplican directamente en el marcado para dar estilo sin escribir hojas de estilo aparte. Las apps de `uis/` usan Tailwind.

### TinyDB

Base de datos ligera en Python que guarda los datos en un único archivo JSON, sin necesidad de un servidor de base de datos. La Supplier API persiste en `services/api/suppliers.db.json` a través de TinyDB.

### TypeScript

Lenguaje que añade tipos a JavaScript para detectar errores antes de ejecutar el código. La lógica compartida (`src/`) y la Talent API están escritas en TypeScript, con el modo estricto activado (`strict: true` en `tsconfig.json`).

### uv

Herramienta moderna y rápida para gestionar entornos y dependencias de Python, y para ejecutar comandos. La Supplier API se maneja con `uv` (por ejemplo, `uv run seed` o `uv run uvicorn main:app --port 8000`).

### Validación

Comprobación de que los datos recibidos cumplen las reglas esperadas antes de procesarlos o guardarlos. En Nexova la validación está en todas partes: Pydantic en el backend de Python, las funciones de `src/utils/validations.ts` en la lógica, y `validation.js` en el formulario del Hito 1.

::: {.callout .note}
**Nota:** muchos términos están conectados. REST se apoya en HTTP, que transporta JSON; Pydantic hace validación y devuelve códigos HTTP como `422`; y el *scoring* es un conjunto de funciones puras escritas en TypeScript. Leer una entrada suele llevarte de forma natural a otras dos o tres.
:::

::: {.callout .tip}
**Tip:** si una sigla te suena pero no la recuerdas, búscala primero por su forma corta (API, CRUD, CORS, REST, SSH). Casi todos los acrónimos del libro tienen su entrada propia en este glosario.
:::

::: {.callout .important}
**Importante:** el alias `@logic` no es un término genérico, sino una decisión de arquitectura del proyecto. Apunta a la carpeta `../../src` (ver `services/talent-api/tsconfig.json` y `uis/backoffice/tsconfig.json`) para que el backoffice y la Talent API reutilicen la lógica del Hito 2 en lugar de copiarla.
:::

## Resumen

- Este glosario define en orden alfabético los términos técnicos que recorren todos los hitos del proyecto Nexova.
- Los conceptos no están aislados: HTTP, REST, JSON, CORS y los códigos de estado describen juntos cómo se comunican frontends y backends.
- Términos como Pydantic, TinyDB, uv y FastAPI pertenecen al mundo Python de la Supplier API; TypeScript, React, Next.js, Tailwind y npm, al mundo JavaScript de las apps y la Talent API.
- *Scoring*, función pura, validación y *seed* describen el corazón de la lógica de negocio: puntuar candidatos de forma explicable y trabajar con datos fiables.
- Cuando una definición no baste, vuelve al capítulo correspondiente del libro, donde el término aparece aplicado sobre el código real del repositorio.