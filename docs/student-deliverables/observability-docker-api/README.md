# Observability Docker API

Small production-style FastAPI service demonstrating the container and telemetry
patterns used in the course: health/readiness endpoints, structured request timing,
Prometheus metrics, Docker image, and Compose health checks.

## Local run

```bash
uv sync
uv run pytest -q
uv run uvicorn app.main:app --port 8000
```

Then open `/health`, `/ready`, and `/metrics`.

## Container run

```bash
docker compose up --build
```

The image runs as a non-root user and exposes port 8000. `docker-compose.yml` waits
for `/ready` before considering the service healthy.
