# Nexova — Supplier Directory API (Lightweight Storage)

Registro oficial y único de los **proveedores externos** de Nexova (job boards, ATS,
formación, nóminas, oficinas…), en sustitución de la hoja de cálculo que Patricia Solís
(HR Manager) compartía por email. Proyecto del syllabus **"Supplier Directory — Lightweight
Storage API"**, solicitado por el CTO Sergio Molina.

**Stack:** FastAPI + TinyDB + Pydantic, gestionado con [`uv`](https://docs.astral.sh/uv/).
El modelo, las categorías, los estados y los datos del seeder replican **exactamente**
[CONTEXT.md](CONTEXT.md) (CONTEXT-nexova · supplier-directory).

## Ejecutar

```bash
cd services/api
uv run seed                          # carga inicial (idempotente, confirma el conteo)
uv run uvicorn main:app --port 8000  # API + Swagger UI en http://localhost:8000/docs
uv run --group dev pytest -q         # pruebas de aceptación en TinyDB aislada
```

> `uv` instala Python y las dependencias automáticamente la primera vez.

### Solución de problemas (macOS)

Si `uv run seed` falla con `ModuleNotFoundError: No module named 'seed'`: en carpetas
sincronizadas (iCloud/Desktop), macOS puede marcar los archivos del venv con el flag
`hidden` y Python ignora los `.pth` ocultos. Arréglalo con:

```bash
chflags -R nohidden .venv && uv run seed
# alternativa que no depende del venv editable:
uv run python seed.py
```

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | `/suppliers` | Alta de proveedor (422 si la entrada es inválida) |
| GET | `/suppliers?country=&category=` | Lista; filtra por país y/o categoría |
| GET | `/suppliers/{id}` | Detalle por ID (404 si no existe) |
| PATCH | `/suppliers/{id}/rate` | Actualiza la tarifa (>0) y registra `rate_updated_at` |
| PATCH | `/suppliers/{id}/status` | Activa/suspende (solo `active`/`suspended`) |
| DELETE | `/suppliers/{id}` | Elimina (404 si no existe) |
| GET | `/health` | Estado del servicio |

### Validaciones (Pydantic → 422 antes de tocar TinyDB)

- `status` solo `active` / `suspended` · `monthly_rate` > 0 · `categories` ⊆ lista válida (mín. 1).
- **Moneda por país** (restricción del CONTEXT): `Spain → EUR`, `USA → USD`; combinaciones inconsistentes se rechazan.
- `rate_updated_at` lo **genera el sistema** (no se acepta del cliente): modelos de entrada (`SupplierIn`) y respuesta (`SupplierOut`) separados; los campos desconocidos también producen `422`.

### Ejemplos

```bash
curl "localhost:8000/suppliers?country=Spain"
curl "localhost:8000/suppliers?category=ats_software"
curl -X PATCH localhost:8000/suppliers/4/rate -H 'Content-Type: application/json' -d '{"monthly_rate": 325.0}'
curl -X PATCH localhost:8000/suppliers/5/status -H 'Content-Type: application/json' -d '{"status": "active"}'
```

## Estructura (la que pide la rúbrica)

```text
services/api/
  main.py           ← aplicación FastAPI (+ CORS para uis/backoffice)
  models.py         ← modelos Pydantic (SupplierIn/Out, RateUpdate, StatusUpdate)
  database.py       ← inicialización de TinyDB (persistencia en suppliers.db.json)
  routes/
    suppliers.py    ← endpoints del directorio
  seed.py           ← carga inicial (uv run seed)
```

El frontend está en `uis/backoffice` → página **/suppliers** (tabla, filtros por país y
categoría sin recargar, alta con errores 422 inline, edición de tarifa, activar/suspender
con badge de color y aviso de renovaciones en <60 días).
