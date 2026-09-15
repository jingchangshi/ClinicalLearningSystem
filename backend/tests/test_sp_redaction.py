"""The SP encounter must be discovered by asking, not by reading the API."""

from app.auth import hash_password
from app.models import SPCase, Teacher, User
from app.services.serializers import dumps_json

from tests.factories import make_student

HIDDEN_HISTORY = {"duration": "大概一个月", "fever": "多为低热38度", "pain": "双手小关节疼"}
SCORING_RUBRIC = {"history_taking": "覆盖主诉与系统回顾。", "communication": "清晰并回应焦虑。"}


def _seed(db_factory, student_username="learner"):
    db = db_factory()
    sp_case = SPCase(
        title="发热皮疹问诊",
        disease_category="SLE",
        difficulty="基础",
        patient_profile=dumps_json({"age": 21, "gender": "女"}),
        opening_statement="医生，我最近总是低烧。",
        hidden_history=dumps_json(HIDDEN_HISTORY),
        emotional_style="焦虑",
        expected_tasks=dumps_json(["问清发热特点"]),
        scoring_rubric=dumps_json(SCORING_RUBRIC),
    )
    db.add(sp_case)
    make_student(db, username=student_username)
    teacher = Teacher(name="Teacher", teacher_no="T001", department="Medicine")
    db.add(teacher)
    db.flush()
    db.add(User(username="teacher", password_hash=hash_password("secret1"), role="teacher", teacher_id=teacher.id))
    db.commit()
    sp_case_id = sp_case.id
    db.close()
    return sp_case_id


def test_student_sp_detail_hides_history_and_rubric(db_factory, client):
    sp_case_id = _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200

    response = client.get(f"/api/sp-cases/{sp_case_id}")
    assert response.status_code == 200
    payload = response.json()
    assert "hidden_history" not in payload
    assert "scoring_rubric" not in payload
    # No hidden value may appear anywhere in the serialised response.
    rendered = response.text
    for value in list(HIDDEN_HISTORY.values()) + list(SCORING_RUBRIC.values()):
        assert value not in rendered
    # Students still get what the encounter needs.
    assert payload["opening_statement"]
    assert payload["expected_tasks"]
    assert payload["scoring_dimensions"]


def test_student_sp_list_never_exposes_hidden_fields(db_factory, client):
    _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200
    rendered = client.get("/api/sp-cases").text
    assert "hidden_history" not in rendered
    assert "scoring_rubric" not in rendered
    assert HIDDEN_HISTORY["pain"] not in rendered


def test_teacher_still_sees_the_full_sp_case(db_factory, client):
    sp_case_id = _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "teacher", "password": "secret1"}).status_code == 200
    payload = client.get(f"/api/sp-cases/{sp_case_id}").json()
    assert payload["hidden_history"] == HIDDEN_HISTORY
    assert payload["scoring_rubric"] == SCORING_RUBRIC


def test_patient_still_reveals_hidden_history_when_asked(db_factory, client):
    """The redaction must not stop the simulated patient from answering."""

    sp_case_id = _seed(db_factory)
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200
    session = client.post("/api/sp-sessions/start", json={"sp_case_id": sp_case_id}).json()
    session_id = session["session_id"]

    response = client.post(
        f"/api/sp-sessions/{session_id}/message",
        json={"message": "发热持续多久了？有没有关节疼痛？"},
    )
    assert response.status_code == 200
    reply = response.json()["patient_reply"]
    assert "一个月" in reply or "关节" in reply
