# Auditoría inicial de rendimiento frontend — Nexova

Fecha: 12/08/2026

## Método y entorno

Se midieron builds de producción, no servidores `next dev`, con Lighthouse
13.4.1 y Google Chrome 151.0.7922.109. La Talent API estuvo activa durante la
medición del dashboard para auditar la vista completa y no su fallback de
error.

| Objetivo | URL | Perfil |
| --- | --- | --- |
| Website, inicio | `http://127.0.0.1:3000/` | Lighthouse desktop |
| Website, inicio | `http://127.0.0.1:3000/` | Lighthouse mobile predeterminado |
| Backoffice, dashboard | `http://127.0.0.1:3001/` | Lighthouse desktop |

Los informes reproducibles están en `audit/before/*.report.html` y
`audit/before/*.report.json`. Las capturas pedidas por la rúbrica están en la
misma carpeta.

## Línea base

### Puntuaciones

| Objetivo | Performance | Accessibility | Best Practices | SEO |
| --- | ---: | ---: | ---: | ---: |
| Website desktop | 100 | 100 | 96 | 100 |
| Website mobile | 100 | 100 | 96 | 100 |
| Backoffice desktop | 100 | 96 | 96 | 100 |

### Señales de carga

| Objetivo | TTFB | FCP | LCP | CLS | TBT | Speed Index |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Website desktop | 47 ms | 208 ms | 408 ms | 0 | 0 ms | 208 ms |
| Website mobile | 2 ms | 754 ms | 1.804 s | 0 | 0 ms | 754 ms |
| Backoffice desktop | 41 ms | 212 ms | 412 ms | 0.0102 | 0 ms | 212 ms |

Lighthouse de navegación no produjo una muestra de INP porque no ejecutó una
interacción representativa. TBT fue 0 ms en los tres perfiles; no se sustituye
INP por una cifra inventada. Todos los valores de LCP y CLS ya estaban dentro
de los umbrales saludables.

## Problemas y causa raíz

### P-01 · `favicon.ico` ausente en ambas aplicaciones

- Evidencia: `errors-in-console` falló en los tres informes; las trazas de red
  identifican `GET /favicon.ico → 404` en los puertos 3000 y 3001.
- Causa: ninguna aplicación App Router define un icono mediante la convención
  `src/app/icon.*` ni incluye un recurso equivalente.
- Impacto: Best Practices queda en 96 en ambos frontends y cada navegación
  genera una petición fallida y ruido de consola.
- Corrección prevista: icono SVG estático y dimensionado en cada aplicación.

### A-01 · contraste insuficiente en el backoffice

- Evidencia: el audit `color-contrast` marcó cinco nodos. La combinación más
  baja fue `text-slate-500` sobre el sidebar `bg-slate-900` (3.75:1); cuatro
  textos `text-slate-500` sobre `bg-slate-100` quedaron en 4.34:1. El mínimo
  exigido para texto normal es 4.5:1.
- Causa: tokens de texto secundario elegidos por apariencia sin verificar el
  contraste sobre los fondos concretos del layout y del dashboard.
- Impacto: Accessibility queda en 96 y esos textos son más difíciles de leer.
- Corrección prevista: subir sólo esos textos a `slate-400` en el sidebar y
  `slate-600` sobre fondos claros, sin alterar la identidad visual.

### P-02 · oportunidades no prioritarias con métricas ya saludables

- Website mobile reporta CSS bloqueante con ahorro estimado de 130 ms y 11 KiB
  de JavaScript legado. Aun así, LCP es 1.804 s, CLS 0, TBT 0 y Performance
  100. Son costes del bundle base de Next/Tailwind y no justifican migrar el
  framework ni reestructurar la app dentro de una auditoría dirigida.
- El dashboard termina con CLS 0.0102 al sustituir el estado de carga por datos
  vivos. Está muy por debajo de 0.1. Se vigilará en la segunda medición, pero no
  se inflará el alcance con una reescritura del flujo de datos.

## Análisis de duplicación

### R-01 · wrapper de campo repetido

`AddCandidateForm.tsx` y `AddSupplierForm.tsx` declaran el mismo componente
local `Field`: etiqueta, tipografía, espaciado y `children`. Debe extraerse como
`FormField` en `/uis/backoffice/src/components/forms/` para que ambos
formularios compartan semántica y estilos.

### R-02 · lista de errores repetida

Los mismos dos formularios repiten el contenedor `role="alert"`, la lista de
mensajes y una instrucción final. La única variación es el texto de la acción.
Un `FormErrorList` con `messages` e `instruction` evita que accesibilidad o
estilos diverjan.

### R-03 · esqueletos de carga repetidos

`Dashboard`, `PipelineBoard`, `SuppliersView` e `IncidentManager` repiten
bloques `animate-pulse` con pequeñas variaciones de altura y grid. Un futuro
`LoadingPanel` parametrizado podría unificarlos, pero no se mezcla con esta
corrección porque sus geometrías sí cumplen funciones distintas y cambiarlo no
movería ninguna señal actual.

### R-04 · boundaries de recuperación duplicados entre frontends

`uis/website/src/app/error.tsx` y `uis/backoffice/src/app/error.tsx` comparten
estructura de alerta, mensaje, reintento y navegación. Una abstracción común
requeriría acordar una capa UI compartida entre aplicaciones; se documenta
como candidata, no se introduce durante una auditoría que prohíbe
reestructurar la arquitectura.

## Plan de corrección y criterio de éxito

Cada problema se corregirá en un commit independiente: icono website, icono
backoffice, contraste backoffice y refactor de formularios. Después se repetirán
las mismas tres ejecuciones.

Se considera éxito si Best Practices mejora de 96 a 100 en cada frontend,
Accessibility del backoffice mejora de 96 a 100 y ningún perfil pierde su 100
de Performance ni empeora fuera de la variación normal de laboratorio.

No se instaló una skill externa adicional: la instalación era opcional y los
hallazgos quedaron identificados directamente por Lighthouse y la revisión de
código. Por ello tampoco se atribuyen recomendaciones a una skill no usada.
