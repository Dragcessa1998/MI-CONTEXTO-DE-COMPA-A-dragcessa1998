# Cómo ejecutar el proyecto (Hito 1 — Web)

Sitio web público de **Nexova**: landing page + formulario de registro de talento con validación en JavaScript. HTML5 semántico, Tailwind CSS compilado, Schema.org, responsive y accesible.

## Ejecutar en local / Codespaces

Desde la raíz del repositorio:

```bash
npx http-server . -p 3000 -a 0.0.0.0
```

Luego abre `http://localhost:3000` (en Codespaces, usa el puerto reenviado que aparece en la pestaña **Ports**).

> Alternativa sin Node: `python3 -m http.server 3000`

El archivo `styles.css` ya está generado y no hace falta compilar nada para ejecutar o entregar la web.

## Regenerar Tailwind CSS

Solo es necesario después de modificar las clases de `index.html` o `application.html`:

```bash
npx tailwindcss@3.4.17 -c tailwind.config.cjs -i styles.input.css -o styles.css --minify
```

El CSS compilado evita cargar Tailwind Play CDN en producción y mejora el rendimiento medido por PageSpeed.

## Publicar en GitHub Pages

El repositorio incluye `.github/workflows/pages.yml`. Al subir estos cambios a `main`:

1. En GitHub, abre **Settings → Pages**.
2. En **Build and deployment → Source**, selecciona **GitHub Actions**.
3. Ejecuta el workflow **Deploy Hito 1 to GitHub Pages**, o vuelve a hacer push a `main`.
4. Comprueba la URL `https://4geeksacademy.github.io/MI-CONTEXTO-DE-COMPA-A-dragcessa1998/`.
5. Analiza esa URL en `https://pagespeed.web.dev/` y adjunta a la entrega una captura con puntuación igual o superior a 80.

## Estructura

```
/
├── index.html        # Landing page (hero, servicios, por qué Nexova, contacto)
├── application.html  # Formulario de registro de talento
├── validation.js     # Validación del formulario (tiempo real + envío simulado)
├── styles.css         # Tailwind compilado y minificado (archivo servido)
├── styles.input.css   # Fuente del CSS
├── tailwind.config.cjs # Configuración y archivos analizados por Tailwind
└── CONTEXT.md        # Contexto de empresa del Hito 1 (datos, campos y validaciones)
```

## Qué probar

- Redimensiona la ventana (móvil / tablet / escritorio): el diseño es responsive *mobile-first*.
- En `application.html`, envía el formulario vacío: deben aparecer mensajes de error específicos por campo.
- Comprueba el contador de caracteres de *Comentarios* (máx. 500) y el botón **Limpiar formulario**.
- Con todos los campos válidos, al enviar aparece el mensaje de éxito (envío simulado, sin backend).
