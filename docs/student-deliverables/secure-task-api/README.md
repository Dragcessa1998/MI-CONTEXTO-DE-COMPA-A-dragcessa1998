# Secure Task API

Standalone FastAPI implementation covering the reusable backend, authentication,
validation, error handling and testing patterns needed by the remaining practical
modules. It uses an in-memory repository so it runs without external services.

## Run

```bash
uv run uvicorn app.main:app --reload
uv run pytest
```

Demo credentials: `demo@example.com` / `correct-horse-battery-staple`.

## Endpoints

- `POST /auth/login` returns a signed JWT.
- `GET /tasks` lists only the authenticated user's tasks.
- `POST /tasks` validates and creates a task.
- `GET /health` is public.

Errors use a stable `{code, message, details}` shape; secrets are never returned.
