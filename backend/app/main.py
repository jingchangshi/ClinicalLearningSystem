import os
import logging
import subprocess
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.routes import auth, case_generation, cases, guidelines, knowledge, sessions, skills, sp, students, teacher
from app.auth import require_role
from app.core.ai_runtime import ai_runtime
from app.core import ai_audit
from app.core.rate_limit import enforce
from app.core.llm_config import LLM_CONFIGURED, llm_config_summary
from app.core.reasoning_steps import REQUIRED_REASONING_STEPS, REQUIRED_STEP_KEYS
from app.core.source_fingerprint import source_fingerprint
from app.database import get_db
from app.models import AIInvocation
from app.services.llm_service import llm_service

@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    # Best-effort: persist any queued AI audit events before the process exits.
    ai_audit.flush(timeout=2.0)


app = FastAPI(title="ClinPath：AI辅助临床教学与自适应学习路径系统", lifespan=lifespan)
logger = logging.getLogger("clinpath.requests")
environment = os.getenv("CLINPATH_ENV", "development").lower()

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
    config = llm_config_summary()
    runtime = ai_runtime.snapshot()
    return {
        "configured": config["configured"],
        "provider": config["provider"],
        "model": config["model"],
        "base_url_host": config["base_url_host"],
        "reachable": runtime["last_probe_ok"],
        "last_probe_at": runtime["last_probe_at"],
        "last_probe_latency_ms": runtime["last_probe_latency_ms"],
        "last_error_type": runtime["last_error_type"],
        "last_call_at": runtime["last_call_at"],
        "last_call_mode": runtime["last_call_mode"],
        "calls": runtime["calls"],
        "failures": runtime["failures"],
        "fallbacks": runtime["fallbacks"],
        "timeout_seconds": config["timeout_seconds"],
        "max_retries": config["max_retries"],
        "deprecated_variables_in_use": config["deprecated_variables_in_use"],
    }


@app.post("/api/system/ai-probe", dependencies=[Depends(require_role(["teacher"]))])
def ai_probe(request: Request) -> dict:
    enforce("ai_probe", f"ip:{request.client.host if request.client else 'unknown'}")
    started = time.monotonic()
    outcome = llm_service.probe()
    config = llm_config_summary()
    return {
        "configured": config["configured"],
        "provider": config["provider"],
        "model": config["model"],
        "latency_ms": outcome["latency_ms"] if outcome["latency_ms"] is not None else round((time.monotonic() - started) * 1000),
        **outcome,
    }


@app.get("/api/system/version")
def system_version(db: Session = Depends(get_db)) -> dict:
    """Deployment truth: which code and schema this process is actually running."""

    return {
        "app": "clinpath",
        "environment": environment,
        "git_sha": git_revision()[0],
        "git_sha_short": (git_revision()[0] or "")[:8] or None,
        "git_dirty": git_revision()[1],
        "backend_source_fingerprint": source_fingerprint(),
        "schema_revision": schema_revision(db),
        "backend_runtime": f"python {os.sys.version_info.major}.{os.sys.version_info.minor}",
        "ai_configured": LLM_CONFIGURED,
    }


@app.get("/api/system/reasoning-steps")
def system_reasoning_steps(user=Depends(require_role(["student"]))) -> dict:
    """The canonical reasoning steps, so the training UI renders exactly what the
    backend will validate on submission."""

    return {"steps": REQUIRED_REASONING_STEPS, "required_keys": REQUIRED_STEP_KEYS}


@app.get("/api/system/ai-invocations", dependencies=[Depends(require_role(["teacher"]))])
def ai_invocations(db: Session = Depends(get_db), limit: int = 20) -> dict:
    """Recent AI task invocations plus a per-task rollup. Metadata only: prompt
    and response bodies are never stored."""

    limit = max(1, min(limit, 100))
    recent = (
        db.query(AIInvocation).order_by(AIInvocation.id.desc()).limit(limit).all()
    )
    rollup = db.execute(
        text(
            "select task_type, count(*) as events, sum(calls) as calls,"
            " sum(failures) as failures, sum(fallback_used) as fallbacks,"
            " cast(avg(latency_ms) as integer) as avg_latency_ms,"
            " max(created_at) as last_seen"
            " from ai_invocations group by task_type order by task_type"
        )
    ).mappings()
    return {
        "recent": [
            {
                "id": row.id,
                "task_type": row.task_type,
                "provider": row.provider,
                "model": row.model,
                "prompt_version": row.prompt_version,
                "evidence_ref": row.evidence_ref,
                "session_id": row.session_id,
                "student_id": row.student_id,
                "calls": row.calls,
                "failures": row.failures,
                "success": row.success,
                "fallback_used": row.fallback_used,
                "latency_ms": row.latency_ms,
                "error_type": row.error_type,
                "created_at": row.created_at,
            }
            for row in recent
        ],
        "by_task": [dict(row) for row in rollup],
    }


_GIT_REVISION_CACHE: tuple[str | None, bool] | None = None


def git_revision() -> tuple[str | None, bool]:
    """(commit id, working tree dirty) so an operator can tell that the running
    process carries local edits instead of reading a stale commit id as truth."""

    global _GIT_REVISION_CACHE
    if _GIT_REVISION_CACHE is None:
        revision = (os.getenv("APP_GIT_SHA") or "").strip() or _git_command("rev-parse", "HEAD")
        _GIT_REVISION_CACHE = (revision or None, bool(_git_command("status", "--porcelain")))
    return _GIT_REVISION_CACHE


def _git_command(*args: str) -> str:
    try:
        # Never expose the working tree path, only the commit id / dirty flag.
        result = subprocess.run(
            ["git", *args],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def schema_revision(db: Session) -> str | None:
    try:
        return db.execute(text("select version_num from alembic_version")).scalar()
    except Exception:
        return None
