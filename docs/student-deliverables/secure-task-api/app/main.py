import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

SECRET = os.getenv("TASK_API_SECRET", "dev-only-change-me")
ALGORITHM = "HS256"
# PBKDF2 avoids platform-specific bcrypt backend issues while remaining a slow,
# salted password hash suitable for this standalone example.
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")
users = {"demo@example.com": {"id": 1, "password": pwd.hash("correct-horse-battery-staple")}}
tasks = []

class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = {}

class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)

class Task(TaskIn):
    id: int
    owner_id: int
    completed: bool = False

app = FastAPI(title="Secure Task API", version="0.1.0")

def fail(code: str, message: str, status_code: int, details: dict | None = None):
    raise HTTPException(status_code, detail={"code": code, "message": message, "details": details or {}})

def token_for(user_id: int) -> str:
    return jwt.encode({"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=30)}, SECRET, algorithm=ALGORITHM)

def current_user(token: Annotated[str, Depends(oauth2)]):
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub", ""))
    except (JWTError, ValueError):
        fail("AUTH_INVALID", "Invalid or expired token", status.HTTP_401_UNAUTHORIZED)
    user = next((u for u in users.values() if u["id"] == user_id), None)
    if not user:
        fail("AUTH_INVALID", "User no longer exists", status.HTTP_401_UNAUTHORIZED)
    return user

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/login")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = users.get(form.username)
    if not user or not pwd.verify(form.password, user["password"]):
        fail("AUTH_FAILED", "Incorrect email or password", status.HTTP_401_UNAUTHORIZED)
    return {"access_token": token_for(user["id"]), "token_type": "bearer"}

@app.get("/tasks", response_model=list[Task])
def list_tasks(user=Depends(current_user)):
    return [t for t in tasks if t.owner_id == user["id"]]

@app.post("/tasks", response_model=Task, status_code=201)
def create_task(body: TaskIn, user=Depends(current_user)):
    task = Task(id=len(tasks) + 1, owner_id=user["id"], **body.model_dump())
    tasks.append(task)
    return task
