# Async Job API

Standalone FastAPI service that demonstrates offloading work from the request
cycle. `POST /jobs` accepts work immediately with HTTP 202, a background worker
processes it, and `GET /jobs/{id}` exposes `queued`, `running`, `completed`, or
`failed` state.

## Run

```bash
uv sync
uv run pytest -q
uv run uvicorn app.main:app --reload
```

The repository uses an in-memory queue intentionally so the behavior is easy to
test. Production deployment can replace the queue adapter with Redis/Celery or
another durable broker without changing the HTTP contract.
