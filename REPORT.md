# Informe de mejoras de rendimiento — Nexova

Fecha de cierre: 12/08/2026

## Resultado

Se repitieron exactamente los tres perfiles descritos en `AUDIT.md`, con los
mismos builds de producción, Lighthouse 13.4.1 y Chrome 151. La web corporativa
y el backoffice terminan con **100 en las cuatro categorías medidas**.

| Objetivo | Performance | Accessibility | Best Practices | SEO |
| --- | ---: | ---: | ---: | ---: |
| Website desktop · antes | 100 | 100 | 96 | 100 |
| Website desktop · después | 100 | 100 | 100 | 100 |
| Website mobile · antes | 100 | 100 | 96 | 100 |
| Website mobile · después | 100 | 100 | 100 | 100 |
| Backoffice desktop · antes | 100 | 96 | 96 | 100 |
| Backoffice desktop · después | 100 | 100 | 100 | 100 |

Mejora cuantificada:

- Website: **+4 Best Practices** tanto en desktop como en mobile.
- Backoffice: **+4 Accessibility** y **+4 Best Practices**.
- Performance y SEO conservaron 100 en todos los perfiles.

## Señales antes y después

| Objetivo | TTFB | FCP | LCP | CLS | TBT | Speed Index |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Website desktop · antes | 47 ms | 208 ms | 408 ms | 0 | 0 ms | 208 ms |
| Website desktop · después | 60 ms | 211 ms | 411 ms | 0 | 0 ms | 211 ms |
| Website mobile · antes | 2 ms | 754 ms | 1.804 s | 0 | 0 ms | 754 ms |
| Website mobile · después | 2 ms | 754 ms | 1.804 s | 0 | 0 ms | 754 ms |
| Backoffice desktop · antes | 41 ms | 212 ms | 412 ms | 0.0102 | 0 ms | 212 ms |
| Backoffice desktop · después | 42 ms | 212 ms | 533 ms | 0.0102 | 0 ms | 212 ms |

Las pequeñas diferencias de TTFB/FCP/LCP son variación normal de una prueba de
laboratorio local. El LCP del backoffice aumentó 121 ms en la segunda corrida,
pero sigue en 0,533 s, Performance conserva 100 y CLS/TBT no empeoraron. No se
afirma una mejora de velocidad que los datos no demuestran; la mejora probada
está en calidad, accesibilidad y eliminación de peticiones fallidas.

INP no se informa porque estas navegaciones no ejecutaron una interacción
representativa. TBT 0 ms indica que Lighthouse no detectó bloqueo del hilo
principal durante la carga, pero no se presenta como sustituto de INP.

## Correcciones aplicadas

### 1. Icono de aplicación en website

- Commit: `a905ad6`.
- Archivo: `uis/website/src/app/icon.svg`.
- Efecto causal: elimina `GET /favicon.ico → 404` y el error de consola que
  hacía fallar `errors-in-console`.
- Confirmación aislada: Best Practices **96 → 100**.

### 2. Icono de aplicación en backoffice

- Commit: `5096eff`.
- Archivo: `uis/backoffice/src/app/icon.svg`.
- Efecto causal: elimina el mismo 404 en el puerto del backoffice.
- Confirmación aislada: Best Practices **96 → 100**.

### 3. Contraste dirigido en backoffice

- Commit: `967bd41`.
- Archivos: layout y descripción/ranking de `Dashboard`.
- Cambio: `slate-500 → slate-400` sobre el sidebar oscuro y
  `slate-500 → slate-600` sobre fondos claros.
- Efecto causal: los cinco nodos que fallaban pasan el mínimo 4.5:1.
- Confirmación aislada: Accessibility **96 → 100**.

### 4. Primitivas reutilizables de formulario

- Commit: `82b8234`.
- Archivo nuevo: `components/forms/FormPrimitives.tsx`.
- Integración: `AddCandidateForm` y `AddSupplierForm` consumen el mismo
  `FormField`, `FormErrorList` y `formInputClass`.
- Efecto: elimina dos implementaciones duplicadas de etiqueta/campo y dos
  alertas duplicadas, manteniendo `role="alert"` en una fuente única.
- Verificación: build y tipos limpios; en navegador, el alta de candidato
  siguió mostrando la validación de salario como lista accesible con su CTA.

## Evidencia

- `audit/before/`: tres informes HTML, tres JSON y tres capturas de la línea
  base.
- `audit/after/`: tres informes HTML, tres JSON y tres capturas posteriores.
- Los JSON conservan los valores numéricos sin redondear y permiten revisar los
  audits individuales; las capturas demuestran las puntuaciones visibles.

## Mayor impacto y trabajo futuro

Los iconos produjeron el mayor impacto transversal: una corrección mínima
eliminó el único fallo de Best Practices en ambas aplicaciones. El cambio de
contraste fue el mayor impacto específico del backoffice y resolvió un problema
real de lectura, no una optimización cosmética.

El CSS bloqueante estimado (130 ms en website mobile) y los 11 KiB de
JavaScript legado permanecen como observaciones de baja prioridad. Con LCP
1,804 s, CLS 0, TBT 0 y Performance 100, intentar eliminarlos exigiría cambios
de toolchain desproporcionados y contrarios al alcance dirigido de la rúbrica.
