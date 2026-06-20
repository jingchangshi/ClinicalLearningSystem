import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import case_generation, cases, guidelines, knowledge, sessions, skills, sp, students, teacher
from app.seed_data import init_db

init_db()

app = FastAPI(title="诊途：临床推理与自适应学习系统")

default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8101",
    "http://127.0.0.1:8101",
    "http://129.153.118.58:8101",
]
frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", ",".join(default_origins)).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(students.router)
app.include_router(cases.router)
app.include_router(sessions.router)
app.include_router(teacher.router)
app.include_router(knowledge.router)
app.include_router(skills.router)
app.include_router(guidelines.router)
app.include_router(sp.router)
app.include_router(case_generation.router)


@app.get("/health")
@app.head("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/health")
@app.head("/api/health")
def api_health() -> dict:
    return {"status": "ok"}
