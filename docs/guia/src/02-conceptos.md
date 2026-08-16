# Capítulo 2. Conceptos esenciales que necesitarás

Antes de abrir el código de Nexova conviene poner cimientos. El proyecto mezcla muchas piezas: páginas web, un motor de cálculo en TypeScript, dos servidores de tipos distintos y una base de datos guardada en un archivo de texto. Si entiendes cada ladrillo por separado, el edificio completo dejará de parecer intimidante. En este capítulo no vas a programar nada del proyecto todavía; vas a aprender el vocabulario y las ideas que se repetirán en cada hito (cada entrega o etapa del proyecto). Cada tecnología viene con un ejemplo mínimo para que la veas funcionar en tu cabeza.

En este capítulo aprenderás:

- Qué hacen HTML, CSS y JavaScript, los tres lenguajes con los que vive cualquier página web.
- Por qué TypeScript añade tipos a JavaScript y en qué te ayuda eso.
- Qué son React y Next.js, qué significa «renderizar» y qué es un componente.
- Para qué sirven Node.js y npm en el día a día.
- Cómo se construye un backend con Python, FastAPI, Pydantic y TinyDB.
- Qué es una API REST, sus métodos HTTP y sus códigos de estado.
- Qué son JSON y CORS, y por qué a veces el navegador bloquea peticiones.
- Las bases de Git y GitHub: commit, push, ramas, fork y Pull Request.

## La web: HTML, CSS y JavaScript

Toda página web se apoya en tres lenguajes complementarios. **HTML** (HyperText Markup Language, lenguaje de marcado de hipertexto) define la *estructura*: qué es un título, qué es un párrafo, dónde hay un botón. **CSS** (Cascading Style Sheets, hojas de estilo en cascada) define la *apariencia*: colores, tamaños, espaciado. Y **JavaScript** define el *comportamiento*: qué ocurre cuando el usuario hace clic o escribe.

En Nexova esta tríada aparece tal cual en el Hito 1, la web pública estática. El archivo `index.html` es la página de bienvenida (landing) y `application.html` es el formulario para que un candidato se postule. Un fragmento de HTML mínimo se lee así:

```html
<button id="submit" aria-label="Enviar candidatura">Enviar</button>
```

El atributo `aria-label` es parte de la *accesibilidad*: ayuda a que los lectores de pantalla describan el botón a personas con discapacidad visual. El HTML real de Nexova usa muchos atributos `aria-*` y roles como `role="alert"` por esa razón.

El JavaScript del Hito 2 vive en `validation.js` y reacciona cuando la página termina de cargar:

```js
document.addEventListener('DOMContentLoaded', function () {
  // aquí se valida el formulario antes de enviarlo
});
```

::: {.callout .note}
**Nota:** «estático» significa que esas páginas no necesitan un servidor que genere contenido al vuelo; son archivos que el navegador descarga y muestra tal cual. Más adelante, en el Hito 4, esa misma web se reescribe con componentes de React.
:::

## TypeScript: JavaScript con tipos

JavaScript es flexible, pero esa flexibilidad esconde errores. Si una función espera un número y le pasas un texto, JavaScript no se queja hasta que el programa explota en producción. **TypeScript** es JavaScript al que se le añaden *tipos*: etiquetas que declaran qué clase de dato es cada cosa (un número, un texto, una lista). El editor avisa del error mientras escribes, antes de ejecutar nada.

En Nexova, toda la lógica de negocio del Hito 2 está en TypeScript, dentro de `src/`. Por ejemplo, `src/types/models.ts` describe cómo es un candidato:

```ts
export interface ScoredCandidate {
  candidate: Candidate;
  score: number;
}
```

Una `interface` es un molde: dice que un `ScoredCandidate` siempre tiene un `candidate` y un `score` numérico. Si alguien intenta poner un texto en `score`, TypeScript lo marca en rojo. El proyecto activa el modo más estricto posible con `"strict": true` en `tsconfig.json`, así que no perdona descuidos.

::: {.callout .tip}
**Tip:** piensa en los tipos como un contrato. Cuando el contrato es claro, refactorizar (reescribir código sin romperlo) deja de dar miedo, porque el compilador te dice exactamente qué dejó de encajar.
:::

## React y Next.js: componentes y renderizado

**React** es una biblioteca para construir interfaces a base de *componentes*: piezas reutilizables que combinan estructura y comportamiento. En lugar de escribir una página gigante, escribes un componente «Botón», uno «Tarjeta», uno «Formulario», y los ensamblas. *Renderizar* significa convertir esos componentes en el HTML que el navegador finalmente muestra.

**Next.js** es un framework construido sobre React que añade lo que falta para una aplicación real: enrutado de páginas, optimizaciones y renderizado en el servidor. Nexova usa Next.js 16 con el **App Router**, su sistema moderno de rutas donde cada carpeta dentro de `app/` es una URL. En el backoffice, la carpeta `suppliers/page.tsx` se convierte automáticamente en la ruta `/suppliers`.

Un componente mínimo de React se escribe en un archivo `.tsx` (TypeScript + marcado) así:

```tsx
export default function Saludo({ nombre }: { nombre: string }) {
  return <p>Hola, {nombre}</p>;
}
```

El proyecto tiene tres aplicaciones Next.js en la carpeta `uis/`: `website` (la web pública), `backoffice` (el panel interno) y `talent-pipeline-tracker` (el seguimiento del pipeline de candidatos). Todas usan React 18 y Tailwind, una forma de escribir CSS con clases predefinidas.

## Node.js y npm

JavaScript nació para vivir dentro del navegador. **Node.js** es lo que le permite ejecutarse *fuera* de él: en tu ordenador o en un servidor. Gracias a Node.js puedes correr herramientas de desarrollo y servidores escritos en JavaScript o TypeScript.

**npm** (Node Package Manager) es el gestor de paquetes que viene con Node.js. Sirve para dos cosas: instalar dependencias (bibliotecas de terceros) y ejecutar comandos definidos en el archivo `package.json`. En la raíz de Nexova, ese archivo define atajos como estos:

```json
"scripts": {
  "typecheck": "tsc --noEmit",
  "demo": "tsx src/demo.ts"
}
```

Con `npm run typecheck` se comprueban los tipos sin generar archivos, y con `npm run demo` se ejecuta una demostración de la lógica de scoring. Cada aplicación de `uis/` se arranca con `npm install` y luego `npm run dev`.

## Python y FastAPI: el backend

El otro gran lenguaje del proyecto es **Python**, conocido por su sintaxis legible. El backend principal de proveedores, en `services/api`, está escrito en Python con **FastAPI**, un framework para crear APIs web rápidas y bien documentadas. FastAPI genera por sí sola una documentación interactiva (Swagger) accesible en la ruta `/docs`.

Definir un punto final (endpoint, una dirección a la que el cliente hace peticiones) en FastAPI es tan directo como esto, sacado de `services/api/routes/suppliers.py`:

```python
@router.post("", status_code=201, response_model=SupplierOut)
def create_supplier(payload: SupplierIn) -> SupplierOut:
    ...
```

El decorador `@router.post(...)` declara que esa función responde a peticiones POST y que, si todo va bien, devuelve el código 201. En Nexova este servidor se gestiona con **uv**, una herramienta moderna que instala dependencias y ejecuta el proyecto. Se levanta con `uv run uvicorn main:app --port 8000`.

## Pydantic: validación de datos

Un backend nunca debe confiar en lo que le envían. **Pydantic** es la biblioteca que FastAPI usa para *validar* datos: comprueba que cada campo tiene el tipo y el valor correctos antes de procesarlos. Si algo no cumple, rechaza la petición automáticamente.

En `services/api/models.py`, el modelo de entrada de un proveedor impone reglas estrictas:

```python
class SupplierIn(BaseModel):
    name: str = Field(min_length=1)
    country: Literal["Spain", "USA"]
    monthly_rate: float = Field(gt=0, allow_inf_nan=False)
    currency: Literal["EUR", "USD"]
```

Aquí `gt=0` exige que la tarifa mensual sea mayor que cero y `Literal[...]` limita el país a dos valores. El proyecto incluso liga país y moneda con una regla de negocio: un proveedor de «Spain» debe usar «EUR», y uno de «USA», «USD». Cualquier entrada inválida se rechaza con un código 422, que verás más abajo.

::: {.callout .important}
**Importante:** validar en el servidor no es opcional. Aunque el formulario del frontend ya compruebe los datos, un atacante puede saltarse el navegador y enviar lo que quiera. Pydantic es la última línea de defensa antes de tocar la base de datos.
:::

## TinyDB: una base de datos en un archivo JSON

Una base de datos guarda información de forma persistente. **TinyDB** es la más sencilla posible: almacena todo en un único archivo de texto con formato JSON, sin necesidad de instalar un servidor de base de datos. Es ideal para prototipos y proyectos de aprendizaje.

En `services/api/database.py`, Nexova la configura para escribir en un archivo llamado `suppliers.db.json` junto al código:

```python
DB_PATH = Path(__file__).resolve().parent / "suppliers.db.json"
_db = TinyDB(DB_PATH, indent=2, ensure_ascii=False)
```

Los datos sobreviven a los reinicios del servidor porque quedan grabados en disco. El comando `uv run seed` rellena la base con 15 proveedores de ejemplo de forma idempotente (puedes ejecutarlo varias veces sin duplicar nada).

## REST, métodos HTTP y códigos de estado

**REST** (REpresentational State Transfer) es un estilo para diseñar APIs en el que cada recurso (un proveedor, un candidato) tiene su propia URL, y las operaciones se expresan con *métodos HTTP*. HTTP es el protocolo de la web; cada petición usa un verbo que indica la intención.

| Método | Intención | Ejemplo en Nexova |
| --- | --- | --- |
| GET | Leer datos sin modificarlos | `GET /suppliers` lista proveedores |
| POST | Crear un recurso nuevo | `POST /suppliers` registra un proveedor |
| PUT | Reemplazar un recurso completo | `PUT /records/:id` en el tracker |
| PATCH | Modificar parte de un recurso | `PATCH /suppliers/{id}/rate` cambia la tarifa |
| DELETE | Eliminar un recurso | `DELETE /suppliers/{id}` lo borra |

El servidor responde a cada petición con un *código de estado*: un número de tres cifras que resume qué pasó. Estos son los que más verás en el proyecto:

| Código | Significado | Cuándo aparece |
| --- | --- | --- |
| 200 | OK | Lectura o actualización correcta |
| 201 | Creado | Tras un POST que registra un recurso |
| 400 | Petición incorrecta | Datos mal formados |
| 404 | No encontrado | El ID solicitado no existe |
| 422 | Entidad no procesable | Pydantic rechaza la validación |

En Nexova estos códigos no son teoría: la función `_get_or_404` lanza un 404 cuando un proveedor no existe, y la API rechaza con 422 cualquier dato que no pase la validación.

## JSON: el idioma común

**JSON** (JavaScript Object Notation) es el formato de texto con el que el frontend y el backend se intercambian datos. Es legible para humanos y fácil de procesar para las máquinas. Un proveedor viaja por la red más o menos así:

```json
{
  "name": "LinkedIn Recruiter",
  "country": "Spain",
  "currency": "EUR",
  "monthly_rate": 850.0,
  "status": "active"
}
```

TinyDB usa JSON para guardar en disco, las APIs lo usan para responder y la web pública del Hito 1 incluye además datos estructurados de Schema.org en formato JSON-LD para que los buscadores entiendan mejor la página.

## CORS: por qué a veces el navegador bloquea

Cuando una página servida en una dirección intenta pedir datos a otra dirección distinta, el navegador lo bloquea por seguridad, salvo que el servidor lo autorice. **CORS** (Cross-Origin Resource Sharing, intercambio de recursos entre orígenes) es el mecanismo de esa autorización.

En desarrollo, backoffice y Talent API pueden usar orígenes distintos. Por eso `services/talent-api/src/security.ts` compara el origen con una allowlist y sólo autoriza el *preflight* que el navegador envía con el método OPTIONS:

```ts
res.header("Access-Control-Allow-Origin", origin);
res.header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS");
if (req.method === "OPTIONS") return res.sendStatus(204);
```

::: {.callout .warning}
**Aviso:** nunca sustituyas la allowlist por `*`. Si una llamada falla con un error de CORS, comprueba el origen configurado y las cabeceras del backend.
:::

## Git y GitHub: control de versiones

**Git** es un sistema de control de versiones: registra la historia de tu código y te permite volver atrás, comparar cambios y trabajar en paralelo. **GitHub** es la plataforma en la nube donde se alojan esos repositorios (proyectos versionados) y donde se colabora.

Los conceptos básicos que usarás en Nexova:

- **commit**: una fotografía guardada de tus cambios, con un mensaje que explica qué hiciste.
- **push**: subir tus commits al repositorio remoto en GitHub.
- **rama** (branch): una línea de trabajo paralela. En el proyecto hay una rama por cada hito, que luego se unifican en `main`.
- **fork**: una copia personal de un repositorio ajeno. La entrega de Nexova se hace sobre un fork privado del repositorio de 4Geeks.
- **Pull Request**: una solicitud para integrar los cambios de una rama en otra, que sirve además como punto de revisión. La entrega final se realiza por Pull Request en la plataforma 4Geeks.

Un flujo típico se resume en tres comandos:

```bash
git checkout -b hito-2     # crea y entra en una rama nueva
git commit -m "Motor de scoring"  # guarda los cambios
git push origin hito-2     # los sube a GitHub
```

::: {.callout .tip}
**Tip:** haz commits pequeños y con mensajes claros. Tu yo del futuro (y quien revise tu Pull Request) agradecerá poder leer la historia del proyecto como un relato y no como un único cambio gigante.
:::

## Resumen

- La web vive de tres lenguajes: HTML para la estructura, CSS para el estilo y JavaScript para el comportamiento; Nexova los usa en el Hito 1 con accesibilidad cuidada.
- TypeScript añade tipos a JavaScript para cazar errores antes de ejecutar, y es la base de la lógica compartida en `src/`.
- React aporta componentes reutilizables y Next.js los convierte en aplicaciones con rutas; el proyecto tiene tres apps en `uis/`.
- El backend se construye con Python y FastAPI, valida con Pydantic y persiste con TinyDB en un archivo JSON.
- Una API REST se maneja con métodos HTTP (GET, POST, PUT, PATCH, DELETE) y responde con códigos de estado (200, 201, 400, 404, 422); JSON es el formato de intercambio y CORS la autorización entre orígenes.
- Git y GitHub registran la historia del código mediante commits, ramas, fork y Pull Request, que es como se entrega el proyecto.
