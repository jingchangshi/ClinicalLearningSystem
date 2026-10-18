"""A teacher review must say which score it was compared against, and who made it.

The bug this pins: ``POST /api/teacher/reviews`` used to write
``Score.ai_score if not None else Score.total_score`` into
``TeacherScoreReview.ai_score``. On a rule-fallback evaluation ``ai_score`` is
None, so the *rule* total was stored in the AI column. A reviewer reading the
history, or any agreement statistic, then could not tell a rule score from a
model score — which is exactly the provenance claim the platform makes
elsewhere.
"""

import pytest

from app.auth import create_access_token
from app.models import (
    CaseSession,
    LearningEvidenceEvent,
    Score,
    TeacherScoreReview,
    User,
)
from app.services.serializers import dumps_json
from tests.factories import make_case, make_student

DIMENSIONS = {
    "medical_knowledge": 80,
    "key_information": 80,
    "differential_diagnosis": 80,
    "evidence_integration": 80,
    "clinical_decision": 80,
    "evidence_based_medicine": 80,
}


def _teacher(client, db_factory, username: str = "reviewer") -> None:
    db = db_factory()
    try:
        user = User(username=username, password_hash="x", role="teacher")
        db.add(user)
        db.commit()
        token = create_access_token(user)
    finally:
        db.close()
    client.cookies.set("access_token", token)


def _scored_session(
    db,
    *,
    evaluation_mode: str,
    degraded: bool,
    ai_score: float | None,
    total: float,
    rule_score: float | None = None,
):
    case = make_case(db)
    student, _ = make_student(db)
    session = CaseSession(student_id=student.id, case_id=case.id, status="completed")
    session.completed_at = session.started_at
    db.add(session)
    db.flush()
    db.add(
        Score(
            session_id=session.id,
            total_score=total,
            **{key: total for key in DIMENSIONS},
            feedback="反馈",
            strengths="优点",
            weaknesses="不足",
            evaluation_mode=evaluation_mode,
            degraded=degraded,
            ai_score=ai_score,
            rule_score=rule_score if rule_score is not None else total,
        )
    )
    event = LearningEvidenceEvent(
        student_id=student.id,
        module_type="case",
        module_id=case.id,
        session_id=session.id,
        event_type="case_session_scored",
        source_table="case_sessions",
        source_id=session.id,
        score=total,
        competency_updates_json=dumps_json({}),
        evidence_payload_json=dumps_json({}),
    )
    db.add(event)
    db.commit()
    return event


def _submit_review(client, event_id: int, teacher_score: float = 70.0) -> dict:
    dimensions = {key: teacher_score for key in DIMENSIONS}
    response = client.post(
        "/api/teacher/reviews",
        json={
            "evidence_event_id": event_id,
            "confirmed_dimensions": dimensions,
            "comment": "教师复核",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_rule_fallback_review_does_not_claim_an_ai_baseline(client, db_factory):
    db = db_factory()
    event = _scored_session(
        db,
        evaluation_mode="rule_fallback",
        degraded=True,
        ai_score=None,
        total=72.6,
        rule_score=72.6,
    )
    event_id = event.id
    db.close()

    _teacher(client, db_factory)
    payload = _submit_review(client, event_id, teacher_score=73.7)

    # The compared number is the rule score, and it says so.
    assert payload["baseline_score"] == pytest.approx(72.6)
    assert payload["baseline_source"] == "rule_fallback"
    assert payload["baseline_source_label"] == "规则降级评分（非 AI）"
    # No model produced this score, so the AI column must stay empty rather
    # than being filled with the rule total.
    assert payload["ai_score"] is None
    assert payload["agreement_delta"] == pytest.approx(1.1)

    # The stored row agrees with the response.
    db = db_factory()
    review = db.query(TeacherScoreReview).one()
    assert review.ai_score is None
    assert review.baseline_score == pytest.approx(72.6)
    assert review.baseline_source == "rule_fallback"
    db.close()


def test_ai_review_records_the_ai_baseline(client, db_factory):
    db = db_factory()
    event = _scored_session(
        db,
        evaluation_mode="ai",
        degraded=False,
        ai_score=78.0,
        total=76.0,
        rule_score=70.0,
    )
    event_id = event.id
    db.close()

    _teacher(client, db_factory)
    payload = _submit_review(client, event_id, teacher_score=80.0)

    assert payload["baseline_score"] == pytest.approx(78.0)
    assert payload["baseline_source"] == "ai"
    assert payload["ai_score"] == pytest.approx(78.0)
    assert payload["agreement_delta"] == pytest.approx(2.0)


def test_degraded_flag_wins_over_a_stale_ai_score(client, db_factory):
    """A degraded evaluation is a rule result even if a partial AI score exists."""

    db = db_factory()
    event = _scored_session(
        db,
        evaluation_mode="ai",
        degraded=True,
        ai_score=90.0,
        total=61.0,
        rule_score=61.0,
    )
    event_id = event.id
    db.close()

    _teacher(client, db_factory)
    payload = _submit_review(client, event_id, teacher_score=64.0)

    assert payload["baseline_source"] == "rule_fallback"
    assert payload["baseline_score"] == pytest.approx(61.0)


def test_reviewable_evidence_exposes_the_baseline_source(client, db_factory):
    db = db_factory()
    rule_event = _scored_session(
        db, evaluation_mode="rule_fallback", degraded=True, ai_score=None, total=72.6
    )
    ai_event = _scored_session(
        db, evaluation_mode="ai", degraded=False, ai_score=78.0, total=76.0
    )
    rule_id, ai_id = rule_event.id, ai_event.id
    db.close()

    _teacher(client, db_factory)
    rows = {row["evidence_event_id"]: row for row in client.get("/api/teacher/reviewable-evidence").json()}

    assert rows[rule_id]["baseline_source"] == "rule_fallback"
    assert rows[rule_id]["ai_score"] is None
    assert rows[rule_id]["baseline_score"] == pytest.approx(72.6)
    assert rows[rule_id]["evaluation_mode"] == "rule_fallback"
    assert rows[rule_id]["degraded"] is True

    assert rows[ai_id]["baseline_source"] == "ai"
    assert rows[ai_id]["ai_score"] == pytest.approx(78.0)
    assert rows[ai_id]["baseline_score"] == pytest.approx(78.0)


def test_review_list_labels_each_row(client, db_factory):
    db = db_factory()
    event = _scored_session(
        db, evaluation_mode="rule_fallback", degraded=True, ai_score=None, total=72.6
    )
    event_id = event.id
    db.close()

    _teacher(client, db_factory)
    _submit_review(client, event_id)

    rows = client.get("/api/teacher/reviews").json()
    assert len(rows) == 1
    assert rows[0]["baseline_source"] == "rule_fallback"
    assert rows[0]["baseline_source_label"] == "规则降级评分（非 AI）"


def test_legacy_rows_are_labelled_ambiguous_not_guessed():
    """History cannot be reconstructed, so the label says so.

    The migration sets ``baseline_source='legacy_ambiguous'`` on pre-existing
    rows. This test pins the label mapping itself, because a future refactor
    must not quietly rename history to "ai".
    """

    from app.services.display_labels import BASELINE_SOURCE_LABELS

    assert set(BASELINE_SOURCE_LABELS) == {"ai", "rule_fallback", "legacy_ambiguous"}
    assert "无法区分" in BASELINE_SOURCE_LABELS["legacy_ambiguous"]
    assert "AI" in BASELINE_SOURCE_LABELS["ai"]
    assert "非 AI" in BASELINE_SOURCE_LABELS["rule_fallback"]


def test_agreement_statistics_never_pool_rule_and_ai_baselines(client, db_factory):
    """The point of the split: a pooled 'agreement' number would be meaningless.

    With one AI baseline and one rule baseline, a caller grouping by
    ``baseline_source`` gets two separate comparisons instead of one.
    """

    db = db_factory()
    rule_event = _scored_session(
        db, evaluation_mode="rule_fallback", degraded=True, ai_score=None, total=72.6
    )
    ai_event = _scored_session(
        db, evaluation_mode="ai", degraded=False, ai_score=78.0, total=76.0
    )
    rule_id, ai_id = rule_event.id, ai_event.id
    db.close()

    _teacher(client, db_factory)
    _submit_review(client, rule_id, teacher_score=73.7)
    _submit_review(client, ai_id, teacher_score=80.0)

    rows = client.get("/api/teacher/reviews").json()
    by_source: dict[str, list[float]] = {}
    for row in rows:
        by_source.setdefault(row["baseline_source"], []).append(row["agreement_delta"])

    assert set(by_source) == {"rule_fallback", "ai"}
    assert by_source["rule_fallback"] == pytest.approx([1.1])
    assert by_source["ai"] == pytest.approx([2.0])
