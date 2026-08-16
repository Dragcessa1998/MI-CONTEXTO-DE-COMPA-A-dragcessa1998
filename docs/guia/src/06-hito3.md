# Capítulo 6. Hito 3: Talent Pipeline Tracker con Next.js

En el Hito 1 construiste la web pública de Nexova y en el Hito 2 escribiste el motor de scoring en TypeScript puro. Ahora toca dar un salto: convertir esa lógica en una herramienta interna de verdad, con la que el equipo de People & Talent de Nexova Solutions pueda gestionar las candidaturas de un proceso de selección día a día. Esa herramienta es el **Talent Pipeline Tracker**, una aplicación construida con Next.js que vive en `uis/talent-pipeline-tracker`.

A diferencia del Hito 2, aquí no trabajas con datos de ejemplo en memoria: la aplicación habla con una API REST real, la del curso (`https://playground.4geeks.com/tracker/api/v1`), y debe implementar un **CRUD completo**. CRUD son las siglas de las cuatro operaciones básicas sobre datos: Create (crear), Read (leer), Update (actualizar) y Delete (borrar). La pieza que cierra ese ciclo —y la estrella de este hito— es el borrado de candidaturas con su botón de confirmación.

En este capítulo aprenderás:

- Qué es el **App Router** de Next.js y cómo las carpetas se convierten en rutas, incluidas las rutas dinámicas `[id]`.
- Cómo se construye un **cliente de datos tipado** (`api.ts`) que envuelve `fetch` y cubre los cuatro verbos del CRUD más las notas.
- Por qué el **borrado** (`deleteRecord` → `DELETE /records/:id`) con confirmación inline es la pieza que completa el CRUD.
- Cómo se gestionan los **filtros por query params**, las **notas internas** y los estados de **carga, error y éxito**.
- Por qué se mapean **etiquetas legibles** del dominio en `labels.ts`.

## El App Router de Next.js: carpetas que son rutas

Next.js es un framework construido sobre React. Un framework es un conjunto de convenciones y herramientas que te da una estructura ya resuelta (enrutado, renderizado, optimizaciones) para que no la montes desde cero. La aplicación usa Next.js 16, como ves en `package.json`:

```json
"dependencies": {
  "next": "16.3.1",
  "react": "^18.3.1",
  "react-dom": "^18.3.1"
}
```

La aplicación usa el **App Router**, el sistema de enrutado basado en la carpeta `src/app`. La idea central es sencilla y muy potente: **cada carpeta dentro de `app` es un segmento de la URL, y un archivo llamado `page.tsx` define la página que se renderiza en esa ruta.** No hay un fichero central de configuración de rutas: la estructura de carpetas *es* el mapa de la aplicación.

Mira el árbol real del proyecto y cómo se traduce a URL:

| Archivo en `src/app/` | URL resultante | Qué muestra |
|---|---|---|
| `page.tsx` | `/` | Listado de candidaturas |
| `candidates/new/page.tsx` | `/candidates/new` | Alta de candidatura (POST) |
| `candidates/[id]/page.tsx` | `/candidates/123` | Detalle de una candidatura |
| `candidates/[id]/edit/page.tsx` | `/candidates/123/edit` | Edición (PUT) |

Los corchetes en `[id]` señalan una **ruta dinámica**: ese segmento no es fijo, sino un comodín que captura el identificador real de la candidatura. Cuando alguien visita `/candidates/abc-123`, Next.js renderiza `candidates/[id]/page.tsx` y te entrega el valor `"abc-123"` en una propiedad llamada `params`. Fíjate en lo escueta que es la página de detalle real:

```tsx
import CandidateDetail from "@/components/CandidateDetail";

export default function CandidateDetailPage({
  params,
}: {
  params: { id: string };
}) {
  return <CandidateDetail id={params.id} />;
}
```

La página apenas hace nada: extrae el `id` de la URL y lo pasa a un componente. Este es un patrón deliberado: **las páginas son delgadas y delegan toda la lógica en componentes** dentro de `src/components`. Así, la lógica se prueba y se reutiliza con independencia del enrutado.

Por encima de todas las páginas está `app/layout.tsx`, el **layout raíz**: una plantilla común que envuelve cada página (la cabecera con el logo de Nexova, la navegación y el contenedor `<main>`). Lo que cambie de una ruta a otra entra por la propiedad `children`; lo que se repite (cabecera, menú) se escribe una sola vez aquí. Observa también el atributo `lang="es"` del `<html>`: un detalle de accesibilidad que indica a los lectores de pantalla que el contenido está en español.

::: {.callout .note}
**Nota:** en el App Router, un componente es por defecto un *Server Component* (se ejecuta en el servidor). Para usar estado o efectos del navegador —`useState`, `useEffect`, manejadores de clic— el archivo debe empezar con la directiva `"use client";`. Verás esa línea al inicio de casi todos los componentes interactivos del tracker, como `CandidatesView.tsx` o `CandidateDetail.tsx`.
:::

## El cliente de datos tipado: `api.ts`

Toda comunicación con el backend pasa por un único archivo: `src/lib/api.ts`. Concentrar el acceso a datos en un solo módulo es una decisión de diseño importante: los componentes nunca llaman a `fetch` directamente, sino a funciones con nombres claros como `listRecords` o `deleteRecord`. Si mañana cambia la URL de la API o la forma de manejar errores, lo tocas en un solo sitio.

El corazón del archivo es una función genérica `request<T>` que envuelve la API `fetch` del navegador. El `<T>` es un **parámetro de tipo** (un genérico de TypeScript): permite que quien llame indique qué forma tendrá la respuesta, y TypeScript la comprobará en tiempo de compilación.

```ts
const API_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "https://playground.4geeks.com/tracker/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    ...options,
  });

  if (!response.ok) {
    throw new Error(await extractError(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
```

Varias decisiones merecen comentario. La URL base se lee de la variable de entorno `NEXT_PUBLIC_API_URL` (el prefijo `NEXT_PUBLIC_` indica a Next.js que esa variable puede usarse en el navegador) y, si no está definida, recae en un valor por defecto con `??`, el operador de fusión de nulos. La opción `cache: "no-store"` desactiva la caché para que el tracker siempre muestre datos frescos. Cuando la respuesta no es correcta (`!response.ok`), se lanza un `Error` con un mensaje legible. Y el caso `204 No Content` se trata aparte: es la respuesta típica de un borrado, que no trae cuerpo, así que devolver `undefined` es correcto.

La función `extractError` traduce el cuerpo de error de la API a un mensaje en español apto para mostrar. La API del curso valida con esquemas y devuelve errores en un campo `detail`, que a veces es una cadena y a veces un array; `extractError` cubre ambos casos:

```ts
async function extractError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail) && body.detail.length > 0) {
      return body.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ");
    }
  } catch {
    /* el cuerpo no era JSON */
  }
  return `Error ${response.status} ${response.statusText}`.trim();
}
```

Sobre esa base, cada operación del CRUD es una función de una sola línea. Esta tabla resume el mapeo completo entre función, verbo HTTP y punto final (endpoint, la dirección concreta de la API a la que se llama):

| Función en `api.ts` | Verbo HTTP | Endpoint | Operación CRUD |
|---|---|---|---|
| `listRecords` | GET | `/records?status=&stage=&search=` | Read (listado) |
| `getRecord` | GET | `/records/:id` | Read (uno) |
| `createRecord` | POST | `/records` | Create |
| `updateRecord` | PUT | `/records/:id` | Update (completo) |
| `patchRecord` | PATCH | `/records/:id` | Update (parcial) |
| `deleteRecord` | DELETE | `/records/:id` | **Delete** |
| `listNotes` | GET | `/records/:id/notes` | Read (notas) |
| `addNote` | POST | `/records/:id/notes` | Create (nota) |
| `deleteNote` | DELETE | `/records/:id/notes/:noteId` | Delete (nota) |

La distinción entre `updateRecord` (PUT) y `patchRecord` (PATCH) es conceptual: **PUT reemplaza el recurso completo** (lo usa el formulario de edición al reenviar todos los campos), mientras que **PATCH actualiza solo una parte** (lo usan los controles de estado y etapa, que cambian uno o dos campos sin tocar el resto). Las firmas tipadas lo dejan explícito:

```ts
/** PUT /records/:id (reemplazo completo) */
export function updateRecord(id: string, input: RecordCreateInput): Promise<TrackerRecord> {
  return request<TrackerRecord>(`/records/${id}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

/** PATCH /records/:id (estado y/o etapa) */
export function patchRecord(id: string, input: RecordPatchInput): Promise<TrackerRecord> {
  return request<TrackerRecord>(`/records/${id}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}
```

Los tipos `TrackerRecord`, `RecordCreateInput` y `RecordPatchInput` viven en `src/types/tracker.ts` y reflejan los esquemas de la API. Que las funciones devuelvan `Promise<TrackerRecord>` significa que, en cuanto un componente recibe la respuesta, el editor y el compilador ya saben que tiene campos como `full_name`, `status` o `stage`; un error tipográfico se detecta antes de ejecutar nada.

## El borrado: la pieza que completa el CRUD

Crear, leer y editar candidaturas es lo habitual, pero un CRUD no está completo hasta que se puede borrar. En `api.ts`, la función es deliberadamente simple:

```ts
/** DELETE /records/:id (elimina la candidatura por completo) */
export function deleteRecord(id: string): Promise<void> {
  return request<void>(`/records/${id}`, {
    method: "DELETE",
  });
}
```

Devuelve `Promise<void>` porque un borrado correcto no trae datos de vuelta (recuerda el caso `204` que vimos en `request`). La parte interesante no es la función, sino *cómo se usa con seguridad* en `CandidateDetail.tsx`. Borrar es una acción destructiva e irreversible, así que la interfaz no la ejecuta de golpe: muestra una **confirmación inline**. El componente mantiene tres piezas de estado dedicadas al borrado:

```tsx
const [confirmingDelete, setConfirmingDelete] = useState(false);
const [deleting, setDeleting] = useState(false);
const [deleteError, setDeleteError] = useState<string | null>(null);
```

Al pulsar "Eliminar" no se borra nada: solo se pone `confirmingDelete` en `true`, lo que despliega un panel de confirmación. Ese panel lleva el atributo `role="alertdialog"`, una marca de accesibilidad que indica a los lectores de pantalla que es un diálogo que requiere una decisión:

```tsx
{confirmingDelete && (
  <div role="alertdialog" aria-label="Confirmar eliminación" className="...">
    <p className="text-sm font-medium text-red-800">
      ¿Eliminar la candidatura de {record.full_name}? Esta acción no se puede deshacer.
    </p>
    <div className="mt-3 flex flex-wrap gap-2">
      <button type="button" onClick={handleDelete} disabled={deleting} className="...">
        {deleting ? "Eliminando…" : "Sí, eliminar"}
      </button>
      <button type="button" onClick={() => setConfirmingDelete(false)} disabled={deleting} className="...">
        Cancelar
      </button>
    </div>
  </div>
)}
```

Solo cuando el usuario confirma con "Sí, eliminar" se ejecuta `handleDelete`, que orquesta los estados de carga y error, llama a la API y, si todo va bien, navega de vuelta al listado:

```tsx
async function handleDelete() {
  setDeleting(true);
  setDeleteError(null);
  try {
    await deleteRecord(id);
    router.push("/");
    router.refresh();
  } catch (err) {
    setDeleteError(err instanceof Error ? err.message : "No se pudo eliminar la candidatura");
    setDeleting(false);
  }
}
```

Fíjate en el doble movimiento final: `router.push("/")` lleva al listado y `router.refresh()` fuerza a volver a pedir los datos al servidor, para que la candidatura borrada ya no aparezca. El botón se deshabilita (`disabled={deleting}`) y cambia su texto a "Eliminando…" mientras la petición está en curso, evitando dobles clics. Si la API falla, el error se guarda en `deleteError` y se muestra en un párrafo con `role="alert"`.

::: {.callout .warning}
**Aviso:** nunca conectes una acción destructiva (DELETE) directamente al `onClick` de un botón sin un paso de confirmación. Un clic accidental borraría datos sin vuelta atrás. El patrón de confirmación en dos pasos con `role="alertdialog"` que usa `CandidateDetail.tsx` es el estándar que debes replicar.
:::

## Notas internas: un segundo CRUD anidado

Cada candidatura tiene **notas internas** —comentarios privados del equipo tras una llamada o entrevista— que el componente `NotesSection.tsx` gestiona con su propio mini-CRUD contra `/records/:id/notes`. El patrón es idéntico al del listado: un estado para los datos, otro para la carga y otro para los errores. Listar usa `listNotes` (que extrae el array `data` de la respuesta paginada), añadir usa `addNote` y borrar usa `deleteNote`.

El borrado de notas ilustra una técnica frecuente: la **actualización optimista del estado local**. En lugar de volver a pedir toda la lista tras borrar, se elimina la nota del array en memoria con un `filter`:

```tsx
async function handleDelete(noteId: string) {
  setDeletingId(noteId);
  setError(null);
  try {
    await deleteNote(recordId, noteId);
    setNotes((current) => current.filter((note) => note.id !== noteId));
  } catch (err) {
    setError(err instanceof Error ? err.message : "No se pudo eliminar la nota");
  } finally {
    setDeletingId(null);
  }
}
```

El estado `deletingId` guarda *cuál* nota se está borrando, para deshabilitar solo el botón de esa fila y mostrar "Eliminando…" únicamente en ella.

## Filtros por query params: la URL como estado

El listado se construye en `CandidatesView.tsx` y los controles de filtrado en `Filters.tsx`. La decisión de diseño más elegante de este hito es que **el estado de los filtros no vive en una variable de React, sino en la URL** como query params (los pares `clave=valor` que van tras el `?`). Así, una búsqueda concreta se puede guardar en favoritos, compartir por enlace o recargar sin perder el contexto.

`CandidatesView` lee esos parámetros con el hook `useSearchParams` y los pasa al cliente de datos:

```tsx
const searchParams = useSearchParams();
const status = searchParams.get("status") ?? "";
const stage = searchParams.get("stage") ?? "";
const search = searchParams.get("q") ?? "";

const fetchData = useCallback(async () => {
  setLoading(true);
  setError(null);
  try {
    const response = await listRecords({ status, stage, search });
    setRecords(response.data);
    setTotal(response.total);
  } catch (err) {
    setError(err instanceof Error ? err.message : "Error desconocido al cargar las candidaturas");
  } finally {
    setLoading(false);
  }
}, [status, stage, search]);
```

`Filters.tsx` hace el camino inverso: cuando cambias un desplegable, llama a `router.replace` para reescribir la URL con los nuevos parámetros, sin recargar la página. La búsqueda por texto se aplica con un **debounce** de 350 milisegundos (un pequeño retardo que espera a que dejes de teclear antes de lanzar la petición, evitando una consulta por cada tecla). En `api.ts`, `listRecords` traduce esos filtros a una cadena de consulta con `URLSearchParams`:

```ts
export function listRecords(filters: RecordFilters = {}): Promise<RecordListResponse> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.stage) params.set("stage", filters.stage);
  if (filters.search) params.set("search", filters.search);
  params.set("limit", "100");
  const query = params.toString();
  return request<RecordListResponse>(`/records${query ? `?${query}` : ""}`);
}
```

Como `CandidatesView` usa `useSearchParams`, Next.js exige envolverlo en un límite de `Suspense`; por eso `app/page.tsx` lo hace, mostrando un `LoadingState` mientras se resuelve.

## Estados de carga, error y éxito

Un detalle que distingue una aplicación profesional de un prototipo es que **nunca deja al usuario sin saber qué está pasando**. El tracker trata los tres estados de cada operación asíncrona de forma explícita. En `src/components/ui.tsx` viven tres componentes reutilizables —`LoadingState`, `ErrorState` y `EmptyState`— y el patrón de renderizado condicional se repite en todas las vistas. Así lo hace `CandidatesView`:

```tsx
{loading ? (
  <LoadingState label="Cargando candidaturas…" />
) : error ? (
  <ErrorState message={error} onRetry={fetchData} />
) : records.length === 0 ? (
  <EmptyState message="No hay candidaturas que coincidan con los filtros aplicados." />
) : (
  <CandidateTable records={records} />
)}
```

`ErrorState` incluye un botón "Reintentar" que vuelve a invocar `fetchData`, y lleva `role="alert"`; `LoadingState` lleva `role="status"` con `aria-live="polite"`. El éxito también es visible: en `StatusStageControls.tsx`, tras un PATCH correcto, aparece un mensaje "Estado actualizado ✓" en verde durante la edición.

## Por qué se mapean etiquetas legibles: `labels.ts`

La API devuelve valores crudos como `in_progress` o `personal_interview`: cómodos para programar, pero impropios de una interfaz que verá el equipo de selección. El archivo `src/lib/labels.ts` resuelve esto con tablas de traducción del dominio:

```ts
export const STATUS_LABELS: Record<RecordStatus, string> = {
  received: "Recibida",
  in_progress: "En proceso",
  selected: "Seleccionada",
  discarded: "Descartada",
};

export const STAGE_LABELS: Record<RecordStage, string> = {
  pending: "Pendiente de revisión",
  review: "En revisión",
  personal_interview: "Entrevista personal",
  technical_interview: "Entrevista técnica",
  offer_presented: "Oferta presentada",
};
```

Las funciones `statusLabel` y `stageLabel` traducen un valor crudo a su etiqueta, con respaldo al propio valor si fuese desconocido. El tipo `Record<RecordStatus, string>` obliga a definir una etiqueta para *cada* estado posible: si mañana la API añade un estado nuevo, TypeScript te avisa de que falta su traducción. Este detalle aporta tres ventajas: la interfaz queda en español neutro y profesional, la traducción está centralizada en un único archivo y los valores técnicos nunca se filtran a la pantalla.

::: {.callout .tip}
**Tip:** centralizar las etiquetas legibles en un solo módulo es el primer paso hacia la internacionalización. Si Nexova quisiera una versión en inglés para su sede de Miami, bastaría con duplicar `labels.ts` y elegir la tabla según el idioma; ni un solo componente cambiaría.
:::

## Resumen

- El **App Router** de Next.js convierte la estructura de carpetas de `src/app` en rutas; `page.tsx` define cada página y `[id]` crea rutas dinámicas que entregan el identificador por `params`.
- Todo el acceso a datos se concentra en `src/lib/api.ts`, un **cliente tipado** que envuelve `fetch` con la función genérica `request<T>` y cubre el CRUD completo (`listRecords`, `getRecord`, `createRecord`, `updateRecord`, `patchRecord`, `deleteRecord`) más las notas.
- El **borrado** (`deleteRecord` → `DELETE /records/:id`) completa el CRUD y se ejecuta solo tras una **confirmación inline** con `role="alertdialog"` en `CandidateDetail.tsx`, evitando pérdidas accidentales de datos.
- Los **filtros y la búsqueda viven en la URL** como query params, lo que permite compartir y recargar vistas; cada operación asíncrona muestra estados explícitos de **carga, error y éxito**.
- `src/lib/labels.ts` traduce los valores crudos de la API (`in_progress`, `personal_interview`) a **etiquetas legibles** del dominio, con la seguridad de tipos que da `Record<RecordStatus, string>`.
