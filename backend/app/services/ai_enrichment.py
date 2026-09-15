"""AI enrichment: cached explanation wording, generated off the read path.

The invariant this module exists to hold: **an ordinary GET/read request never
calls the provider.** A page read returns the deterministic pathway (or the
deterministic class aggregate) immediately, plus, when a *current* cached
enrichment exists, better wording for the parts a model writes well.

Lifecycle:

    learning event -> competency/evidence update -> deterministic pathway
                                                      |
                                                      v
                                          optional AI enrichment (persisted)
                                                      |
    GET /student/pathway  <-- read persisted state --+

Durability is deliberately asymmetric:

  * Core assessment state (score, evidence, competency projection) is written
    synchronously inside the request transaction and must never be lost.
  * Enrichment text is optional and regenerable. Losing a queued enrichment task
    costs a nicer sentence, so a best-effort in-process worker is enough — and it
    is only started when a provider is actually configured.

Invalidation is data, not a timer: every row stores ``source_fingerprint`` — a
digest of the evidence that produced it. A row is used only while the fingerprint
still matches, so a stale explanation can never be shown as current.
"""

import hashlib
import logging
import os
import queue
import threading
from typing import Callable, Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import ai_audit
from app.core.ai_audit import ai_invocation
from app.core.llm_config import LLM_CONFIGURED, LLM_MODEL, LLM_PROVIDER
from app.models import AIEnrichment, LearningEvidenceEvent, Student
from app.services.learning_evidence_service import build_student_evidence_summary
from app.services.llm_service import llm_service
from app.services.pathway_context import load_pathway_catalog
from app.services.recommendation_service import build_learning_pathway, task_key
from app.services.serializers import dumps_json, loads_json, serialize_profile

logger = logging.getLogger("clinpath.ai_enrichment")

KIND_PATHWAY = "pathway"
KIND_TEACHER_INSIGHT = "teacher_insight"

CLASS_CACHE_KEY = "class"
# Escape hatch for tests, for load tests and for an operator who wants provider
# traffic to stop immediately without redeploying.
ENABLE_ENV_VAR = "CLINPATH_AI_ENRICHMENT"


def _enabled() -> bool:
    if not LLM_CONFIGURED:
        return False
    return (os.getenv(ENABLE_ENV_VAR) or "on").strip().lower() not in {"0", "off", "false", "no"}


# --- fingerprints (the invalidation rule) -------------------------------------


def _digest(*parts: object) -> str:
    joined = "|".join(str(part) for part in parts)
    return f"v1:{hashlib.sha256(joined.encode()).hexdigest()[:16]}"


def student_fingerprint(db: Session, student_id: int) -> str:
    """Changes whenever this learner's evidence or competency projection moves."""

    student = db.get(Student, student_id)
    updated_at = None
    if student is not None and student.competency_profile is not None:
        updated_at = student.competency_profile.updated_at
    latest_event = (
        db.query(func.max(LearningEvidenceEvent.id))
        .filter(LearningEvidenceEvent.student_id == student_id)
        .scalar()
    )
    return _digest("student", student_id, updated_at, latest_event or 0)


def class_fingerprint(db: Session) -> str:
    """Changes whenever any learner in the class produces new evidence."""

    latest_event = db.query(func.max(LearningEvidenceEvent.id)).scalar()
    event_count = db.query(func.count(LearningEvidenceEvent.id)).scalar()
    return _digest("class", latest_event or 0, event_count or 0)


# --- reads (what a GET is allowed to do) --------------------------------------


def load_current(db: Session, kind: str, cache_key: str, fingerprint: str) -> dict | None:
    """Return the cached payload only when it still describes the current state."""

    row = (
        db.query(AIEnrichment)
        .filter(AIEnrichment.kind == kind, AIEnrichment.cache_key == cache_key)
        .first()
    )
    if row is None or row.source_fingerprint != fingerprint:
        return None
    payload = loads_json(row.payload_json, None)
    if not isinstance(payload, dict):
        return None
    return {
        "payload": payload,
        "generated_at": row.generated_at,
        "provider": row.provider,
        "model": row.model,
        "prompt_version": row.prompt_version,
        "fallback_used": row.fallback_used,
    }


def current_pathway_enrichment(db: Session, student_id: int) -> dict | None:
    return load_current(db, KIND_PATHWAY, f"student:{student_id}", student_fingerprint(db, student_id))


def current_teacher_insight(db: Session) -> dict | None:
    return load_current(db, KIND_TEACHER_INSIGHT, CLASS_CACHE_KEY, class_fingerprint(db))


def explanation_for(enrichment: dict | None, key: str) -> str | None:
    if not enrichment:
        return None
    explanations = enrichment["payload"].get("explanations")
    if not isinstance(explanations, dict):
        return None
    value = explanations.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def apply_task_explanations(tasks: Iterable[dict], enrichment: dict | None) -> str:
    """Rewrite rule reasons with current AI wording. Returns the source label."""

    used = False
    for task in tasks:
        explanation = explanation_for(enrichment, task_key(task))
        if explanation:
            task["reason"] = explanation
            task["reason_source"] = "ai"
            used = True
        else:
            task["reason_source"] = "rule"
    return "ai" if used else "rule"


# --- writes (generation) -------------------------------------------------------


def regenerate_pathway(db: Session, student_id: int) -> bool:
    """Rebuild one learner's pathway explanation from the current evidence."""

    student = db.get(Student, student_id)
    if student is None or student.competency_profile is None:
        return False
    profile = serialize_profile(student.competency_profile)
    pathway = build_learning_pathway(profile, load_pathway_catalog(db))
    tasks = pathway["recommended_tasks"]
    evidence = build_student_evidence_summary(db, student_id)["evidence_summary"]
    explanations: dict[str, str] = {}
    fallback_used = False
    if tasks:
        with ai_invocation(
            "recommendation_explanation",
            student_id=student_id,
            evidence_ref=f"learning_pathway:student:{student_id}",
        ) as invocation:
            explanations = llm_service.explain_recommendation_batch(
                profile,
                {"evidence_summary": evidence},
                [
                    {
                        "task_key": task_key(task),
                        "title": task["title"],
                        "type": task["type"],
                        "priority": task["priority"],
                        "fallback_reason": task["reason"],
                        "target_abilities": task.get("target_abilities", []),
                    }
                    for task in tasks
                ],
            )
            fallback_used = invocation.fallback_used
    payload = {
        "explanations": explanations,
        "task_keys": [task_key(task) for task in tasks],
        "current_stage": pathway["current_stage"],
    }
    _store(
        db,
        KIND_PATHWAY,
        f"student:{student_id}",
        student_id,
        payload,
        student_fingerprint(db, student_id),
        fallback_used=fallback_used,
    )
    return True


def regenerate_teacher_insight(db: Session, generate: Callable[[Session], str | None]) -> str | None:
    """Persist a class insight. ``generate`` is supplied by the teacher route so
    this module stays free of dashboard assembly details."""

    text = generate(db)
    if not text or not text.strip():
        return None
    payload = {"insight": text.strip()}
    _store(
        db,
        KIND_TEACHER_INSIGHT,
        CLASS_CACHE_KEY,
        None,
        payload,
        class_fingerprint(db),
        fallback_used=False,
    )
    return payload["insight"]


def _store(
    db: Session,
    kind: str,
    cache_key: str,
    student_id: int | None,
    payload: dict,
    fingerprint: str,
    *,
    fallback_used: bool = False,
) -> None:
    record = (
        db.query(AIEnrichment)
        .filter(AIEnrichment.kind == kind, AIEnrichment.cache_key == cache_key)
        .first()
    )
    if record is None:
        record = AIEnrichment(kind=kind, cache_key=cache_key, student_id=student_id)
        db.add(record)
    record.payload_json = dumps_json(payload)
    record.prompt_version = ai_audit.PROMPT_VERSIONS.get(
        "recommendation_explanation" if kind == KIND_PATHWAY else "teacher_insight"
    )
    record.provider = LLM_PROVIDER
    record.model = LLM_MODEL
    record.source_fingerprint = fingerprint
    record.fallback_used = fallback_used
    db.commit()


# --- background scheduling -----------------------------------------------------

_pending: set[tuple[str, int | None]] = set()
_lock = threading.Lock()
_wake = threading.Event()
_worker: threading.Thread | None = None
_session_factory: Callable[[], Session] | None = None


def set_session_factory(factory: Callable[[], Session] | None) -> None:
    """Test hook, mirroring ``ai_audit.set_session_factory``."""

    global _session_factory
    _session_factory = factory


def _session() -> Session:
    if _session_factory is not None:
        return _session_factory()
    from app.database import SessionLocal

    return SessionLocal()


def schedule_student(student_id: int) -> None:
    """Called after a committed learning event. Cheap and safe to call always."""

    if not _enabled():
        return
    _enqueue((KIND_PATHWAY, student_id))
    _enqueue((KIND_TEACHER_INSIGHT, None))


def _enqueue(item: tuple[str, int | None]) -> None:
    global _worker
    with _lock:
        # Coalesce: N events for one student need one regeneration, not N.
        _pending.add(item)
        if _worker is None:
            _worker = threading.Thread(target=_worker_loop, name="ai-enrichment", daemon=True)
            _worker.start()
    _wake.set()


def pending_count() -> int:
    with _lock:
        return len(_pending)


def _worker_loop() -> None:
    while True:
        _wake.wait(timeout=30.0)
        _wake.clear()
        while True:
            with _lock:
                if not _pending:
                    break
                kind, student_id = _pending.pop()
            _run(kind, student_id)


def _run(kind: str, student_id: int | None) -> None:
    db = _session()
    try:
        if kind == KIND_PATHWAY and student_id is not None:
            regenerate_pathway(db, student_id)
        elif kind == KIND_TEACHER_INSIGHT:
            from app.routes.teacher import build_teacher_insight_text

            regenerate_teacher_insight(db, build_teacher_insight_text)
    except Exception as error:  # enrichment is optional; never break the request path
        db.rollback()
        logger.warning(
            "ai_enrichment: regeneration failed kind=%s student_id=%s failure_type=%s",
            kind,
            student_id,
            type(error).__name__,
        )
    finally:
        db.close()
