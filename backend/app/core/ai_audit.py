"""Unified AI invocation audit trail.

One audit event per AI task invocation (not per HTTP request and not per retry),
matching the contract in ``docs/ARCH.md`` §5.3:

    task_type, provider, model, prompt_version, evidence reference,
    latency, success/failure, fallback_used, created_at

Prompt and response bodies are deliberately **never** stored: the audit records a
reference (session / step / evidence id) plus a digest-free machine summary, so it
can be reviewed without moving PHI or hidden answers into a log table.
"""

import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable, Iterator

from app.core.llm_config import LLM_MODEL, LLM_PROVIDER

logger = logging.getLogger("clinpath.ai_audit")

PROMPT_VERSIONS = {
    "case_evaluation": "case-evaluation-v1",
    "tutor_question": "tutor-question-v1",
    "sp_patient": "sp-patient-v1",
    "sp_evaluation": "sp-evaluation-v1",
    "guideline_rationale": "guideline-rationale-v1",
    "recommendation_explanation": "recommendation-explanation-v1",
    "teacher_insight": "teacher-insight-v1",
    "case_generation": "case-generation-v1",
    "skill_feedback": "skill-feedback-v1",
}


@dataclass
class Invocation:
    task_type: str
    session_id: int | None = None
    student_id: int | None = None
    evidence_ref: str | None = None
    prompt_version: str | None = None
    calls: int = 0
    failures: int = 0
    fallback_used: bool = False
    latency_ms: int = 0
    error_type: str | None = None
    recorded: bool = False


_active: ContextVar[Invocation | None] = ContextVar("clinpath_ai_invocation", default=None)
_session_factory: Callable[[], object] | None = None

# Audit events are queued and written by a background thread: a busy SQLite file
# can then neither drop an event nor add lock latency to a training request.
_queue: deque[dict] = deque(maxlen=2000)
_queue_lock = threading.Lock()
_wake = threading.Event()
_flusher: threading.Thread | None = None
DROPPED_EVENTS = 0


def set_session_factory(factory: Callable[[], object] | None) -> None:
    """Test hook: point the audit writer at the test database."""

    global _session_factory
    _session_factory = factory


@contextmanager
def ai_invocation(
    task_type: str,
    *,
    session_id: int | None = None,
    student_id: int | None = None,
    evidence_ref: str | None = None,
) -> Iterator[Invocation]:
    invocation = Invocation(
        task_type=task_type,
        session_id=session_id,
        student_id=student_id,
        evidence_ref=evidence_ref,
        prompt_version=PROMPT_VERSIONS.get(task_type),
    )
    token = _active.set(invocation)
    try:
        yield invocation
    finally:
        _active.reset(token)
        invocation.recorded = _persist(invocation)


def report_call(
    *,
    success: bool,
    fallback_used: bool,
    latency_ms: int,
    error_type: str | None = None,
) -> None:
    """Called once per provider attempt by ``LLMService``."""

    invocation = _active.get()
    if invocation is None:
        return
    invocation.calls += 1
    invocation.latency_ms += max(0, latency_ms)
    if fallback_used:
        invocation.fallback_used = True
    if not success:
        invocation.failures += 1
    if error_type:
        invocation.error_type = error_type


def active_invocation() -> Invocation | None:
    return _active.get()


def _persist(invocation: Invocation) -> bool:
    if invocation.calls == 0:
        logger.warning("ai_audit: task recorded no provider call task_type=%s", invocation.task_type)
    _enqueue(_record(invocation))
    return True


def _record(invocation: Invocation) -> dict:
    return {
        "task_type": invocation.task_type,
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "prompt_version": invocation.prompt_version,
        "evidence_ref": invocation.evidence_ref,
        "session_id": invocation.session_id,
        "student_id": invocation.student_id,
        "calls": invocation.calls,
        "failures": invocation.failures,
        "success": invocation.calls > 0 and invocation.failures == 0 and not invocation.fallback_used,
        "fallback_used": invocation.fallback_used,
        "latency_ms": invocation.latency_ms,
        "error_type": invocation.error_type,
    }


def _enqueue(record: dict) -> None:
    global DROPPED_EVENTS
    with _queue_lock:
        if len(_queue) == _queue.maxlen:
            DROPPED_EVENTS += 1
            logger.warning("ai_audit: queue full, dropping oldest audit event")
        _queue.append(record)
    _start_flusher()
    _wake.set()


def _start_flusher() -> None:
    global _flusher
    if _flusher is not None and _flusher.is_alive():
        return
    _flusher = threading.Thread(target=_flush_loop, name="ai-audit-flusher", daemon=True)
    _flusher.start()


def _flush_loop() -> None:
    while True:
        _wake.wait(timeout=1.0)
        _wake.clear()
        _drain()


def _drain() -> int:
    written = 0
    for _ in range(50):
        with _queue_lock:
            if not _queue:
                break
            # Claim the record first: two drainers must never write the same event.
            record = _queue.popleft()
        if not _write(record):
            # Keep it queued for the next pass instead of losing the event.
            with _queue_lock:
                _queue.appendleft(record)
            break
        written += 1
    return written


def flush(timeout: float = 5.0) -> bool:
    """Wait until the queue is empty (tests and shutdown call this)."""

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _drain()
        with _queue_lock:
            if not _queue:
                return True
        time.sleep(0.05)
    return False


def queue_depth() -> int:
    with _queue_lock:
        return len(_queue)


def reset_for_tests() -> None:
    """Drop any queued events so tests cannot leak state into each other."""

    with _queue_lock:
        _queue.clear()


def _write(record: dict) -> bool:
    for attempt in range(3):
        try:
            from app.database import SessionLocal
            from app.models import AIInvocation

            factory = _session_factory or SessionLocal
            db = factory()
            try:
                # No statements before the INSERT: a read (even a PRAGMA) would turn
                # this into a lock upgrade, which returns SQLITE_BUSY immediately
                # instead of honouring the connection's busy_timeout.
                db.add(AIInvocation(**record))
                db.commit()
            finally:
                db.close()
            return True
        except Exception as error:
            if attempt < 2:
                time.sleep(0.1 * (2**attempt))
                continue
            logger.warning(
                "ai_audit: write failed, event stays queued task_type=%s failure_type=%s detail=%s",
                record["task_type"],
                type(error).__name__,
                str(error)[:200],
            )
            return False
    return False
