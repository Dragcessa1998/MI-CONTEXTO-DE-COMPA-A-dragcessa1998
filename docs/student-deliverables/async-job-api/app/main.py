from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from threading import Lock
from uuid import uuid4
from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

class JobState(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"

class JobRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)

class Job(BaseModel):
    id: str
    state: JobState
    result: str | None = None
    error: str | None = None

app = FastAPI(title="Async Job API", version="0.1.0")
jobs: dict[str, Job] = {}
lock = Lock()
executor = ThreadPoolExecutor(max_workers=2)

def process(job_id: str, text: str):
    with lock:
        jobs[job_id].state = JobState.running
    try:
        result = text.upper()
        with lock:
            jobs[job_id].result = result
            jobs[job_id].state = JobState.completed
    except Exception as exc:
        with lock:
            jobs[job_id].error = str(exc)
            jobs[job_id].state = JobState.failed

def enqueue(job_id: str, text: str):
    executor.submit(process, job_id, text)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/jobs", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
def create_job(body: JobRequest, background: BackgroundTasks):
    job_id = str(uuid4())
    job = Job(id=job_id, state=JobState.queued)
    with lock:
        jobs[job_id] = job
    background.add_task(enqueue, job_id, body.text)
    return job

@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    with lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"code":"JOB_NOT_FOUND","message":"Unknown job"})
        return job
