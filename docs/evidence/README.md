# Evidencia del analizador de incidentes

Comando reproducido el 17/08/2026:

```bash
printf 'n\n' | uv run --project services/api python scripts/analyze.py data/incidents-nexova.csv
```

- `incident-analysis-console.txt` conserva la transcripción exacta de una ejecución con código de salida 0.
- `incident-analysis-console.jpg` es esa misma transcripción renderizada para la evidencia visual requerida. No se presenta como captura nativa de Terminal, porque el entorno bloqueó el control de esa aplicación.
- `incident-analysis-dashboard.jpg` procede de la aplicación local real tras autenticar, procesar el CSV de 100 filas y recuperar el último resumen agregado.

Ningún artefacto contiene filas individuales, direcciones de email ni descripciones de clientes.
