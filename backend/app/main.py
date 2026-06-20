from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import cases, sessions, students, teacher
from app.seed_data import init_db

init_db()

app = FastAPI(title="诊途：临床推理与自适应学习系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(students.router)
app.include_router(cases.router)
app.include_router(sessions.router)
app.include_router(teacher.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/health")
def api_health() -> dict:
    return {"status": "ok"}
