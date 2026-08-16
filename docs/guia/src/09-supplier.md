# Capítulo 9. Supplier Directory: una API con FastAPI, TinyDB y Pydantic

Hasta ahora has trabajado el frontend (la web pública, el backoffice, el seguimiento de candidatos) y un backend escrito en TypeScript con Express (la talent-api). En este capítulo cambias de ecosistema: vas a construir un servicio en **Python** que cumple el proyecto oficial del syllabus, la *Lightweight Storage API* (API de almacenamiento ligero). Su misión de negocio es concreta y muy real: sustituir la hoja de cálculo que Patricia Solís, la HR Manager de Nexova, actualiza a mano y comparte por correo cada vez que cambia el coste de un proveedor. El resultado de esa hoja eran varias versiones circulando en paralelo sin que nadie supiera cuál era la vigente. Este servicio crea el registro oficial y único de proveedores: una sola fuente de verdad accesible por HTTP.

El código vive en `services/api/` y se apoya en tres piezas que vas a conocer a fondo: **FastAPI** (el framework web), **Pydantic v2** (la capa de validación de datos) y **TinyDB** (una base de datos que persiste en un archivo JSON). Todo el servicio se gestiona con **uv**, un gestor de proyectos y entornos de Python moderno y rápido.

En este capítulo aprenderás:

- Qué es FastAPI y por qué encaja tan bien con la validación automática de datos.
- Cómo Pydantic v2 modela la entrada (`SupplierIn`) y la salida (`SupplierOut`), y cómo `Field`, `field_validator` y `model_validator` blindan las reglas de negocio.
- Las reglas de negocio del directorio: moneda por país, fechas reales, tarifas finitas y mayores que cero, y categorías válidas.
- Cómo TinyDB guarda los datos en `suppliers.db.json` y por qué eso es suficiente para este proyecto.
- Los puntos finales (endpoints) de la API: `POST`, `GET` con filtros, `GET/{id}`, `PATCH` de tarifa y de estado, y `DELETE`.
- Cómo se convierte un error de validación en una respuesta HTTP 422 consistente, incluso ante `Infinity` o `NaN`.
- Cómo se carga el seed de 15 proveedores de forma idempotente y cómo arrancar todo con uv.
- Cómo el backoffice consume esta API desde la ruta `/suppliers`.

## Qué es FastAPI y por qué se eligió

Un *framework web* es una librería que te da la estructura para recibir peticiones HTTP y devolver respuestas sin reinventar el protocolo. **FastAPI** es uno de los frameworks de Python más populares para construir APIs. Sus dos grandes ventajas son: primero, usa las *anotaciones de tipo* de Python (los `: tipo` que escribes junto a cada parámetro) para validar automáticamente lo que entra; y segundo, genera documentación interactiva sola, sin que tengas que escribirla.

Esa documentación interactiva se llama **Swagger UI** y queda publicada en la ruta `/docs`. Es una página donde ves cada endpoint, sus parámetros y puedes probarlos desde el navegador. Para un proyecto que reemplaza una hoja de cálculo compartida, tener `/docs` significa que cualquiera del equipo de Nexova puede entender y probar la API sin leer el código.

El punto de entrada del servicio es `services/api/main.py`, donde se crea la aplicación:

```python
app = FastAPI(
    title="Nexova — Supplier Directory API",
    description="Directorio de proveedores: fuente única de verdad accesible vía API.",
    version="1.0.0",
)
```

Justo debajo se instala la configuración web defensiva, incluido **CORS** (Cross-Origin Resource Sharing, intercambio de recursos entre orígenes). Un navegador bloquea por defecto que una página de un origen llame a otro origen distinto. Nexova sólo autoriza los orígenes declarados en `CORS_ALLOWED_ORIGINS` y rechaza una configuración vacía o con comodín:

```python
from app_security import install_security_middleware

install_security_middleware(app)
```

La misma instalación añade hosts de confianza y cabeceras defensivas. Por último, `main.py` registra el *router* con todos los endpoints de proveedores (`app.include_router(suppliers_router)`) y expone un endpoint de salud, `GET /health`, que devuelve el estado y cuántos proveedores hay almacenados. Un endpoint de salud es una práctica habitual: permite comprobar de un vistazo que el servicio está vivo.

::: {.callout .note}
**Nota:** un *router* en FastAPI es simplemente un grupo de rutas que se montan juntas bajo un prefijo común. En este proyecto, todas las rutas de proveedores viven en `routes/suppliers.py` bajo el prefijo `/suppliers`, y `main.py` las "incluye". Así el archivo principal queda corto y la lógica de cada recurso queda separada.
:::

## Pydantic v2: modelar y validar los datos

**Pydantic** es la librería que define cómo deben ser los datos y los valida automáticamente. Trabaja con *modelos*: clases que heredan de `BaseModel` y describen, campo a campo, qué tipo y qué restricciones tiene cada dato. FastAPI y Pydantic están integrados: cuando declaras que un endpoint recibe un `SupplierIn`, FastAPI usa Pydantic para validar el cuerpo de la petición antes de que tu código se ejecute. Si algo no cumple, FastAPI responde con un error 422 y tu función ni siquiera llega a correr.

Los modelos están en `services/api/models.py`. El más importante es `SupplierIn`, el modelo de **entrada**: describe lo que el cliente puede enviar al dar de alta un proveedor.

```python
class SupplierIn(BaseModel):
    name: str = Field(min_length=1, description="Nombre comercial del proveedor o plataforma")
    country: Literal["Spain", "USA"] = Field(description='País del contrato activo: "Spain" o "USA"')
    categories: list[str] = Field(min_length=1, description="Tipo de servicio que provee (ver lista válida)")
    monthly_rate: float = Field(gt=0, allow_inf_nan=False, description="Coste mensual vigente en la moneda del contrato")
    currency: Literal["EUR", "USD"] = Field(description='"EUR" para Spain, "USD" para USA')
    status: SupplierStatus
    contract_renewal_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Fecha de renovación del contrato (formato YYYY-MM-DD)",
    )
    contact_email: str | None = Field(default=None, description="Email del account manager del proveedor")
    notes: str | None = Field(default=None, description="Observaciones internas")
```

Observa el detalle. `Field` es la función con la que añades restricciones a un campo más allá de su tipo. Aquí `min_length=1` exige que `name` no sea una cadena vacía; `gt=0` (greater than, mayor que) exige que `monthly_rate` sea positivo; `pattern` aplica una *expresión regular* (un patrón de texto) que obliga a que la fecha tenga la forma `YYYY-MM-DD`. El tipo `Literal["Spain", "USA"]` es muy expresivo: significa que `country` solo puede ser exactamente una de esas dos cadenas; cualquier otra cosa es un 422 automático. Los campos con `| None` y `default=None` son opcionales.

### El modelo de salida hereda del de entrada

El modelo de **salida**, `SupplierOut`, es lo que la API devuelve. Hereda de `SupplierIn` y le añade dos campos que el sistema genera, no el cliente:

```python
class SupplierOut(SupplierIn):
    id: int
    rate_updated_at: datetime
```

Esta separación entrada/salida es una decisión de diseño deliberada y muy buena. El `id` lo asigna la base de datos; `rate_updated_at` (el momento de la última actualización de tarifa) lo pone el servidor. Como `SupplierIn` no los incluye, un cliente no puede falsificarlos: aunque los mande en el cuerpo, Pydantic los ignora porque no existen en el modelo de entrada. Es la diferencia entre "lo que puedo recibir" y "lo que puedo devolver".

### Validadores de campo: reglas a medida

Cuando una restricción no cabe en un `Field`, Pydantic ofrece los `field_validator`: funciones que validan un campo concreto con tu propia lógica. En `SupplierIn` hay tres.

El primero limpia el nombre y rechaza cadenas que solo tengan espacios (la regex `min_length=1` no detectaría `"   "`):

```python
@field_validator("name")
@classmethod
def name_must_not_be_blank(cls, value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("El nombre no puede estar vacío ni ser solo espacios")
    return value
```

El segundo es sutil, pero importante. La regex del `Field` solo comprueba la **forma** `YYYY-MM-DD`; aceptaría `2025-13-45`, una fecha imposible. Este validador usa `date.fromisoformat` para verificar que la fecha **existe** de verdad:

```python
@field_validator("contract_renewal_date")
@classmethod
def renewal_date_must_be_real(cls, value: str | None) -> str | None:
    if value is not None:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("contract_renewal_date debe ser una fecha real (YYYY-MM-DD)") from exc
    return value
```

El tercero comprueba que todas las categorías enviadas estén en la lista `VALID_CATEGORIES`, una constante con las nueve categorías permitidas (portales de empleo, software ATS, formación, etcétera):

```python
@field_validator("categories")
@classmethod
def categories_must_be_valid(cls, value: list[str]) -> list[str]:
    invalid = [c for c in value if c not in VALID_CATEGORIES]
    if invalid:
        raise ValueError(
            f"Categorías no válidas: {invalid}. Las válidas son: {VALID_CATEGORIES}"
        )
    return value
```

### Validador de modelo: la coherencia país-moneda

Algunas reglas no dependen de un solo campo, sino de la relación entre varios. Para eso está `model_validator(mode="after")`: se ejecuta después de validar todos los campos individuales y tiene acceso al objeto completo. La regla de negocio del CONTEXT es clara: un proveedor de España debe facturar en euros y uno de Estados Unidos en dólares.

```python
@model_validator(mode="after")
def currency_must_match_country(self) -> "SupplierIn":
    expected = "EUR" if self.country == "Spain" else "USD"
    if self.currency != expected:
        raise ValueError(
            f'Un proveedor de "{self.country}" debe tener currency = "{expected}"'
        )
    return self
```

Así, enviar un proveedor `"Spain"` con `currency = "USD"` se rechaza con un 422. Esta es exactamente la clase de inconsistencia que la hoja de cálculo de Patricia no podía evitar.

### Bloquear Infinity y NaN

Hay un detalle de precisión que merece su propio foco. El tipo `float` de un ordenador admite tres valores "raros": `inf` (infinito), `-inf` y `NaN` (Not a Number, "no es un número"). Una tarifa mensual nunca debería ser ninguno de esos. Por eso el `Field` de `monthly_rate` lleva `allow_inf_nan=False`: con ese flag, Pydantic rechaza esos valores no finitos. La misma protección se repite en el modelo `RateUpdate`, el cuerpo del endpoint que actualiza tarifas:

```python
class RateUpdate(BaseModel):
    monthly_rate: float = Field(gt=0, allow_inf_nan=False)
```

::: {.callout .important}
**Dato crítico:** `gt=0` y `allow_inf_nan=False` trabajan juntos. El primero descarta cero y negativos; el segundo descarta `Infinity` y `NaN`. Sin el segundo, alguien podría colar una tarifa "infinita" que rompería cualquier suma de presupuesto aguas abajo.
:::

## TinyDB: una base de datos en un archivo

Para almacenar los proveedores, el proyecto usa **TinyDB**, una base de datos ligera que guarda todo en un único archivo JSON. No necesita un servidor de base de datos aparte ni configuración: es perfecta para un proyecto de "almacenamiento ligero". La inicialización está en `services/api/database.py`:

```python
DB_PATH = Path(__file__).resolve().parent / "suppliers.db.json"

_db: TinyDB | None = None

def get_db() -> TinyDB:
    global _db
    if _db is None:
        _db = TinyDB(DB_PATH, indent=2, ensure_ascii=False)
    return _db

def suppliers_table() -> Table:
    return get_db().table("suppliers")
```

El archivo `suppliers.db.json` se crea junto al código, de modo que los datos sobreviven a los reinicios del servidor (un requisito de la rúbrica). La función `get_db()` aplica un patrón sencillo: crea la instancia de TinyDB la primera vez que se usa y la reutiliza después. TinyDB organiza los registros en *tablas*; aquí solo hay una, `suppliers`. Cada documento guardado recibe un identificador entero automático (`doc_id`), que es lo que la API expone como `id`.

::: {.callout .note}
**Nota:** el propio `database.py` documenta que esto es temporal: "Se migrará a Postgres cuando el ORM esté listo". TinyDB es la decisión correcta para empezar rápido; cuando el volumen crezca, la capa de modelos Pydantic permitirá cambiar el almacenamiento sin tocar los endpoints.
:::

## Los endpoints de la API

Toda la superficie HTTP vive en `services/api/routes/suppliers.py`, bajo el prefijo `/suppliers`. Antes de los endpoints hay tres funciones auxiliares que evitan repetir código: `_now_iso()` devuelve la hora actual en formato ISO; `_to_out()` convierte un documento de TinyDB en un `SupplierOut`; y `_get_or_404()` busca por id y, si no existe, lanza directamente un 404.

```python
def _get_or_404(supplier_id: int) -> Document:
    doc = suppliers_table().get(doc_id=supplier_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return doc
```

Esta tabla resume la superficie completa de la API:

| Método y ruta | Qué hace | Código de éxito |
| --- | --- | --- |
| `POST /suppliers` | Da de alta un proveedor | 201 |
| `GET /suppliers` | Lista, con filtros `?country=` y `?category=` | 200 |
| `GET /suppliers/{id}` | Detalle de un proveedor | 200 (404 si no existe) |
| `PATCH /suppliers/{id}/rate` | Actualiza la tarifa y re-sella `rate_updated_at` | 200 |
| `PATCH /suppliers/{id}/status` | Activa o suspende | 200 |
| `DELETE /suppliers/{id}` | Elimina un proveedor | 200 (404 si no existe) |
| `GET /health` | Estado del servicio | 200 |

### Crear: POST con 201

El alta declara `status_code=201` (el código HTTP de "creado") y `response_model=SupplierOut`. Fíjate en cómo el servidor añade el campo generado:

```python
@router.post("", status_code=201, response_model=SupplierOut)
def create_supplier(payload: SupplierIn) -> SupplierOut:
    record = payload.model_dump()
    record["rate_updated_at"] = _now_iso()  # generado por el sistema, no por el cliente
    doc_id = suppliers_table().insert(record)
    return SupplierOut(id=doc_id, **record)
```

`payload: SupplierIn` es la magia de FastAPI: el cuerpo de la petición ya llega validado. Si no lo estaba, esta función nunca se ejecuta. `model_dump()` convierte el modelo en un diccionario, se le añade el sello de tiempo, se inserta en TinyDB (que devuelve el `doc_id`) y se responde con el objeto completo, ya con su `id`.

### Listar con filtros combinables

El listado acepta dos parámetros de consulta opcionales y los aplica en cadena. Los *query params* son los valores que van tras el `?` en la URL, como `/suppliers?country=Spain&category=ats_software`.

```python
@router.get("", response_model=list[SupplierOut])
def list_suppliers(
    country: str | None = Query(default=None, ...),
    category: str | None = Query(default=None, ...),
) -> list[SupplierOut]:
    docs = suppliers_table().all()
    if country is not None:
        docs = [d for d in docs if d.get("country") == country]
    if category is not None:
        docs = [d for d in docs if category in d.get("categories", [])]
    return [_to_out(d) for d in docs]
```

Sin parámetros devuelve todos los proveedores; los dos filtros se pueden combinar. El filtro de categoría usa `category in d.get("categories", [])` porque un proveedor puede tener varias categorías. Esto resuelve preguntas reales de Patricia como "¿qué herramientas de ATS tenemos?".

### Actualizar la tarifa y re-sellar el tiempo

El endpoint más interesante por la regla de negocio es el `PATCH` de tarifa. La rúbrica exige *trazabilidad*: cada vez que cambia la tarifa, debe quedar registrado **cuándo**, para que Patricia pueda justificar variaciones de presupuesto ante dirección.

```python
@router.patch("/{supplier_id}/rate", response_model=SupplierOut)
def update_rate(supplier_id: int, payload: RateUpdate) -> SupplierOut:
    _get_or_404(supplier_id)
    table = suppliers_table()
    table.update(
        {"monthly_rate": payload.monthly_rate, "rate_updated_at": _now_iso()},
        doc_ids=[supplier_id],
    )
    return _to_out(table.get(doc_id=supplier_id))
```

Cada actualización de `monthly_rate` re-sella `rate_updated_at` con la hora actual, de forma automática y atómica. El cliente no controla ese campo; lo controla el servidor. El `PATCH` de estado es análogo y solo admite `"active"` o `"suspended"` gracias al modelo `StatusUpdate`, que reutiliza el enum `SupplierStatus`. Y el `DELETE` borra por id devolviendo 404 si no existe. Conviene recordar que un proveedor suspendido no se borra: se mantiene con estado `"suspended"` para conservar el historial comercial.

## El error 422 a prueba de Infinity

FastAPI ya devuelve 422 cuando la validación de Pydantic falla. Pero hay un caso límite peligroso: si la entrada contiene `Infinity` o `NaN`, el cuerpo de error que FastAPI intenta serializar contiene esos valores, y el JSON estándar **no** los admite. El resultado sería un 500 (error del servidor) en lugar del 422 esperado. `main.py` instala un manejador propio que sanea esos valores antes de responder:

```python
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    detail = _sanitize_non_finite(jsonable_encoder(exc.errors()))
    return JSONResponse(status_code=422, content={"detail": detail})
```

La función auxiliar `_sanitize_non_finite` recorre recursivamente la estructura del error y convierte cualquier `inf`/`-inf`/`nan` en su representación de texto. Así el 422 siempre es serializable y el contrato de la API se mantiene: una validación inválida significa 422, sin excepciones.

::: {.callout .warning}
**Aviso:** sin este manejador, un cliente malicioso o un error de cálculo que enviara `monthly_rate: Infinity` provocaría un 500 en vez de un 422. Un 500 sugiere "el servidor está roto"; un 422 dice "tu petición es inválida". La diferencia importa para quien depura desde el otro lado.
:::

## El seed idempotente de 15 proveedores

Para que el directorio no arranque vacío, `services/api/seed.py` carga los 15 proveedores que representan el estado actual de la hoja de Patricia (LinkedIn Talent Solutions, InfoJobs, Workable, Greenhouse, HireVue, Regus Valencia, WeWork Miami, etcétera). Lo valioso del seeder es que es **idempotente**: puedes ejecutarlo muchas veces sin crear duplicados.

```python
for raw in SUPPLIERS_SEED:
    supplier = SupplierIn(**raw)  # valida con el mismo modelo de la API
    if table.contains(supplier_query.name == supplier.name):
        skipped += 1
        continue
    record = supplier.model_dump()
    record["rate_updated_at"] = datetime.now(timezone.utc).isoformat()
    table.insert(record)
    inserted += 1
```

Dos detalles de calidad: primero, cada registro pasa por `SupplierIn(**raw)`, el **mismo** modelo que valida la API, así que el seeder nunca inserta datos que la API rechazaría. Segundo, antes de insertar comprueba si ya existe un proveedor con ese nombre; si existe, lo omite. Por eso lanzarlo dos veces deja la base igual.

## Cómo correrlo con uv

El proyecto se gestiona con **uv**, declarado en `services/api/pyproject.toml` con sus dependencias (`fastapi`, `uvicorn`, `tinydb`, `pydantic`) y un script `seed` que apunta a `seed:main`. **Uvicorn** es el servidor que ejecuta la aplicación FastAPI. Los dos comandos clave, desde `services/api/`, son:

```bash
uv run seed                          # carga inicial (idempotente)
uv run uvicorn main:app --port 8000  # API + Swagger en /docs
```

Con el servidor en marcha, abre `http://localhost:8000/docs` para probar cada endpoint desde Swagger UI.

::: {.callout .tip}
**Tip (footgun en macOS):** si el repositorio vive en una carpeta del Escritorio sincronizada con iCloud, el atributo `UF_HIDDEN` sobre `.venv` puede romper `uv run seed` con un `ModuleNotFoundError`. La solución es `chflags -R nohidden .venv` y reintentar, o ejecutar directamente `uv run python seed.py`.
:::

## El frontend del backoffice que la consume

La API no es un fin en sí misma: el panel interno la usa en vivo. La ruta `/suppliers` del backoffice (Next.js, en `:3000`) la consume a través de un cliente tipado en `uis/backoffice/src/lib/suppliers.ts`, que apunta a `NEXT_PUBLIC_SUPPLIERS_API_URL` (por defecto `http://localhost:8000`). Ese cliente define una función por endpoint (`list`, `create`, `updateRate`, `updateStatus`) y traduce el formato de error de FastAPI (`{"detail": [...]}`) en un mensaje legible.

La vista visual está en `uis/backoffice/src/components/SuppliersView.tsx`, montada por `page.tsx`. Ofrece a Patricia exactamente lo que pide el CONTEXT: una tabla con filtros por país y por categoría que se aplican sin recargar la página, edición de tarifa fila a fila, un control para activar o suspender, y un *badge* de aviso cuando la renovación del contrato cae en los próximos 60 días. La función `renewalBadge` calcula esos días y muestra "Renueva en N d" en ámbar o "Vencida" en rojo. El alta se hace desde `AddSupplierForm.tsx`. Un detalle de robustez: la vista usa un contador de secuencia (`loadSeq`) para que, si cambias los filtros rápido, una respuesta lenta y obsoleta no pise a la más reciente.

## Resumen

- El Supplier Directory (`services/api/`) es el proyecto oficial *Lightweight Storage API*: sustituye una hoja de cálculo por un registro único accesible por HTTP, construido con FastAPI, TinyDB y Pydantic v2 y gestionado con uv.
- Pydantic separa entrada (`SupplierIn`) y salida (`SupplierOut`): el cliente nunca fija `id` ni `rate_updated_at`, que genera el sistema; las reglas de negocio se imponen con `Field`, `field_validator` y un `model_validator` que exige Spain→EUR y USA→USD.
- Las validaciones cubren casos reales: nombre no vacío, fechas que existen de verdad (`date.fromisoformat`), categorías de una lista cerrada y tarifas mayores que cero y finitas (`gt=0`, `allow_inf_nan=False`).
- Los endpoints siguen un contrato HTTP limpio (201 al crear, 404 al no encontrar, 422 al validar), con un manejador propio que mantiene el 422 incluso ante `Infinity` o `NaN`; el `PATCH` de tarifa re-sella el momento del cambio para la trazabilidad.
- TinyDB persiste en `suppliers.db.json`, el seeder carga 15 proveedores de forma idempotente, y todo arranca con `uv run seed` y `uv run uvicorn main:app --port 8000`, con Swagger en `/docs`. El backoffice lo consume en vivo desde la ruta `/suppliers`.
