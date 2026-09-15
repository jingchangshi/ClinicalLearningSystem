"""Systematic leak sweep: no hidden field value may appear in any student response.

This turns the "serialize_detail vs serialize_summary" class of bug into a durable
invariant: every student-reachable endpoint is called and the whole response body
is scanned for the markers that only teachers may read.
"""

from app.auth import hash_password
from app.models import (
    Case,
    ClinicalSkill,
    GuidelineDocument,
    KnowledgeUnit,
    SPCase,
    Teacher,
    User,
)
from app.services.serializers import dumps_json

from tests.factories import ANSWER_TEXTS, make_student

SECRETS = {
    "标准诊断": "SECRETDXALPHA",
    "标准治疗": "SECRETTXALPHA",
    "病例量规": "SECRETRUBRICALPHA",
    "鉴别诊断": "SECRETDDXALPHA",
    "SP隐藏病史": "SECRETSPHISTORYALPHA",
    "SP评分量规": "SECRETSPRUBRICALPHA",
    "测验答案": "SECRETQUIZKEYALPHA",
    "技能检查表": "SECRETSKILLRUBRICALPHA",
}


def _seed(db_factory) -> dict:
    db = db_factory()
    case = Case(
        title="泄漏扫描病例",
        disease_category="SLE",
        difficulty="基础",
        learning_objectives=dumps_json(["关键信息提取"]),
        chief_complaint="发热",
        history="反复发热。",
        physical_exam="皮疹。",
        lab_results="ANA阳性。",
        imaging="未见异常。",
        standard_diagnosis=SECRETS["标准诊断"],
        differential_diagnosis=dumps_json([SECRETS["鉴别诊断"]]),
        treatment_plan=SECRETS["标准治疗"],
        rubric=dumps_json({"medical_knowledge": SECRETS["病例量规"]}),
    )
    sp_case = SPCase(
        title="泄漏扫描问诊",
        disease_category="SLE",
        difficulty="基础",
        patient_profile=dumps_json({"age": 30}),
        opening_statement="医生我发热。",
        hidden_history=dumps_json({"fever": SECRETS["SP隐藏病史"]}),
        emotional_style="平静",
        expected_tasks=dumps_json(["问诊"]),
        scoring_rubric=dumps_json({"history_taking": SECRETS["SP评分量规"]}),
    )
    unit = KnowledgeUnit(
        title="泄漏扫描知识",
        category="基础",
        level="基础",
        learning_objectives=dumps_json(["识别"]),
        content="内容",
        key_points=dumps_json(["要点"]),
        quiz_items=dumps_json([{"question": "问题？", "answer_keywords": [SECRETS["测验答案"]]}]),
        related_case_ids=dumps_json([]),
    )
    skill = ClinicalSkill(
        title="泄漏扫描技能",
        category="查体",
        difficulty="基础",
        indication="评估",
        contraindication="无",
        steps=dumps_json(["步骤一"]),
        common_errors=dumps_json(["错误一"]),
        scoring_rubric=dumps_json({"safety": SECRETS["技能检查表"]}),
    )
    guideline = GuidelineDocument(
        title="泄漏扫描指南",
        organization="EULAR",
        year=2023,
        disease_category="SLE",
        source_type="指南",
        summary="摘要",
        recommendations=dumps_json([{"text": "推荐", "grade": "A"}]),
        pico_examples=dumps_json([{"p": "人群", "i": "干预", "c": "对照", "o": "结局"}]),
    )
    db.add_all([case, sp_case, unit, skill, guideline])
    student, _ = make_student(db, username="learner")
    teacher = Teacher(name="Teacher", teacher_no="T001", department="Medicine")
    db.add(teacher)
    db.flush()
    db.add(User(username="teacher", password_hash=hash_password("secret1"), role="teacher", teacher_id=teacher.id))
    db.commit()
    ids = {
        "case": case.id,
        "sp_case": sp_case.id,
        "unit": unit.id,
        "skill": skill.id,
        "guideline": guideline.id,
        "student": student.id,
    }
    db.close()
    return ids


def _assert_clean(response, label: str, allow: set[str] | None = None) -> None:
    assert response.status_code < 400, f"{label} returned {response.status_code}"
    body = response.text
    leaked = [
        name
        for name, marker in SECRETS.items()
        if marker in body and name not in (allow or set())
    ]
    assert not leaked, f"{label} leaked {leaked}"


def test_no_student_endpoint_leaks_hidden_material(db_factory, client):
    ids = _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200

    catalog_calls = [
        ("cases list", "/api/cases"),
        ("case detail", f"/api/cases/{ids['case']}"),
        ("sp list", "/api/sp-cases"),
        ("sp detail", f"/api/sp-cases/{ids['sp_case']}"),
        ("knowledge list", "/api/knowledge"),
        ("knowledge detail", f"/api/knowledge/{ids['unit']}"),
        ("skill list", "/api/skills"),
        ("skill detail", f"/api/skills/{ids['skill']}"),
        ("guideline list", "/api/guidelines"),
        ("guideline detail", f"/api/guidelines/{ids['guideline']}"),
        ("student dashboard", "/api/student/dashboard"),
        ("student pathway", "/api/student/pathway"),
        ("student competency", "/api/student/competency"),
        ("student knowledge progress", "/api/student/knowledge-progress"),
        ("student self", "/api/student/me"),
        ("students list", "/api/students"),
        ("student by id", f"/api/students/{ids['student']}"),
        ("student dashboard by id", f"/api/students/{ids['student']}/dashboard"),
        ("student pathway by id", f"/api/students/{ids['student']}/pathway"),
        ("student competency by id", f"/api/students/{ids['student']}/competency"),
    ]
    for label, path in catalog_calls:
        _assert_clean(client.get(path), label)

    # Training flows: session payload, coach/tutor output and the result page.
    session_id = client.post("/api/sessions/start", json={"case_id": ids["case"]}).json()["id"]
    _assert_clean(client.get(f"/api/sessions/{session_id}"), "session detail")
    for step, text in ANSWER_TEXTS.items():
        client.post(f"/api/sessions/{session_id}/answers", json={"step": step, "answer_text": text})
    _assert_clean(
        client.post(f"/api/sessions/{session_id}/tutor", json={"step": "treatment"}),
        "tutor turn",
    )
    _assert_clean(
        client.post(
            f"/api/sessions/{session_id}/coach",
            json={"step": "key_information", "answer_text": ANSWER_TEXTS["key_information"]},
        ),
        "coach question",
    )
    client.post(f"/api/sessions/{session_id}/submit")
    _assert_clean(client.get(f"/api/sessions/{session_id}/result"), "case result")

    # SP encounter + its result payload.
    sp_session_id = client.post("/api/sp-sessions/start", json={"sp_case_id": ids["sp_case"]}).json()["session_id"]
    # The simulated patient revealing hidden history *when asked* is the exercise,
    # not a leak: only that one marker may appear in the reply.
    _assert_clean(
        client.post(f"/api/sp-sessions/{sp_session_id}/message", json={"message": "发热多久了？"}),
        "sp message",
        allow={"SP隐藏病史"},
    )
    client.post(
        f"/api/sp-sessions/{sp_session_id}/submit",
        json={"diagnosis_summary": "考虑感染与自身免疫病鉴别。"},
    )
    # The result carries the student's own transcript, which legitimately echoes
    # what the patient disclosed during the encounter.
    _assert_clean(
        client.get(f"/api/sp-sessions/{sp_session_id}/result"),
        "sp result",
        allow={"SP隐藏病史"},
    )

    # Knowledge quiz + skill + guideline submissions.
    _assert_clean(
        client.post(f"/api/knowledge/{ids['unit']}/quiz", json={"answers": ["抗dsDNA升高"]}),
        "knowledge quiz",
    )
    skill_session = client.post(f"/api/skills/{ids['skill']}/sessions/start", json={}).json()
    skill_session_id = skill_session["id"]
    _assert_clean(
        client.post(f"/api/skill-sessions/{skill_session_id}/submit", json={"submitted_steps": ["步骤一"]}),
        "skill submit",
    )
    _assert_clean(
        client.post(
            f"/api/guidelines/{ids['guideline']}/pico",
            json={
                "clinical_question": "活动性SLE如何治疗？",
                "pico": "P: 活动性SLE；I: 羟氯喹；C: 单用激素；O: 复发率",
                "answer": "推荐联合治疗。",
            },
        ),
        "guideline pico",
    )


def test_teacher_endpoints_still_return_hidden_material(db_factory, client):
    """The sweep must be meaningful: the same markers are visible to a teacher."""

    ids = _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "teacher", "password": "secret1"}).status_code == 200

    case_body = client.get(f"/api/teacher/cases").text
    assert SECRETS["标准诊断"] in case_body
    sp_body = client.get(f"/api/sp-cases/{ids['sp_case']}").text
    assert SECRETS["SP隐藏病史"] in sp_body
    unit_body = client.get(f"/api/knowledge/{ids['unit']}").text
    assert SECRETS["测验答案"] in unit_body


def test_sp_disclosure_is_question_driven_not_a_dump(db_factory, client):
    """Asking something unrelated must not return the whole hidden history."""

    ids = _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200
    session_id = client.post("/api/sp-sessions/start", json={"sp_case_id": ids["sp_case"]}).json()["session_id"]

    reply = client.post(
        f"/api/sp-sessions/{session_id}/message",
        json={"message": "您好，请问您今年多大年纪？"},
    ).text
    assert SECRETS["SP隐藏病史"] not in reply
    assert SECRETS["SP评分量规"] not in reply
