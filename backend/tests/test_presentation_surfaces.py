"""Display semantics for the teacher/student surfaces a teacher actually reads.

These are the regressions behind "the page shows stage_1_basic_recognition":
the API must hand the UI Chinese business labels, and the historical read paths
must stay historical — no model call, no hidden answer.
"""

import json

import pytest

from app.auth import create_access_token
from app.models import (
    CaseSession,
    CompetencyProfile,
    LearningEvidenceEvent,
    Score,
    Student,
    StudentAnswer,
    TutorTurn,
    User,
)
from app.services.serializers import dumps_json
from tests.factories import make_case, make_catalog, make_student


def _login(client, db_factory, *, username: str, student_id: int | None = None, role: str = "student") -> None:
    """Sign in as an existing account, or create a staff account if there is none."""

    db = db_factory()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            user = User(username=username, password_hash="x", role=role, student_id=student_id)
            db.add(user)
            db.commit()
        token = create_access_token(user)
    finally:
        db.close()
    client.cookies.set("access_token", token)


def _completed_case_session(db, student, *, case_id: int = 1, tutor_reply: str = "补体下降提示疾病活动。"):
    """A finished case: five answers, a two-turn tutor exchange, one score."""

    session = CaseSession(student_id=student.id, case_id=case_id, status="completed")
    session.completed_at = session.started_at
    db.add(session)
    db.flush()
    steps = [
        "key_information",
        "initial_diagnosis",
        "differential_diagnosis",
        "examination",
        "treatment",
    ]
    for index, step in enumerate(steps):
        db.add(StudentAnswer(session_id=session.id, step=step, answer_text=f"{step} 的回答 {index}"))
    db.add(
        TutorTurn(
            session_id=session.id,
            step="key_information",
            turn_index=0,
            role="tutor",
            message="为什么蛋白尿比关节痛更值得优先评估？",
            tutor_state_json=dumps_json({"internal": "never exposed"}),
        )
    )
    db.add(
        TutorTurn(
            session_id=session.id,
            step="key_information",
            turn_index=1,
            role="student",
            message=tutor_reply,
            tutor_state_json="{}",
        )
    )
    db.add(
        TutorTurn(
            session_id=session.id,
            step="key_information",
            turn_index=2,
            role="tutor",
            message="那补体下降如何影响你的鉴别排序？",
            tutor_state_json=dumps_json({"internal": "never exposed"}),
        )
    )
    db.add(
        Score(
            session_id=session.id,
            total_score=72.5,
            medical_knowledge=70,
            key_information=74,
            differential_diagnosis=71,
            evidence_integration=69,
            clinical_decision=75,
            evidence_based_medicine=66,
            feedback="整体方向正确。",
            strengths="诊断方向正确",
            weaknesses="循证依据不足",
            evaluation_mode="ai",
            model="deepseek-flash",
            ai_score=72.5,
            rule_score=70.0,
            degraded=False,
            evaluation_detail_json=dumps_json({"dimensions": {}}),
        )
    )
    db.commit()
    return session


def _seed_learning_evidence(db, student, *, session_id: int | None = None) -> LearningEvidenceEvent:
    event = LearningEvidenceEvent(
        student_id=student.id,
        module_type="case",
        module_id=None,
        session_id=session_id,
        event_type="case_session_scored",
        source_table="case_sessions",
        source_id=1,
        score=72.5,
        competency_updates_json=dumps_json(
            {"differential_diagnosis": {"before": 58, "after": 64, "delta": 6, "module_score": 78}}
        ),
        evidence_payload_json=dumps_json({"notice": "never exposed"}),
    )
    db.add(event)
    db.commit()
    return event


# --- Stage and module semantics -------------------------------------------


def test_serialized_student_carries_a_chinese_stage_label(db_factory):
    from app.services.display_labels import stage_label
    from app.services.serializers import serialize_student

    db = db_factory()
    student, _ = make_student(db)
    db.commit()

    payload = serialize_student(student)

    assert payload["current_stage"] == "stage_1_basic_recognition"
    assert payload["current_stage_label"] == "阶段1：基础疾病识别"
    assert stage_label("stage_1_basic_recognition") == "阶段1：基础疾病识别"
    assert stage_label("stage_3_clinical_decision") == "阶段3：临床决策训练"
    assert stage_label("stage_4_evidence_based_learning") == "阶段4：循证医学与文献训练"
    db.close()


def test_legacy_stage_key_still_renders_a_business_label():
    from app.services.display_labels import stage_label

    assert stage_label("stage_1_basic_knowledge") == "阶段1：基础疾病识别"
    assert stage_label("something_new") == "something_new"


def test_module_and_event_labels_cover_the_catalog_keys():
    from app.services.display_labels import event_label, module_label

    assert module_label("case") == "病例推理训练"
    assert module_label("knowledge") == "基础知识学习"
    assert module_label("clinical_skill") == "临床技能训练"
    assert module_label("sp_case") == "SP模拟问诊"
    assert event_label("case_session_scored") == "病例推理训练完成"
    assert event_label("teacher_score_confirmed") == "教师评分确认"


def test_teacher_dashboard_student_rows_use_the_stage_label(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _ = make_student(db, name="学习者")
    db.commit()
    db.close()

    _login(client, db_factory, username="teacher1", student_id=None, role="teacher")
    payload = client.get("/api/teacher/dashboard").json()

    row = payload["students"][0]
    assert row["current_stage_label"] == "阶段1：基础疾病识别"
    assert row["name"] == "学习者"


# --- Evidence and growth trend semantics ----------------------------------


def test_evidence_events_are_readable_and_hide_internal_pointers(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _ = make_student(db, name="学习者")
    db.commit()
    session = _completed_case_session(db, student)
    _seed_learning_evidence(db, student, session_id=session.id)
    session_id = session.id
    student_id = student.id
    db.close()

    _login(client, db_factory, username="teacher2", role="teacher")
    payload = client.get(f"/api/teacher/students/{student_id}/learning-profile").json()

    event = payload["evidence_events"][0]
    assert event["module_label"] == "病例推理训练"
    assert event["event_label"] == "病例推理训练完成"
    assert event["activity_title"] == "SLE基础病例"
    assert event["competency_changes"] == [
        {
            "key": "differential_diagnosis",
            "label": "鉴别诊断",
            "before": 58,
            "after": 64,
            "delta": 6,
        }
    ]
    # Internal pointers and raw evidence payloads stay server-side.
    assert "source_table" not in event
    assert "source_id" not in event
    assert "evidence_payload" not in event
    assert "competency_updates" not in event
    assert json.dumps(payload, ensure_ascii=False).find("case_sessions") == -1
    assert session_id  # the event still points at a real session server-side


def test_growth_trend_is_a_time_series_that_excludes_provenance_events(db_factory):
    from app.services.learning_evidence_service import build_growth_trend

    db = db_factory()
    student, _ = make_student(db)
    db.commit()
    _seed_learning_evidence(db, student)
    db.add(
        LearningEvidenceEvent(
            student_id=student.id,
            module_type="case",
            module_id=None,
            session_id=None,
            event_type="teacher_score_confirmed",
            source_table="teacher_score_reviews",
            source_id=1,
            score=65,
            competency_updates_json="{}",
            evidence_payload_json="{}",
        )
    )
    db.commit()

    trend = build_growth_trend(db, student.id)

    assert len(trend) == 1
    point = trend[0]
    assert point["module_label"] == "病例推理训练"
    assert point["score"] == 72.5
    assert point["competency_changes"][0]["label"] == "鉴别诊断"
    assert "average_after" not in point, "an undefined aggregate must not be shown as a growth index"
    db.close()


# --- Student history and case review --------------------------------------


def test_student_history_lists_completed_cases_with_their_evidence(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _ = make_student(db, name="学习者", username="learner")
    db.commit()
    session = _completed_case_session(db, student)
    session_id = session.id
    db.close()

    _login(client, db_factory, username="learner", student_id=None)
    payload = client.get("/api/student/history").json()

    assert payload["count"] == 1
    item = payload["items"][0]
    assert item["session_id"] == session_id
    assert item["case_title"] == "SLE基础病例"
    assert item["status_label"] == "已完成"
    assert item["total_score"] == 72.5
    assert item["evaluation_mode"] == "ai"
    assert item["tutor_turn_count"] == 3
    assert item["answer_count"] == 5


def test_result_carries_the_five_step_review_with_the_tutor_transcript(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _ = make_student(db, name="学习者", username="learner")
    db.commit()
    session = _completed_case_session(db, student)
    session_id = session.id
    db.close()

    _login(client, db_factory, username="learner", student_id=None)
    payload = client.get(f"/api/sessions/{session_id}/result").json()

    review = payload["reasoning_review"]
    assert [step["step_title"] for step in review] == [
        "关键信息提取",
        "初步诊断及依据",
        "鉴别诊断",
        "进一步检查",
        "治疗方案",
    ]
    key_information = review[0]
    assert key_information["answer_text"] == "key_information 的回答 0"
    assert [turn["role"] for turn in key_information["tutor_turns"]] == ["tutor", "student", "tutor"]
    assert [turn["message"] for turn in key_information["tutor_turns"]] == [
        "为什么蛋白尿比关节痛更值得优先评估？",
        "补体下降提示疾病活动。",
        "那补体下降如何影响你的鉴别排序？",
    ]
    assert review[1]["tutor_turns"] == []


def test_history_and_result_never_leak_answers_or_tutor_state(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _ = make_student(db, name="学习者", username="learner")
    db.commit()
    session = _completed_case_session(db, student)
    session_id = session.id
    db.close()

    _login(client, db_factory, username="learner", student_id=None)
    history = client.get("/api/student/history").json()
    result = client.get(f"/api/sessions/{session_id}/result").json()

    forbidden_keys = {
        "standard_diagnosis",
        "treatment_plan",
        "rubric",
        "hidden_history",
        "tutor_state",
        "tutor_state_json",
        "evidence_payload",
        "source_table",
    }
    # ``provider`` / ``model`` stay: the learner must be able to see whether a
    # real model scored the case (invariant 3), which is the opposite of a leak.
    assert not (forbidden_keys & _all_keys(history))
    assert not (forbidden_keys & _all_keys(result))

    # No hidden value may survive in a non-key position either.
    body = json.dumps([history, result], ensure_ascii=False)
    assert "系统性红斑狼疮" not in body  # the hidden standard diagnosis
    assert "激素联合免疫抑制剂" not in body  # the hidden treatment plan
    assert "never exposed" not in body  # the stored tutor reasoning state


def _all_keys(payload) -> set[str]:
    if isinstance(payload, dict):
        return set(payload) | {key for value in payload.values() for key in _all_keys(value)}
    if isinstance(payload, list):
        return {key for item in payload for key in _all_keys(item)}
    return set()


def test_a_student_cannot_read_another_students_history(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    owner, _ = make_student(db, name="本人", username="learner")
    other, _ = make_student(db, name="他人", username="other")
    db.commit()
    session = _completed_case_session(db, owner)
    other_session = _completed_case_session(db, other)
    owner_session_id = session.id
    other_session_id = other_session.id
    db.close()

    _login(client, db_factory, username="learner", student_id=None)

    # The list is scoped by the token, not by anything the client sends.
    history = client.get("/api/student/history").json()
    assert [item["session_id"] for item in history["items"]] == [owner_session_id]
    assert client.get(f"/api/sessions/{other_session_id}/result").status_code == 403
    assert client.get(f"/api/sessions/{owner_session_id}/result").status_code == 200


def test_anonymous_visitors_are_refused(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _ = make_student(db, name="学习者", username="learner")
    db.commit()
    session = _completed_case_session(db, student)
    session_id = session.id
    db.close()

    assert client.get("/api/student/history").status_code == 401
    assert client.get(f"/api/sessions/{session_id}/result").status_code == 401


def test_result_requires_a_score(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _ = make_student(db, name="学习者", username="learner")
    db.commit()
    session = CaseSession(student_id=student.id, case_id=1)
    db.add(session)
    db.commit()
    session_id = session.id
    db.close()

    _login(client, db_factory, username="learner", student_id=None)
    assert client.get(f"/api/sessions/{session_id}/result").status_code == 404


# --- Research export ------------------------------------------------------


def _seed_research_rows(db, student, *, count: int):
    modules = [
        ("knowledge", "knowledge_quiz_submitted"),
        ("case", "case_session_scored"),
        ("guideline", "guideline_pico_submitted"),
    ]
    for index in range(count):
        module_type, event_type = modules[index % len(modules)]
        db.add(
            LearningEvidenceEvent(
                student_id=student.id,
                module_type=module_type,
                module_id=None,
                session_id=None,
                event_type=event_type,
                source_table="synthetic",
                source_id=index + 1,
                score=60 + index,
                competency_updates_json=dumps_json({"medical_knowledge": {"before": 60, "after": 61}}),
                evidence_payload_json="{}",
            )
        )
    db.commit()


def test_research_export_keeps_anonymity_and_offers_a_preview(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _ = make_student(db, name="学习者")
    db.commit()
    _seed_research_rows(db, student, count=30)
    db.close()

    _login(client, db_factory, username="teacher3", student_id=None, role="teacher")
    payload = client.get("/api/teacher/export/research-data").json()

    assert payload["anonymous"] is True
    assert len(payload["rows"]) == 30
    assert "name" not in payload["rows"][0]
    assert payload["rows"][0]["student_code"].startswith("S")
    assert payload["rows"][0]["module_label"] == "基础知识学习"

    summary = payload["summary"]
    assert summary["student_count"] == 1
    assert summary["record_count"] == 30
    assert summary["preview_limit"] == 20
    assert len(payload["preview_rows"]) == 20
    assert set(summary["module_labels"]) == {"基础知识学习", "病例推理训练", "指南循证学习"}


def test_research_export_csv_is_excel_friendly_and_complete(db_factory, client):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    student, _ = make_student(db, name="学习者")
    db.commit()
    _seed_research_rows(db, student, count=25)
    db.close()

    _login(client, db_factory, username="teacher4", student_id=None, role="teacher")
    response = client.get("/api/teacher/export/research-data.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    text = response.text
    assert text.startswith("\ufeff")
    assert "匿名学生编号,班级,学习模块,训练得分,记录时间" in text
    # Header + every record, and no student name anywhere.
    assert len(text.strip().splitlines()) == 26
    assert "学习者" not in text


@pytest.mark.parametrize("path", ["/api/teacher/export/research-data.csv"])
def test_research_export_is_teacher_only(db_factory, client, path):
    db = db_factory()
    make_case(db)
    make_catalog(db)
    make_student(db, name="学习者")
    db.commit()
    db.close()

    assert client.get(path).status_code == 401
