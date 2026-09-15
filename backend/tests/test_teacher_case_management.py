"""Destructive case management runs only against the disposable test database,
and must stay behind teacher/admin authorization."""

from app.models import Case

from tests.factories import make_case, make_student

CASE_PAYLOAD = {
    "title": "新建测试病例",
    "disease_category": "SLE",
    "difficulty": "基础",
    "learning_objectives": ["关键信息提取"],
    "chief_complaint": "发热",
    "history": "反复发热两周。",
    "physical_exam": "面部皮疹。",
    "lab_results": "ANA阳性。",
    "imaging": "未见异常。",
    "standard_diagnosis": "系统性红斑狼疮",
    "differential_diagnosis": ["感染"],
    "treatment_plan": "激素治疗后随访。",
    "rubric": {"medical_knowledge": "诊断依据"},
}


def test_student_cannot_create_update_or_delete_cases(db_factory, client):
    db = db_factory()
    case = make_case(db)
    make_student(db, username="learner")
    db.commit()
    case_id = case.id
    db.close()

    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200
    assert client.post("/api/teacher/cases", json=CASE_PAYLOAD).status_code == 403
    assert client.put(f"/api/teacher/cases/{case_id}", json=CASE_PAYLOAD).status_code == 403
    assert client.delete(f"/api/teacher/cases/{case_id}").status_code == 403

    db = db_factory()
    assert db.get(Case, case_id) is not None
    assert db.query(Case).count() == 1
    db.close()


def test_anonymous_cannot_delete_cases(db_factory, client):
    db = db_factory()
    case = make_case(db)
    db.commit()
    case_id = case.id
    db.close()

    assert client.delete(f"/api/teacher/cases/{case_id}").status_code == 401

    db = db_factory()
    assert db.get(Case, case_id) is not None
    db.close()


def test_teacher_case_lifecycle_in_disposable_database(db_factory, client):
    from app.auth import hash_password
    from app.models import Teacher, User

    db = db_factory()
    teacher = Teacher(name="Teacher", teacher_no="T001", department="Medicine")
    db.add(teacher)
    db.flush()
    db.add(User(username="teacher", password_hash=hash_password("secret1"), role="teacher", teacher_id=teacher.id))
    db.commit()
    db.close()

    assert client.post("/api/auth/login", json={"username": "teacher", "password": "secret1"}).status_code == 200

    created = client.post("/api/teacher/cases", json=CASE_PAYLOAD)
    assert created.status_code == 200
    case_id = created.json()["id"]
    assert created.json()["title"] == CASE_PAYLOAD["title"]

    updated = client.put(f"/api/teacher/cases/{case_id}", json={**CASE_PAYLOAD, "difficulty": "进阶"})
    assert updated.status_code == 200
    assert updated.json()["difficulty"] == "进阶"

    assert client.delete(f"/api/teacher/cases/{case_id}").status_code == 200

    db = db_factory()
    assert db.get(Case, case_id) is None
    db.close()

    assert client.delete(f"/api/teacher/cases/{case_id}").status_code == 404
