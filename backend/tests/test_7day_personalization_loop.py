"""End-to-end validation of the 7-day personalisation loop (round 4, T3).

The study's 7-day cycle is: D1 T0 assessment -> D2-D3 basic-case training ->
D4-D5 weakness-driven reinforcement + teacher feedback -> D6 T1 assessment -> D7
feedback. D1 (T0) is an *independent* assessment whose papers are scored by the
blinded raters only after D6, so T0 never feeds the ClinPath competency profile.
The profile that drives the D4-D5 personalisation is produced by the **D2/D3
training** submissions.

This file walks one *training* case submission through the real route code and
checks the four links the protocol claims are connected:

  1. training submit -> a six-dimension formative score, in BOTH the ``ai`` and
     the ``rule_fallback`` paths;
  2. that score -> ``competency_profiles`` (``UPDATE_WEIGHT = 0.3``);
  3. weakest abilities -> a per-student ``LearningRecommendation``, and two
     students with different weaknesses get different recommendations;
  4. a teacher can read the profile behind the weakness and record an
     intervention that then appears in the interventions list.

Deterministic and offline: the suite runs with ``LLM_*`` unset, so the real
scoring path is ``rule_fallback``. Where a test needs a controlled weakness
profile it injects a fixed score payload into the submit route's scoring call —
the route wiring (competency update, recommendation write, evidence event) is
still the production code.
"""

import json

import pytest

from app.auth import create_access_token
from app.models import (
    Case,
    LearningEvidenceEvent,
    LearningRecommendation,
    Score,
    Student,
    User,
)
from app.services.competency_update_service import UPDATE_WEIGHT
from app.services.scoring_llm import WEIGHTS, evaluate_case_submission
from app.services.serializers import CORE_ABILITIES, dumps_json
from tests.factories import ANSWER_TEXTS, make_case, make_catalog, make_student

BASELINE = 60.0  # what ``make_student`` writes for every core dimension

REASON_BY_DIMENSION = {
    "medical_knowledge": "医学知识基础需要巩固",
    "key_information": "关键信息提取需要更系统",
    "differential_diagnosis": "鉴别诊断链条需要拓宽",
    "evidence_integration": "证据整合和反证处理需要强化",
    "clinical_decision": "治疗决策和监测计划需要训练",
    "evidence_based_medicine": "循证医学意识需要提升",
}


class _FakeLLM:
    """Stand-in for ``llm_service`` at the scoring boundary."""

    def __init__(self, payload):
        self.payload = payload

    def chat_json(self, system_prompt, user_prompt, fallback, task_type=None):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def _ai_payload() -> dict:
    return {
        "dimensions": {
            key: {
                "score": 72,
                "confidence": 0.7,
                "evidence": ["学生提到了发热"],
                "missing_points": [],
                "feedback": "继续补充证据",
            }
            for key in CORE_ABILITIES
        },
        "strengths": ["推理链条清晰"],
        "priority_gaps": ["证据权重不足"],
        "overall_feedback": "整体尚可。",
        "safety_flags": [],
    }


def _score_payload(weak: str, weak_score: float = 40.0, strong: float = 80.0) -> dict:
    """A six-dimension score whose named dimension is the weakest."""

    scores = {key: strong for key in CORE_ABILITIES}
    scores[weak] = weak_score
    total = round(sum(scores[key] * WEIGHTS[key] for key in CORE_ABILITIES), 1)
    return {
        **scores,
        "total_score": total,
        "strengths": "s",
        "weaknesses": "w",
        "feedback": "f",
        "evaluation_mode": "rule_fallback",
        "degraded": True,
        "rule_score": total,
        "ai_score": None,
        "evaluation_detail": {"mode": "rule_fallback", "dimensions": {}},
    }


def _sign_in(client, db_factory, user_id: int) -> None:
    db = db_factory()
    try:
        user = db.get(User, user_id)
        token = create_access_token(user)
    finally:
        db.close()
    client.cookies.set("access_token", token)


def _submit_case(client, case_id: int) -> int:
    """The real five-step submission path: start -> answers -> submit."""

    started = client.post("/api/sessions/start", json={"case_id": case_id})
    assert started.status_code == 200, started.text
    session_id = started.json()["id"]
    for step, text in ANSWER_TEXTS.items():
        saved = client.post(
            f"/api/sessions/{session_id}/answers",
            json={"step": step, "answer_text": text},
        )
        assert saved.status_code == 200, saved.text
    submitted = client.post(f"/api/sessions/{session_id}/submit")
    assert submitted.status_code == 200, submitted.text
    return session_id


def _training_case(db, title: str, objectives: list[str], difficulty: str) -> Case:
    case = Case(
        title=title,
        disease_category="SLE",
        difficulty=difficulty,
        learning_objectives=dumps_json(objectives),
        chief_complaint="发热伴皮疹",
        history="反复发热、面部皮疹。",
        physical_exam="面部蝶形红斑。",
        lab_results="ANA阳性，补体降低。",
        imaging="胸部CT未见明显异常。",
        standard_diagnosis="系统性红斑狼疮",
        differential_diagnosis=dumps_json(["感染"]),
        treatment_plan="激素联合免疫抑制剂。",
        rubric=dumps_json({}),
    )
    db.add(case)
    db.flush()
    return case


# --- Link 1: the formative score carries the six dimensions -----------------


def test_training_scoring_produces_six_dimensions_in_both_paths():
    """``evaluate_case_submission`` returns all six CORE_ABILITIES either way."""

    case = {"title": "SLE基础病例", "standard_diagnosis": "系统性红斑狼疮"}
    answers = [{"step": step, "answer_text": text} for step, text in ANSWER_TEXTS.items()]

    rule = evaluate_case_submission(case, answers, {}, _FakeLLM({"_fallback": True}))
    assert rule["evaluation_mode"] == "rule_fallback"
    assert rule["degraded"] is True
    assert set(CORE_ABILITIES) <= set(rule)
    assert set(CORE_ABILITIES) <= set(rule["evaluation_detail"]["dimensions"])

    ai = evaluate_case_submission(case, answers, {}, _FakeLLM(_ai_payload()))
    assert ai["evaluation_mode"] == "ai"
    assert ai["degraded"] is False
    assert set(CORE_ABILITIES) <= set(ai)
    for key in CORE_ABILITIES:
        assert 0 <= rule[key] <= 100
        assert 0 <= ai[key] <= 100


# --- Links 2 + 3: training submission drives profile and recommendation -----


def test_training_submission_updates_profile_and_writes_recommendation(db_factory, client):
    db = db_factory()
    make_case(db)
    student, user = make_student(db, name="训练生", username="trainee")
    db.commit()
    student_id, user_id = student.id, user.id
    db.close()

    _sign_in(client, db_factory, user_id)
    session_id = _submit_case(client, 1)

    db = db_factory()
    score = db.query(Score).filter(Score.session_id == session_id).one()
    # The persisted formative score has all six dimensions.
    for key in CORE_ABILITIES:
        assert getattr(score, key) is not None, key

    profile = db.get(Student, student_id).competency_profile
    weakest = min(CORE_ABILITIES, key=lambda key: getattr(score, key))
    for key in CORE_ABILITIES:
        expected = round(BASELINE * (1 - UPDATE_WEIGHT) + getattr(score, key) * UPDATE_WEIGHT, 1)
        assert getattr(profile, key) == expected, key

    # The weakest dimension moved toward its module score by the documented weight.
    expected_delta = round(UPDATE_WEIGHT * (getattr(score, weakest) - BASELINE), 1)
    assert round(getattr(profile, weakest) - BASELINE, 1) == expected_delta

    # A per-student recommendation row was written, keyed to the weakest dimension.
    recommendation = (
        db.query(LearningRecommendation)
        .filter(LearningRecommendation.student_id == student_id)
        .one()
    )
    assert recommendation.recommended_case_id == 1
    assert recommendation.recommendation_reason.startswith(REASON_BY_DIMENSION[weakest])
    assert recommendation.pathway_stage

    # The learning evidence stays traceable to the session that produced it.
    event = (
        db.query(LearningEvidenceEvent)
        .filter(
            LearningEvidenceEvent.student_id == student_id,
            LearningEvidenceEvent.event_type == "case_session_scored",
        )
        .one()
    )
    assert event.session_id == session_id
    assert set(json.loads(event.competency_updates_json)) == set(CORE_ABILITIES)
    db.close()


def test_different_weaknesses_get_different_recommendations(db_factory, client, monkeypatch):
    """Two students whose training exposes different weaknesses get different tasks."""

    from app.routes import sessions as sessions_routes

    db = db_factory()
    knowledge_case = _training_case(db, "知识型病例", ["疾病识别与诊断标准"], "基础")
    reasoning_case = _training_case(db, "鉴别型病例", ["鉴别诊断与排除逻辑"], "进阶")
    student_a, user_a = make_student(db, name="甲", username="student_a")
    student_b, user_b = make_student(db, name="乙", username="student_b")
    db.commit()
    knowledge_id, reasoning_id = knowledge_case.id, reasoning_case.id
    student_a_id, user_a_id = student_a.id, user_a.id
    student_b_id, user_b_id = student_b.id, user_b.id
    db.close()

    payloads = {
        user_a_id: _score_payload("medical_knowledge"),
        user_b_id: _score_payload("differential_diagnosis"),
    }
    current = {"user": user_a_id}
    monkeypatch.setattr(
        sessions_routes,
        "score_student_answer",
        lambda case, answers, rubric: payloads[current["user"]],
    )

    _sign_in(client, db_factory, user_a_id)
    _submit_case(client, knowledge_id)

    current["user"] = user_b_id
    _sign_in(client, db_factory, user_b_id)
    _submit_case(client, reasoning_id)

    db = db_factory()
    rec_a = db.query(LearningRecommendation).filter_by(student_id=student_a_id).one()
    rec_b = db.query(LearningRecommendation).filter_by(student_id=student_b_id).one()

    # The weakness, not a shared default, decides which case is recommended.
    assert rec_a.recommended_case_id == knowledge_id
    assert rec_b.recommended_case_id == reasoning_id
    assert rec_a.recommended_case_id != rec_b.recommended_case_id
    assert rec_a.recommendation_reason != rec_b.recommendation_reason
    assert "医学知识" in rec_a.recommendation_reason
    assert "鉴别诊断" in rec_b.recommendation_reason
    db.close()


# --- Link 4: the teacher sees the basis and records an intervention ----------


def test_teacher_reads_profile_and_records_an_intervention(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, user = make_student(db, name="学习者", username="learner")
    db.commit()
    student_id, user_id = student.id, user.id
    db.close()

    _sign_in(client, db_factory, user_id)
    _submit_case(client, 1)

    db = db_factory()
    teacher = User(username="teacher_loop", password_hash="x", role="teacher")
    db.add(teacher)
    db.commit()
    teacher_id = teacher.id
    db.close()

    _sign_in(client, db_factory, teacher_id)

    profile = client.get(f"/api/teacher/students/{student_id}/learning-profile").json()
    assert profile["competency"]["evidence_based_medicine"] is not None
    # The teacher must see the recommendation basis: the tasks the weakness drove.
    assert profile["recommended_tasks"], "no recommended tasks behind the weakness"
    task = profile["recommended_tasks"][0]
    assert task["target_abilities"]
    assert task["source_evidence"]

    # The dashboard exposes the class weak-dimension view.
    dashboard = client.get("/api/teacher/dashboard").json()
    assert "weak_dimensions" in dashboard
    assert any(row["key"] in CORE_ABILITIES for row in dashboard["weak_dimensions"])

    created = client.post(
        "/api/teacher/interventions",
        json={
            "title": "循证医学证据等级小课",
            "target_ability": "evidence_based_medicine",
            "target_students": [student_id],
            "intervention_type": "micro_lesson",
            "description": "针对本轮训练暴露的循证医学短板。",
        },
    )
    assert created.status_code == 200, created.text
    new_id = created.json()["id"]

    rows = client.get("/api/teacher/interventions").json()
    row = next(item for item in rows if item["id"] == new_id)
    assert row["target_ability_label"] == "循证医学"
    assert row["intervention_type_label"] == "专题小课"
    assert row["target_students"] == [student_id]


# --- Assessment isolation ------------------------------------------------------
# The former xfail here ("an assessment session does not enter the formative
# profile") documented that /api/sessions has no assessment mode. Independent
# assessments no longer use that route at all: they live in their own domain
# (app/assessment, /api/assessments, assessment_* tables) and the isolation is
# proven positively in tests/test_assessment_isolation.py.
