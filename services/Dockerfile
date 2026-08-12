FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    PYTHONPATH=/workspace:/workspace/services/api

RUN pip install --no-cache-dir uv==0.8.13

WORKDIR /workspace

# El paquete compartido se instala desde su fuente única del monorepo.
COPY packages/shared ./packages/shared
COPY services/requirements.txt ./services/requirements.txt
WORKDIR /workspace/services
RUN uv pip install --system -r requirements.txt

COPY services /workspace/services
COPY data /workspace/data
COPY docs/company-knowledge-base /workspace/docs/company-knowledge-base
WORKDIR /workspace/services/api

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
