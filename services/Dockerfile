FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/nexova-venv

RUN pip install --no-cache-dir uv==0.8.13

WORKDIR /workspace

# Copy every local package referenced by the API lockfile before installing it.
COPY data ./data
COPY packages/shared ./packages/shared
COPY services /workspace/services
WORKDIR /workspace/services/api
RUN uv sync --frozen --no-dev

ENV PATH="/opt/nexova-venv/bin:${PATH}"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
