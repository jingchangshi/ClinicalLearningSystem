"""Permanent architecture gate: an ordinary read must not reach the provider.

Timing alone is weak evidence — a fast path can still be one cached DNS lookup
away from a paid call. These tests replace the SDK boundary and assert
``provider_call_count == 0`` for every navigation endpoint the goal names, and
they additionally assert that a read publishes no AI audit event at all.
"""

import json
from types import SimpleNamespace

import pytest

from app.core import ai_audit
from app.services import llm_service as llm_module
from tests.factories import ANSWER_TEXTS, make_case, make_catalog, make_student


class ProviderSpy:
    """A live-looking provider plus the audit hook, recording instead of sending."""

    def __init__(self) -> None:
        self.provider_calls: list[dict] = []
        self.audit_calls: list[dict] = []

    @property
    def calls(self) -> int:
        return len(self.provider_calls)


@pytest.fixture
def recorded_provider(monkeypatch) -> ProviderSpy:
    spy = ProviderSpy()
    calls = spy.provider_calls

    class _Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps(
                                {
                                    "explanations": {"case:1": "AI 写的推荐理由"},
                                    "insight": "AI 写的班级洞察",
                                }
                            )
                        )
                    )
                ]
            )

    class _FakeOpenAI:
        def __init__(self, *_args, **_kwargs):
            self.chat = SimpleNamespace(completions=_Completions())

    monkeypatch.setattr(llm_module, "OpenAI", _FakeOpenAI)
    # With a key present the service takes the real path, so a route that calls
    # the model cannot hide behind an unconfigured deployment.
    monkeypatch.setattr(llm_module, "LLM_API_KEY", "test-key")
    # ``report_call`` fires once per provider attempt, so it also catches a call
    # that never reaches the SDK.
    monkeypatch.setattr(ai_audit, "report_call", lambda **kwargs: spy.audit_calls.append(kwargs))
    return spy


def _seed(db_factory):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _user = make_student(db, username="learner")
    db.commit()
    student_id = student.id
    db.close()
    return student_id


def _login_student(client) -> None:
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200


def _login_teacher(client, db_factory) -> None:
    from app.auth import create_access_token
    from app.models import User

    db = db_factory()
    teacher = User(username="teacher", password_hash="x", role="teacher")
    db.add(teacher)
    db.commit()
    token = create_access_token(teacher)
    db.close()
    client.cookies.set("access_token", token)


@pytest.mark.parametrize(
    "path",
    ["/api/student/pathway", "/api/student/dashboard", "/api/student/competency"],
)
def test_student_read_endpoints_make_no_provider_call(db_factory, client, recorded_provider, path):
    _seed(db_factory)
    _login_student(client)

    response = client.get(path)

    assert response.status_code == 200
    assert recorded_provider.provider_calls == [], f"{path} reached the provider: reads must stay deterministic"
    assert recorded_provider.audit_calls == [], f"{path} published an AI audit event during a read"


def test_teacher_read_endpoints_make_no_provider_call(db_factory, client, recorded_provider):
    student_id = _seed(db_factory)
    _login_teacher(client, db_factory)

    for path in ("/api/teacher/dashboard", f"/api/teacher/students/{student_id}/learning-profile"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert recorded_provider.provider_calls == [], f"{path} reached the provider"
        assert recorded_provider.audit_calls == [], f"{path} published an AI audit event during a read"


def test_pathway_still_ranks_and_explains_without_a_provider(db_factory, client, recorded_provider):
    _seed(db_factory)
    _login_student(client)

    payload = client.get("/api/student/pathway").json()

    assert payload["recommended_tasks"], "the deterministic pipeline must still produce tasks"
    for task in payload["recommended_tasks"]:
        assert task["reason"].strip()
        assert task["reason_source"] == "rule"
    assert payload["explanation_source"] == "rule"
    assert payload["explanation_generated_at"] is None
    assert payload["recommendation_reason_source"] == "rule"


def test_teacher_dashboard_uses_rule_insight_until_one_is_cached(db_factory, client, recorded_provider):
    _seed(db_factory)
    _login_teacher(client, db_factory)

    payload = client.get("/api/teacher/dashboard").json()

    assert payload["teaching_insight_source"] == "rule"
    assert payload["teaching_insight_summary"]
    assert recorded_provider.provider_calls == []


def test_teacher_can_request_a_fresh_insight_without_turning_get_into_a_write(
    db_factory, client, recorded_provider
):
    _seed(db_factory)
    _login_teacher(client, db_factory)

    refreshed = client.post("/api/teacher/dashboard/refresh-insight")

    assert refreshed.status_code == 200
    assert recorded_provider.calls == 1, "the explicit refresh action is the one that may spend a call"
    # Freshly generated, so the next read serves it from the cache with no call.
    assert client.get("/api/teacher/dashboard").json()["teaching_insight_source"] == "ai"
    assert recorded_provider.calls == 1


def test_cached_explanations_are_served_without_a_provider_call(
    db_factory, client, recorded_provider, monkeypatch
):
    student_id = _seed(db_factory)
    from app.services import ai_enrichment

    monkeypatch.setattr(
        ai_enrichment.llm_service,
        "explain_recommendation_batch",
        lambda profile, evidence, tasks: {task["task_key"]: "AI 写的推荐理由" for task in tasks},
    )
    db = db_factory()
    try:
        assert ai_enrichment.regenerate_pathway(db, student_id) is True
        row = ai_enrichment.current_pathway_enrichment(db, student_id)
        assert row is not None and row["payload"]["explanations"]
    finally:
        db.close()

    calls_after_generation = recorded_provider.calls
    _login_student(client)
    payload = client.get("/api/student/pathway").json()

    assert recorded_provider.calls == calls_after_generation, "reading a cached explanation must not call the provider"
    assert payload["explanation_source"] == "ai", "a current cached explanation should be served"


def test_stale_enrichment_is_never_shown_as_current(db_factory, monkeypatch):
    """A learning event changes the fingerprint, so old wording stops applying."""

    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _user = make_student(db, username="learner")
    db.commit()

    from app.services import ai_enrichment
    from app.services.competency_update_service import update_competency_from_knowledge

    monkeypatch.setattr(llm_module, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        ai_enrichment.llm_service,
        "explain_recommendation_batch",
        lambda profile, evidence, tasks: {"case:1": "AI 写的推荐理由"},
    )
    assert ai_enrichment.regenerate_pathway(db, student.id) is True
    assert ai_enrichment.current_pathway_enrichment(db, student.id) is not None

    update_competency_from_knowledge(db, student.id, 90, source_id=1)
    db.commit()

    assert ai_enrichment.current_pathway_enrichment(db, student.id) is None
    db.close()


def test_pathway_page_does_not_trigger_generation_for_a_stale_row(db_factory, client, monkeypatch, recorded_provider):
    """Stale means "show the rule reason", not "regenerate on read"."""

    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _user = make_student(db, username="learner")
    db.commit()

    from app.services import ai_enrichment
    from app.services.competency_update_service import update_competency_from_knowledge

    monkeypatch.setattr(
        ai_enrichment.llm_service,
        "explain_recommendation_batch",
        lambda profile, evidence, tasks: {"case:1": "AI 写的推荐理由"},
    )
    ai_enrichment.regenerate_pathway(db, student.id)
    update_competency_from_knowledge(db, student.id, 90, source_id=1)
    db.commit()
    db.close()

    _login_student(client)
    payload = client.get("/api/student/pathway").json()

    assert payload["explanation_source"] == "rule"
    assert recorded_provider.calls == 0


def test_submitting_a_case_schedules_enrichment_without_blocking_the_response(
    db_factory, client, monkeypatch, recorded_provider
):
    """The write path enqueues optional enrichment; it never performs it inline."""

    from app.services import ai_enrichment

    scheduled: list[int] = []
    monkeypatch.setattr(ai_enrichment, "schedule_student", scheduled.append)
    monkeypatch.setattr(ai_enrichment, "_enabled", lambda: True)

    _seed(db_factory)
    _login_student(client)
    session_id = client.post("/api/sessions/start", json={"case_id": 1}).json()["id"]
    for step, text in ANSWER_TEXTS.items():
        client.post(f"/api/sessions/{session_id}/answers", json={"step": step, "answer_text": text})

    response = client.post(f"/api/sessions/{session_id}/submit")

    assert response.status_code == 200
    assert scheduled == [1], "the learning event must schedule enrichment"
    assert recorded_provider.calls == 1, "only the real evaluation may call the provider during submit"
