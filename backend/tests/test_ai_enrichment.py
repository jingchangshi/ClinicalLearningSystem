"""The enrichment worker must actually reach both kinds of enrichment.

A wrong import name in the worker's lazy import stayed invisible because the
worker swallows its own exceptions: every learning event logged a warning and
the class insight was simply never generated. These tests drive the worker entry
point itself, not the functions around it.
"""

import pytest

from app.services import ai_enrichment
from app.services.llm_service import llm_service
from tests.factories import make_case, make_catalog, make_student


@pytest.fixture
def seeded(db_factory):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _user = make_student(db, username="learner")
    db.commit()
    student_id = student.id
    db.close()
    return student_id


@pytest.fixture
def worker_uses_test_database(db_factory):
    ai_enrichment.set_session_factory(db_factory)
    try:
        yield
    finally:
        ai_enrichment.set_session_factory(None)


def test_worker_generates_the_class_insight(seeded, db_factory, worker_uses_test_database, monkeypatch):
    monkeypatch.setattr(llm_service, "generate_teacher_insight", lambda *args, **kwargs: "班级共性短板为鉴别诊断。")

    ai_enrichment._run(ai_enrichment.KIND_TEACHER_INSIGHT, None)

    db = db_factory()
    row = ai_enrichment.current_teacher_insight(db)
    db.close()
    assert row is not None, "the worker must persist a class insight"
    assert row["payload"]["insight"] == "班级共性短板为鉴别诊断。"


def test_worker_generates_the_pathway_explanation(seeded, db_factory, worker_uses_test_database, monkeypatch):
    monkeypatch.setattr(
        llm_service,
        "explain_recommendation_batch",
        lambda profile, evidence, tasks: {task["task_key"]: "AI 写的推荐理由" for task in tasks},
    )

    ai_enrichment._run(ai_enrichment.KIND_PATHWAY, seeded)

    db = db_factory()
    row = ai_enrichment.current_pathway_enrichment(db, seeded)
    db.close()
    assert row is not None
    assert row["payload"]["explanations"]


def test_a_failing_enrichment_never_escapes_the_worker(seeded, db_factory, worker_uses_test_database, monkeypatch):
    def explode(*_args, **_kwargs):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(llm_service, "explain_recommendation_batch", explode)

    ai_enrichment._run(ai_enrichment.KIND_PATHWAY, seeded)

    db = db_factory()
    assert ai_enrichment.current_pathway_enrichment(db, seeded) is None
    db.close()


def test_scheduling_is_a_no_op_without_a_provider(monkeypatch):
    monkeypatch.setattr(ai_enrichment, "LLM_CONFIGURED", False)

    ai_enrichment.schedule_student(1)

    assert ai_enrichment.pending_count() == 0
