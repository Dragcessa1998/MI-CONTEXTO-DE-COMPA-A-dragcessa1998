# Capítulo 7. Hito 4: infraestructura AI-ready y las apps

Hasta ahora el proyecto Nexova ha avanzado por capas técnicas: una web estática (Hito 1), la lógica de negocio en TypeScript (Hito 2) y una aplicación que consume una API externa (Hito 3). El Hito 4 da un giro de naturaleza distinta. En lugar de añadir una funcionalidad más, prepara el repositorio para que tanto las personas como las herramientas de inteligencia artificial (IA) puedan trabajar dentro de él con un mapa fiable. A esto lo llamamos infraestructura *AI-ready*: un conjunto de archivos y convenciones que documentan el proyecto de forma que un agente de código (un asistente de IA como Claude Code, Cursor o Windsurf, capaz de leer y escribir archivos) pueda incorporarse sin romper nada. Sobre esa base, el hito migra la web pública a React y estrena el backoffice, el panel interno de la consultora.

En este capítulo aprenderás:

- Qué es el *memory-bank* y por qué actúa como memoria persistente del proyecto.
- Cómo `AGENTS.md` define un protocolo de trabajo: lectura obligatoria, flujo previo a cada *commit* y zonas protegidas.
- Qué contiene la carpeta `.agents/` (reglas y *skills*) y cómo se aplica una regla de alcance permanente.
- Cómo se migró la web pública a componentes React en `uis/website`.
- Cómo el `uis/backoffice` consume la talent-api real por HTTP e importa solo *tipos* desde `@logic`, sin copiar la lógica.

## La infraestructura AI-ready

Recordemos el contexto de negocio que define `memory-bank/projectbrief.md`: Nexova Solutions es una consultora de recursos humanos y selección de talento con sede en Valencia y oficina en Miami, dirigida por la CEO Laura Mendoza. Su reto estrella es un *pipeline* (cadena de procesamiento) de *scoring* de currículums explicable, combinado con RAG (*Retrieval-Augmented Generation*, generación de texto apoyada en documentos recuperados) sobre la base de candidatos. En un proyecto así, donde la IA no es un adorno, sino la ventaja competitiva, tiene sentido que el propio repositorio esté pensado para que la IA participe en su construcción.

### El memory-bank: la memoria del proyecto

El problema fundamental de cualquier agente de IA es que no recuerda nada entre sesiones: cada conversación empieza en blanco. El *memory-bank* resuelve esto guardando el contexto del proyecto en archivos Markdown versionados que el agente lee al arrancar. Es, literalmente, la memoria externa del proyecto. Vive en `memory-bank/` y se divide en tres documentos con responsabilidades claras:

| Archivo | Responsabilidad | Frecuencia de cambio |
| --- | --- | --- |
| `projectbrief.md` | Contexto de negocio: qué es Nexova, departamentos, el problema por resolver | Baja (es zona protegida) |
| `techContext.md` | Stack, estructura del monorepo y decisiones de arquitectura | Media (cuando cambia la arquitectura) |
| `progress.md` | Estado actual, decisiones recientes y próximos pasos | Alta (en cada sesión) |

La separación no es casual. El `projectbrief.md` es el contrato del proyecto y apenas se toca; `techContext.md` documenta decisiones como "la lógica de negocio vive una sola vez en `/src` y las apps la importan, no la copian", y `progress.md` es el diario de a bordo. Como advierte su propia cabecera, "un banco de memoria desactualizado deja de ser útil en días", de ahí que actualizarlo sea parte del flujo de trabajo.

::: {.note}
**Nota:** los tres archivos terminan con enlaces tipo `[[techContext]]` y `[[progress]]`. Es la sintaxis de *wikilink* (enlaces internos entre notas, popularizada por herramientas como Obsidian). Sirve para navegar el banco de memoria como una red de notas conectadas, no como archivos sueltos.
:::

### AGENTS.md: el protocolo de trabajo

Si el *memory-bank* es la memoria, `AGENTS.md` es el reglamento. Define cómo opera cualquier agente de código dentro del monorepo (un *monorepo* es un único repositorio que alberga varios proyectos relacionados). Su primera regla es la **lectura obligatoria al inicio de cada sesión**, en este orden: `projectbrief.md`, `techContext.md`, `progress.md`, el `CONTEXT.md` del hito en curso y, por último, las reglas y *skills* de `.agents/`. Así el agente nunca trabaja a ciegas.

La segunda sección establece un **flujo obligatorio antes de cada commit** (un *commit* es un punto de guardado en el control de versiones Git). Son cinco pasos en orden estricto:

1. Revisar contexto (que el cambio cumpla `CONTEXT.md` y las reglas).
2. Verificar tipos y *build* (`npm run build` o `tsc --noEmit` sin errores).
3. No duplicar: la lógica compartida se importa desde su fuente única, no se copia.
4. Actualizar el *memory-bank* (`progress.md` siempre; `techContext.md` si hubo una decisión de arquitectura).
5. Higiene y entrega: no subir secretos, mensajes descriptivos, trabajar en una rama de hito y entregar por *Pull Request* (la solicitud para fusionar una rama en otra).

La tercera sección define las **zonas protegidas**: archivos que el agente no puede modificar sin permiso explícito. Entre ellos, `CONTEXT.md` y `company-choice.md` (decisiones del estudiante), `projectbrief.md` (la verdad de negocio), cualquier archivo `.env` o con secretos, y los *lockfiles* salvo cuando el cambio sea de dependencias. La consigna ante la duda es clara: "pregunta primero".

::: {.important}
**Importante:** la regla "no duplicar" del paso 3 es el corazón de la arquitectura. La lógica de *scoring* del Hito 2 vive una sola vez en `/src` y todas las apps la importan mediante un alias de TypeScript. Copiar y pegar esa lógica en cada app sería una violación directa del protocolo.
:::

### .agents/: reglas y skills

La carpeta `.agents/` contiene la configuración específica para herramientas de agentes, y no debe confundirse con las carpetas `/agents` y `/skills` de la raíz, que son andamiaje (estructura vacía con un README) de la plantilla del curso. Dentro encontramos dos subcarpetas.

`.agents/rules/monorepo-conventions.md` es una **regla** con una cabecera YAML (*front matter*, el bloque de metadatos entre `---`) que declara `scope: always` y `appliesTo: "**/*"`. Esto significa que la regla está *siempre activa*: aplica a cada archivo del repositorio y en cada sesión. Su contenido resume las convenciones clave: dónde va cada tipo de código, el tipado estricto sin `any`, las convenciones de nombres (`camelCase` para variables, `PascalCase` para componentes y tipos) y la obligación de mostrar siempre etiquetas legibles en lugar de valores crudos de la API (por ejemplo, `in_progress` se muestra como "En proceso").

`.agents/skills/scaffold-ui-app/SKILL.md` es una **skill**: una receta reutilizable y verificable para una tarea concreta, en este caso crear una nueva app Next.js dentro de `uis/` (Next.js es el *framework* de React usado en el proyecto). La *skill* declara sus entradas (`app_name`, `purpose`, `shares_business_logic`), los pasos por seguir y, lo más interesante, unos **criterios de aceptación verificables** con comandos concretos. Por ejemplo, comprueba que, si la app comparte lógica, esta se importe y no se copie:

```bash
grep -r "from \"@logic/" uis/<app_name>/src || echo "no importa lógica compartida"
test -d uis/<app_name>/src/lib/business-logic && echo "FALLO: lógica copiada" || echo "OK: sin copia"
```

Una *skill* así convierte una buena práctica en algo que el agente puede ejecutar y comprobar por sí mismo, no en un consejo que se pueda olvidar.

## La web pública migrada a React: uis/website

El Hito 1 entregó una web estática con `index.html`, `application.html` y `validation.js`. El Hito 4 la migra a una aplicación Next.js con React, manteniendo la identidad visual y la accesibilidad, pero ganando la modularidad de los componentes. El resultado vive en `uis/website`.

El `src/app/layout.tsx` define el marco común a todas las páginas: la etiqueta `<html lang="es">`, un enlace "Saltar al contenido principal" para accesibilidad (una buena práctica para usuarios de teclado y lectores de pantalla), y la cabecera y el pie compartidos:

```tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <a href="#main" className="sr-only focus:not-sr-only ...">
          Saltar al contenido principal
        </a>
        <SiteHeader />
        <main id="main">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
```

La página de inicio `src/app/page.tsx` no es más que la composición de las secciones que antes eran bloques de HTML, ahora como componentes React independientes: `Hero`, `Services`, `WhyNexova` y `Contact`. El formulario de candidatura del Hito 1 también encuentra su sitio: la ruta `/apply` (`src/app/apply/page.tsx`) renderiza el componente `ApplyForm`, con la validación reescrita en `src/lib/validation.ts`.

Un detalle revelador está en el `tsconfig.json` de la web: su único alias es `"@/*": ["./src/*"]`. No hay alias `@logic`. La web pública es puramente de presentación; no necesita la lógica de *scoring* y, fiel a la convención de no crear acoplamientos innecesarios, no la importa.

## El backoffice: panel interno que consume la API real

El `uis/backoffice` es la pieza más rica del hito: el panel interno para el equipo de Operaciones de Selección. Su `layout.tsx` es deliberadamente distinto del de la web pública (la convención exige *layouts* separados): en lugar de cabecera y pie corporativos, monta una barra lateral oscura con el logotipo de Nexova y la navegación. El componente `NavLinks` define las tres rutas del panel y resalta la activa con `aria-current="page"`:

| Ruta | Componente | Función |
| --- | --- | --- |
| `/` | `Dashboard` | Panel con KPIs y ranking de candidatos |
| `/processes` | `PipelineBoard` | Tablero del *pipeline* de selección por etapas |
| `/suppliers` | `SuppliersView` | Directorio de proveedores |

### El principio clave: consumir la API, importar solo los tipos

Aquí está la lección central del hito y conviene entenderla con precisión. El `tsconfig.json` del backoffice sí declara el alias hacia la lógica compartida:

```json
"paths": {
  "@/*": ["./src/*"],
  "@logic/*": ["../../src/*"]
}
```

Pero ¿qué importa exactamente a través de `@logic`? Si abres `src/lib/api.ts`, la respuesta es nítida: solo **tipos**.

```ts
import type { Candidate, Vacancy } from "@logic/types/models";
```

La palabra clave es `import type`: esto trae únicamente las definiciones de tipo de TypeScript, que se borran al compilar y no generan ningún código en tiempo de ejecución. El backoffice **no** ejecuta la función de *scoring* del Hito 2. En su lugar, llama por la red a la talent-api real, donde esa lógica sí se ejecuta. El propio comentario de cabecera del archivo lo explica: "el backoffice ya NO importa la lógica del Hito 2 de forma estática: ahora consume la API real por la red (con CORS). Reutiliza los tipos de dominio... la misma fuente de verdad que usa el backend".

La comunicación se hace con `fetch`, la función estándar del navegador para peticiones HTTP. La función `request` centraliza las llamadas, fija la URL base con la variable de entorno `NEXT_PUBLIC_API_URL` (por defecto `http://localhost:4000`), normaliza los errores de red y de negocio en una clase `ApiError`, y traduce el `204` (sin contenido) a `undefined`:

```ts
res = await fetch(`${API_URL}${path}`, {
  ...init,
  headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  cache: "no-store",
});
```

En desarrollo, cuando navegador y API usan orígenes distintos, hace falta CORS (*Cross-Origin Resource Sharing*). La Talent API sólo devuelve un `204` al *preflight* si el origen está en `TALENT_API_CORS_ALLOWED_ORIGINS`; producción usa además el proxy same-origin `/talent-api`:

```ts
res.header("Access-Control-Allow-Origin", origin);
res.header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
res.header("Access-Control-Allow-Headers", "Authorization,Content-Type");
if (req.method === "OPTIONS") return res.sendStatus(204);
```

::: {.tip}
**Tip:** `import type` no es un detalle estético. Si escribieras `import { computeScore }` y llamaras a esa función en el cliente, estarías duplicando la lógica de negocio en el navegador y la API dejaría de ser la única fuente de verdad. Importar solo tipos mantiene la regla "no duplicar" y deja claro el reparto de responsabilidades: el backend calcula, el frontend muestra.
:::

### Las tres rutas en acción

El `Dashboard` (ruta `/`) es un componente cliente que carga en paralelo varios *endpoints* (puntos finales de la API) con `Promise.all`: el resumen de `/reports/summary`, la tasa de cobertura de `/reports/fill-rate`, los candidatos, las vacantes y el ranking de `GET /vacancies/:id/ranking`. Con esos datos pinta los KPIs (indicadores clave de rendimiento), el desglose de candidatos por estado y la tabla de ranking. Gestiona los tres estados posibles —carga, listo y error— y muestra un indicador de conexión que cambia de color según el estado. Permite además dar de alta candidatos, tras lo cual recarga y recalcula el panel en vivo.

El `PipelineBoard` (ruta `/processes`) agrupa los procesos de selección por etapa y permite moverlos con `PATCH /processes/:id`, recargando el tablero al instante. El `SuppliersView` (ruta `/suppliers`) es especial: consume una API distinta, la Supplier Directory hecha con FastAPI en el puerto :8000, con su propio cliente tipado en `src/lib/suppliers.ts`. Como esa API devuelve errores en el formato de FastAPI (`{"detail": [...]}`), el cliente tiene su propio parseo, aunque reutiliza la misma clase `ApiError`. Tanto aquí como en el resto del panel se respeta la convención de dominio: las categorías y los estados se muestran siempre con etiquetas legibles (por ejemplo, `job_boards` se presenta como "Portales de empleo"), nunca con el valor crudo.

## Resumen

- La infraestructura *AI-ready* se compone del *memory-bank* (memoria persistente del proyecto), `AGENTS.md` (protocolo de trabajo) y `.agents/` (reglas y *skills*), todo versionado junto al código.
- El *memory-bank* separa negocio (`projectbrief.md`), arquitectura (`techContext.md`) y estado (`progress.md`); `AGENTS.md` impone lectura inicial obligatoria, un flujo de cinco pasos antes de cada *commit* y zonas protegidas.
- La web pública (`uis/website`) migra el Hito 1 a componentes React con *layout* propio, accesibilidad y la ruta `/apply`; no importa lógica de negocio (su `tsconfig` no tiene alias `@logic`).
- El backoffice (`uis/backoffice`) tiene *layout* de barra lateral y tres rutas: `/` (panel con KPIs y ranking), `/processes` (tablero de *pipeline* con `PATCH /processes/:id`) y `/suppliers` (proveedores).
- El principio rector del backoffice es consumir la talent-api real por HTTP con `fetch` y CORS, e importar de `@logic` únicamente *tipos* (`import type`), de modo que la lógica de *scoring* viva y se ejecute una sola vez en el backend.
