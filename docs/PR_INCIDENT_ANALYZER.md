## Qué entrega este PR

- CLI `scripts/analyze.py` con ruta CSV, validación contextual, resumen legible y exportación opcional; `analyze.py` conserva compatibilidad.
- Una única lógica compartida por CLI y API, sin conservar ni mostrar emails o filas individuales.
- `POST /api/incidents/analyze`, `GET /api/incidents/results/latest` y exportación CSV autenticados.
- Página `/incident-analysis` con carga, resumen, inválidos, satisfacción, descarga y recuperación tras recarga.
- Next.js 16.3.1/PostCSS 8.5.26 y auditoría npm sin vulnerabilidades conocidas.

## Resultado exacto del CONTEXT

- 100 filas: 96 válidas y 4 inválidas.
- Categorías: 28/18/21/17/12.
- Estados: 27/56/13.
- Satisfacción: 56 tickets puntuados; media 3,84/5.
- Cero emails o descripciones en consola, JSON, CSV exportado o capturas.

## Evidencia visual

![Salida real de analyze.py](https://raw.githubusercontent.com/Dragcessa1998/MI-CONTEXTO-DE-COMPA-A-dragcessa1998/project/25-incident-analyzer/docs/evidence/incident-analysis-console.jpg)

La imagen anterior renderiza la transcripción exacta de una ejecución local con exit code 0; no se presenta como captura nativa de Terminal porque el entorno bloqueó el control de esa aplicación. La transcripción está en `docs/evidence/incident-analysis-console.txt`.

![Panel con el CSV cargado](https://raw.githubusercontent.com/Dragcessa1998/MI-CONTEXTO-DE-COMPA-A-dragcessa1998/project/25-incident-analyzer/docs/evidence/incident-analysis-dashboard.jpg)

## Verificación

```bash
uv run --project services/api --group dev pytest -q
printf 'n\n' | uv run --project services/api python scripts/analyze.py data/incidents-nexova.csv
npm run build --prefix uis/backoffice
npm audit --prefix uis/backoffice --audit-level=low
```

Resultado: **46 passed**, CLI con exit code 0, build Next de 6 rutas y **0 vulnerabilidades npm**.
