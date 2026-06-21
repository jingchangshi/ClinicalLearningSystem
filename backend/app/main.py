import os
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, case_generation, cases, guidelines, knowledge, sessions, skills, sp, students, teacher
from app.seed_data import init_db

init_db()

app = FastAPI(title="ClinPath：AI辅助临床教学与自适应学习路径系统")
logger = logging.getLogger("clinpath.requests")

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


@app.middleware("http")
async def log_request_paths(request: Request, call_next):
    response = await call_next(request)
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    message = "%s %s -> %s matched=%s"
    if response.status_code == 404:
        logger.warning(message, request.method, request.url.path, response.status_code, route_path or "unmatched")
    else:
        logger.info(message, request.method, request.url.path, response.status_code, route_path or "unmatched")
    return response

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(students.student_router)
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
