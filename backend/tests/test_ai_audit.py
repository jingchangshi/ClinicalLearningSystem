"""Every AI capability must leave one bounded, PHI-free audit event."""

import pytest

from app.core import ai_audit
from app.core.ai_audit import PROMPT_VERSIONS, ai_invocation
from app.core.reasoning_steps import REQUIRED_STEP_KEYS
from app.models import AIInvocation
from app.services import llm_service as llm_module
from app.services.llm_service import LLMService

from tests.factories import ANSWER_TEXTS, make_case, make_student


@pytest.fixture(autouse=True)
def audit_into_test_db(db_factory):
    """Point the audit writer at the test database for this module."""

    from sqlalchemy.orm import sessionmaker

    db = db_factory()
    engine = db.get_bind()
    db.close()
    testing_session = sessionmaker(bind=engine, autoflush=False)
    previous = ai_audit._session_factory
    ai_audit.set_session_factory(testing_session)
    try:
        yield testing_session
    finally:
        ai_audit.set_session_factory(previous)


def test_audit_records_metadata_without_bodies(audit_into_test_db):
    with ai_invocation("tutor_question", session_id=7, student_id=3, evidence_ref="case_session:7:step:treatment"):
        ai_audit.report_call(success=True, fallback_used=False, latency_ms=412)
        ai_audit.report_call(success=True, fallback_used=False, latency_ms=88)

    assert ai_audit.flush() is True
    db = audit_into_test_db()
    row = db.query(AIInvocation).one()
    assert row.task_type == "tutor_question"
    assert row.session_id == 7 and row.student_id == 3
    assert row.evidence_ref == "case_session:7:step:treatment"
    assert row.calls == 2 and row.failures == 0
    assert row.latency_ms == 500
    assert row.success is True and row.fallback_used is False
    assert row.prompt_version == PROMPT_VERSIONS["tutor_question"]
    # No prompt/response payload columns may exist at all.
    columns = set(AIInvocation.__table__.columns.keys())
    assert not columns & {"prompt", "response", "completion", "body", "payload", "messages"}
    db.close()


def test_audit_marks_fallback_and_failure(audit_into_test_db):
    with ai_invocation("case_evaluation"):
        ai_audit.report_call(success=False, fallback_used=False, latency_ms=900, error_type="APITimeoutError")
        ai_audit.report_call(success=False, fallback_used=True, latency_ms=0, error_type="APITimeoutError")

    assert ai_audit.flush() is True
    db = audit_into_test_db()
    row = db.query(AIInvocation).one()
    assert row.success is False
    assert row.fallback_used is True
    assert row.failures == 2
    assert row.error_type == "APITimeoutError"
    db.close()


def test_service_reports_each_provider_attempt(monkeypatch, audit_into_test_db):
    service = LLMService()
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("provider down")
        return "ok"

    monkeypatch.setattr(llm_module, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(service, "_chat_text_once", lambda *_: flaky())
    with ai_invocation("sp_patient", session_id=1):
        assert service.chat_completion("s", "u", "fallback") == "ok"

    assert ai_audit.flush() is True
    db = audit_into_test_db()
    row = db.query(AIInvocation).one()
    assert row.calls == 2
    assert row.failures == 1
    assert row.success is False  # one attempt failed, so the task was not clean
    assert row.fallback_used is False
    db.close()


def test_unconfigured_provider_is_audited_as_fallback(monkeypatch, audit_into_test_db):
    service = LLMService()
    monkeypatch.setattr(llm_module, "LLM_API_KEY", None)
    with ai_invocation("recommendation_explanation"):
        assert service.chat_completion("s", "u", "rule text") == "rule text"

    assert ai_audit.flush() is True
    db = audit_into_test_db()
    row = db.query(AIInvocation).one()
    assert row.fallback_used is True
    assert row.success is False
    assert row.error_type == "NotConfigured"
    assert row.calls == 1
    db.close()


def test_submit_and_tutor_write_audit_events(db_factory, client):
    db = db_factory()
    make_case(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200
    session_id = client.post("/api/sessions/start", json={"case_id": 1}).json()["id"]
    for step in REQUIRED_STEP_KEYS:
        client.post(
            f"/api/sessions/{session_id}/answers",
            json={"step": step, "answer_text": ANSWER_TEXTS[step]},
        )
    assert client.post(f"/api/sessions/{session_id}/tutor", json={"step": "treatment"}).status_code == 200
    assert client.post(f"/api/sessions/{session_id}/submit").status_code == 200

    assert ai_audit.flush() is True
    db = db_factory()
    tasks = {row.task_type for row in db.query(AIInvocation).all()}
    assert {"case_evaluation", "tutor_question"} <= tasks
    tutor_row = db.query(AIInvocation).filter(AIInvocation.task_type == "tutor_question").one()
    assert tutor_row.session_id == session_id
    assert tutor_row.evidence_ref.endswith("step:treatment")
    db.close()


def test_ai_invocations_endpoint_is_teacher_only(db_factory):
    db = db_factory()
    from app.auth import hash_password
    from app.models import Teacher, User

    teacher = Teacher(name="T", teacher_no="T9", department="Med")
    db.add(teacher)
    db.flush()
    db.add(User(username="teacher9", password_hash=hash_password("secret1"), role="teacher", teacher_id=teacher.id))
    make_student(db, username="learner9")
    db.commit()
    db.close()

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/system/ai-invocations").status_code == 401
        assert client.post("/api/auth/login", json={"username": "learner9", "password": "secret1"}).status_code == 200
        assert client.get("/api/system/ai-invocations").status_code == 403

    with TestClient(app) as client:
        assert client.post("/api/auth/login", json={"username": "teacher9", "password": "secret1"}).status_code == 200
        response = client.get("/api/system/ai-invocations")
        assert response.status_code == 200
        assert set(response.json()) == {"recent", "by_task"}
