"""Students must not be able to read answer keys or grading checklists from the API.

The rule-based quiz and the skill scorer both grade server-side, so hiding these
fields changes nothing about learning outcomes — it only removes the shortcut.
"""

from app.auth import hash_password
from app.models import ClinicalSkill, KnowledgeUnit, Teacher, User
from app.services.serializers import dumps_json

from tests.factories import make_student

ANSWER_KEYWORDS = ["狼疮肾炎", "抗dsDNA"]
SKILL_RUBRIC = {"preparation": "能说明目的并保护隐私。", "safety": "动作轻柔。"}


def _seed(db_factory):
    db = db_factory()
    unit = KnowledgeUnit(
        title="SLE核心知识",
        category="基础",
        level="基础",
        learning_objectives=dumps_json(["识别核心表现"]),
        content="内容",
        key_points=dumps_json(["要点"]),
        quiz_items=dumps_json(
            [{"question": "哪些指标支持SLE活动？", "answer_keywords": ANSWER_KEYWORDS}]
        ),
        related_case_ids=dumps_json([]),
    )
    db.add(unit)
    db.add(
        ClinicalSkill(
            title="关节查体",
            category="查体",
            difficulty="基础",
            indication="关节痛",
            contraindication="无",
            steps=dumps_json(["视诊", "触诊"]),
            common_errors=dumps_json(["顺序错误"]),
            scoring_rubric=dumps_json(SKILL_RUBRIC),
        )
    )
    make_student(db, username="learner")
    teacher = Teacher(name="Teacher", teacher_no="T001", department="Medicine")
    db.add(teacher)
    db.flush()
    db.add(User(username="teacher", password_hash=hash_password("secret1"), role="teacher", teacher_id=teacher.id))
    db.commit()
    unit_id = unit.id
    db.close()
    return unit_id


def test_student_knowledge_detail_hides_answer_keys(db_factory, client):
    unit_id = _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200

    response = client.get(f"/api/knowledge/{unit_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["quiz_items"][0]["question"]
    assert "answer_keywords" not in payload["quiz_items"][0]
    for keyword in ANSWER_KEYWORDS:
        assert keyword not in response.text


def test_teacher_knowledge_detail_keeps_answer_keys(db_factory, client):
    unit_id = _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "teacher", "password": "secret1"}).status_code == 200
    payload = client.get(f"/api/knowledge/{unit_id}").json()
    assert payload["quiz_items"][0]["answer_keywords"] == ANSWER_KEYWORDS


def test_student_skill_detail_hides_the_checklist(db_factory, client):
    _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200

    response = client.get("/api/skills/1")
    assert response.status_code == 200
    payload = response.json()
    assert "scoring_rubric" not in payload
    assert payload["steps"] and payload["common_errors"]
    for value in SKILL_RUBRIC.values():
        assert value not in response.text


def test_teacher_skill_detail_keeps_the_checklist(db_factory, client):
    _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "teacher", "password": "secret1"}).status_code == 200
    payload = client.get("/api/skills/1").json()
    assert payload["scoring_rubric"] == SKILL_RUBRIC


def test_quiz_still_grades_server_side_without_exposing_keys(db_factory, client):
    unit_id = _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200

    correct = client.post(f"/api/knowledge/{unit_id}/quiz", json={"answers": ["抗dsDNA和补体下降"]}).json()
    wrong = client.post(f"/api/knowledge/{unit_id}/quiz", json={"answers": ["我不知道"]}).json()
    assert correct["quiz_score"] > wrong["quiz_score"]
