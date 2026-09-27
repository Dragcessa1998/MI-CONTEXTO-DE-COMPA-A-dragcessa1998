import time
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Request duration", ["method", "path"])

app = FastAPI(title="Observability Docker API", version="0.1.0")

@app.middleware("http")
async def telemetry(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    REQUESTS.labels(request.method, path, str(response.status_code)).inc()
    LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
    response.headers["X-Request-Duration-Ms"] = f"{(time.perf_counter()-started)*1000:.2f}"
    return response

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    return {"status": "ready", "dependencies": {"in_memory_store": "ok"}}

@app.get("/hello")
def hello(name: str = "world"):
    return {"message": f"Hello, {name}!"}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
