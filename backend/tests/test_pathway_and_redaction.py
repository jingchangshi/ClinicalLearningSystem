"""Regression guards for the production 500 on /api/student/pathway and for hidden answers."""

from tests.factories import ANSWER_TEXTS, make_case, make_catalog, make_student

HIDDEN_FIELDS = ("standard_diagnosis", "treatment_plan", "rubric", "differential_diagnosis")


def _login(client, username="learner"):
    assert client.post("/api/auth/login", json={"username": username, "password": "secret1"}).status_code == 200


def test_student_pathway_returns_200_with_datetime_in_profile(db_factory, client):
    """The pathway builder used to json.dumps() the competency profile, whose
    updated_at is a datetime, so every student request returned 500."""

    db = db_factory()
    make_case(db)
    make_catalog(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    _login(client)
    response = client.get("/api/student/pathway")
    assert response.status_code == 200
    payload = response.json()
    assert payload["current_stage"]
    assert payload["recommended_tasks"]
    assert payload["competency"]["updated_at"]


def test_student_session_payload_never_exposes_hidden_answers(db_factory, client):
    db = db_factory()
    case = make_case(db)
    make_student(db, username="learner")
    db.commit()
    hidden_diagnosis, hidden_treatment = case.standard_diagnosis, case.treatment_plan
    db.close()

    _login(client)
    session_id = client.post("/api/sessions/start", json={"case_id": 1}).json()["id"]
    client.post(f"/api/sessions/{session_id}/answers", json={"step": "key_information", "answer_text": "发热皮疹"})

    session_payload = client.get(f"/api/sessions/{session_id}").json()
    assert HIDDEN_FIELDS[0] not in session_payload["case"]
    assert HIDDEN_FIELDS[1] not in session_payload["case"]
    assert HIDDEN_FIELDS[2] not in session_payload["case"]

    coach_payload = client.post(
        f"/api/sessions/{session_id}/coach", json={"step": "key_information", "answer_text": "发热皮疹"}
    ).json()
    assert hidden_diagnosis not in coach_payload["message"]
    assert hidden_treatment not in coach_payload["message"]


def test_result_payload_carries_evidence_and_evaluation_mode(db_factory, client):
    db = db_factory()
    make_case(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    _login(client)
    session_id = client.post("/api/sessions/start", json={"case_id": 1}).json()["id"]
    for step, text in ANSWER_TEXTS.items():
        client.post(f"/api/sessions/{session_id}/answers", json={"step": step, "answer_text": text})
    client.post(f"/api/sessions/{session_id}/submit")

    result = client.get(f"/api/sessions/{session_id}/result")
    assert result.status_code == 200
    score = result.json()["score"]
    assert score["evaluation_mode"] in {"ai", "rule_fallback"}
    assert isinstance(score["degraded"], bool)
    assert score["evaluation_detail"]["dimensions"]
    assert score["safety_flags"] is not None
    for dimension in score["evaluation_detail"]["dimensions"].values():
        assert dimension["evidence"]
        assert dimension["feedback"]
    assert "standard_diagnosis" not in result.json()["case"]
