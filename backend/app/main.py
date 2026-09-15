import os
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, case_generation, cases, guidelines, knowledge, sessions, skills, sp, students, teacher
from app.auth import require_role
from app.core.llm_config import LLM_API_KEY, LLM_MODEL
from app.services.llm_service import llm_service
from fastapi import Depends

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


@app.get("/api/system/ai-status", dependencies=[Depends(require_role(["teacher"]))])
def ai_status() -> dict:
    return {
        "configured": bool(LLM_API_KEY),
        "provider": "deepseek",
        "model": LLM_MODEL,
        "reachable": None,
    }


@app.post("/api/system/ai-probe", dependencies=[Depends(require_role(["teacher"]))])
def ai_probe() -> dict:
    if not LLM_API_KEY:
        return {"configured": False, "reachable": False, "provider": "deepseek", "model": LLM_MODEL, "latency_ms": None, "error_type": "NotConfigured"}
    started = time.monotonic()
    try:
        # Keep this real request intentionally tiny and never expose provider output.
        llm_service._client().chat([{"role": "user", "content": "Reply: ok"}], temperature=0)
        return {"configured": True, "reachable": True, "provider": "deepseek", "model": LLM_MODEL, "latency_ms": round((time.monotonic() - started) * 1000), "error_type": None}
    except Exception as error:
        return {"configured": True, "reachable": False, "provider": "deepseek", "model": LLM_MODEL, "latency_ms": round((time.monotonic() - started) * 1000), "error_type": type(error).__name__}
