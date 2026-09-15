"""One logical answer per (session, step); a completed session cannot be corrupted."""

from app.core.reasoning_steps import REQUIRED_STEP_KEYS
from app.models import CaseSession, Score, StudentAnswer

from tests.factories import ANSWER_TEXTS, make_case, make_student


def _login(client, username="learner"):
    response = client.post("/api/auth/login", json={"username": username, "password": "secret1"})
    assert response.status_code == 200


def _start_session(client, case_id=1):
    response = client.post("/api/sessions/start", json={"case_id": case_id})
    assert response.status_code == 200
    return response.json()["id"]


def _save(client, session_id, step, text):
    return client.post(f"/api/sessions/{session_id}/answers", json={"step": step, "answer_text": text})


def test_repeated_save_keeps_one_logical_answer(db_factory, client):
    db = db_factory()
    make_case(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    _login(client)
    session_id = _start_session(client)
    assert _save(client, session_id, "key_information", "第一版回答 A").status_code == 200
    assert _save(client, session_id, "key_information", "第二版回答 B").status_code == 200

    payload = client.get(f"/api/sessions/{session_id}").json()
    saved = [answer for answer in payload["answers"] if answer["step"] == "key_information"]
    assert len(saved) == 1
    assert saved[0]["answer_text"] == "第二版回答 B"

    db = db_factory()
    rows = db.query(StudentAnswer).filter(StudentAnswer.session_id == session_id).all()
    assert len(rows) == 1
    assert rows[0].answer_text == "第二版回答 B"
    assert rows[0].updated_at >= rows[0].created_at
    db.close()


def test_missing_step_is_rejected_with_structured_error(db_factory, client):
    db = db_factory()
    make_case(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    _login(client)
    session_id = _start_session(client)
    for step in REQUIRED_STEP_KEYS[:-1]:
        assert _save(client, session_id, step, ANSWER_TEXTS[step]).status_code == 200

    response = client.post(f"/api/sessions/{session_id}/submit")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["missing_steps"] == ["treatment"]

    db = db_factory()
    assert db.query(Score).filter(Score.session_id == session_id).count() == 0
    assert db.get(CaseSession, session_id).status == "in_progress"
    db.close()


def test_empty_and_unknown_steps_are_rejected(db_factory, client):
    db = db_factory()
    make_case(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    _login(client)
    session_id = _start_session(client)
    assert _save(client, session_id, "key_information", "   ").status_code == 400
    assert _save(client, session_id, "reasoning", "旧版自由步骤").status_code == 400


def test_duplicate_submit_is_idempotent_and_does_not_double_count(db_factory, client):
    db = db_factory()
    make_case(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    _login(client)
    session_id = _start_session(client)
    for step, text in ANSWER_TEXTS.items():
        assert _save(client, session_id, step, text).status_code == 200

    first = client.post(f"/api/sessions/{session_id}/submit")
    assert first.status_code == 200
    second = client.post(f"/api/sessions/{session_id}/submit")
    assert second.status_code == 200
    assert second.json()["score_id"] == first.json()["score_id"]

    db = db_factory()
    assert db.query(Score).filter(Score.session_id == session_id).count() == 1
    assert db.get(CaseSession, session_id).status == "completed"
    db.close()


def test_completed_session_cannot_change_answers_or_score(db_factory, client):
    db = db_factory()
    make_case(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    _login(client)
    session_id = _start_session(client)
    for step, text in ANSWER_TEXTS.items():
        assert _save(client, session_id, step, text).status_code == 200
    score_id = client.post(f"/api/sessions/{session_id}/submit").json()["score_id"]

    assert _save(client, session_id, "key_information", "提交后偷改答案").status_code == 409

    db = db_factory()
    answer = (
        db.query(StudentAnswer)
        .filter(StudentAnswer.session_id == session_id, StudentAnswer.step == "key_information")
        .one()
    )
    assert answer.answer_text == ANSWER_TEXTS["key_information"]
    assert db.get(Score, score_id).total_score is not None
    db.close()
