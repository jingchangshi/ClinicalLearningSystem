"""Identifiers typed into a case must be surfaced at the door, not only at the model."""

import json

from app.auth import hash_password
from app.models import Case, Teacher, User

CASE_PAYLOAD = {
    "title": "测试病例",
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


def _login_teacher(db_factory, client, username="teacher"):
    db = db_factory()
    teacher = Teacher(name="Teacher", teacher_no="T001", department="Medicine")
    db.add(teacher)
    db.flush()
    db.add(User(username=username, password_hash=hash_password("secret1"), role="teacher", teacher_id=teacher.id))
    db.commit()
    db.close()
    assert client.post("/api/auth/login", json={"username": username, "password": "secret1"}).status_code == 200


def test_clean_case_reports_nothing(db_factory, client):
    _login_teacher(db_factory, client)
    response = client.post("/api/teacher/cases", json=CASE_PAYLOAD)
    assert response.status_code == 200
    report = response.json()["deidentification"]
    assert report["clean"] is True
    assert report["findings"] == []


def test_identifiers_are_reported_without_echoing_values(db_factory, client):
    _login_teacher(db_factory, client)
    payload = {
        **CASE_PAYLOAD,
        "history": "患者姓名：张三，电话 13800138000，住院号 ZY202600777，反复发热两周。",
    }
    response = client.post("/api/teacher/cases", json=payload)
    assert response.status_code == 200
    report = response.json()["deidentification"]
    assert report["clean"] is False
    assert [finding["field"] for finding in report["findings"]] == ["history"]
    assert report["findings"][0]["label"] == "现病史"
    kinds = set(report["findings"][0]["kinds"])
    assert {"labelled_name", "mainland_mobile", "medical_record_number"} <= kinds
    # The *report* must never echo the identifiers themselves. (The created case
    # still returns the text the teacher wrote — that is their own input, not a
    # diagnostic echo.)
    report_text = json.dumps(report, ensure_ascii=False)
    assert "13800138000" not in report_text
    assert "ZY202600777" not in report_text
    assert "张三" not in report_text


def test_authoring_keeps_what_the_teacher_typed(db_factory, client):
    """We warn, we do not silently rewrite an author's case text."""

    _login_teacher(db_factory, client)
    payload = {**CASE_PAYLOAD, "history": "联系电话 13800138000，反复发热两周。"}
    case_id = client.post("/api/teacher/cases", json=payload).json()["id"]

    db = db_factory()
    stored = db.get(Case, case_id)
    assert "13800138000" in stored.history
    db.close()


def test_strict_mode_blocks_identifiers_when_enabled(db_factory, client, monkeypatch):
    monkeypatch.setenv("REQUIRE_CASE_DEIDENTIFICATION", "true")
    _login_teacher(db_factory, client)
    payload = {**CASE_PAYLOAD, "history": "患者姓名：李四，反复发热。"}

    response = client.post("/api/teacher/cases", json=payload)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["fields"][0]["field"] == "history"
    assert "李四" not in response.text

    db = db_factory()
    assert db.query(Case).count() == 0
    db.close()


def test_strict_mode_still_allows_clinical_numbers(db_factory, client, monkeypatch):
    monkeypatch.setenv("REQUIRE_CASE_DEIDENTIFICATION", "true")
    _login_teacher(db_factory, client)
    payload = {
        **CASE_PAYLOAD,
        "history": "32岁女性，体温最高38.6℃，白细胞3.0×10^9/L，补体C3 0.45 g/L。",
    }
    assert client.post("/api/teacher/cases", json=payload).status_code == 200
