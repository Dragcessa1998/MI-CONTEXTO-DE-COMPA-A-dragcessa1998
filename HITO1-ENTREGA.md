# Hito 1 — Guía de entrega

## Evidencias incluidas

- `index.html`: HTML5 semántico con header, navegación, hero, tres secciones, CTA, footer con contacto y Schema.org `Organization`.
- `application.html`: formulario responsive organizado con `fieldset` y `legend`, tipos de entrada apropiados, etiquetas asociadas con `for` y campos obligatorios con `required`.
- `validation.js`: validación en tiempo real, mensajes específicos, bloqueo del envío inválido, foco en el primer error, confirmación de éxito y limpieza completa.
- `styles.css`: Tailwind CSS compilado y minificado, sin Tailwind Play CDN en producción.
- `.github/workflows/pages.yml`: despliegue automático de los archivos del Hito 1 en GitHub Pages.
- `robots.txt`, `sitemap.xml`, canonical, Open Graph y favicon: SEO técnico básico para la URL pública.

## Comprobaciones realizadas

- HTML validado sin errores mediante `html-validate`.
- JavaScript validado sintácticamente mediante `node --check`.
- JSON-LD analizado correctamente como JSON.
- Diseño comprobado sin desbordamiento horizontal en 390 px, 768 px y 1440 px.
- Menú móvil comprobado al abrir, cerrar y pulsar Escape.
- Formulario vacío: nueve mensajes específicos y foco en el primer campo inválido.
- Formulario válido: mensaje de éxito visible y enfocado.
- Botón de limpieza: valores, contador y errores restablecidos.
- Consola del navegador: sin errores ni advertencias del proyecto.

## Último paso obligatorio en GitHub

1. Sube el contenido a la rama `main` del repositorio.
2. Abre **Settings → Pages** y selecciona **GitHub Actions** como fuente.
3. Ejecuta **Deploy Hito 1 to GitHub Pages** si no se inicia automáticamente.
4. Verifica `https://4geeksacademy.github.io/MI-CONTEXTO-DE-COMPA-A-dragcessa1998/`.
5. Ejecuta PageSpeed Insights sobre esa URL y guarda una captura con puntuación de rendimiento igual o superior a 80.

La puntuación de PageSpeed solo puede obtenerse después de publicar la URL; no se puede acreditar desde un ZIP local.
