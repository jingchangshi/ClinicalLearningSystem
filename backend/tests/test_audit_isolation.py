"""Guard: the test process must never write audit rows into a real database."""

from app.core import ai_audit
from app.models import AIInvocation

from tests.factories import ANSWER_TEXTS, make_case, make_student


def test_audit_writer_is_isolated_in_tests():
    assert ai_audit._session_factory is not None, (
        "tests must install an isolated audit session factory in conftest"
    )
    url = str(ai_audit._session_factory().bind.url)
    assert url != "sqlite:///./clinical_learning.db", "audit writer must not target the dev/prod database"
    assert "clinical_learning.db" not in url


def test_audited_route_only_touches_the_isolated_store(db_factory, client):
    db = db_factory()
    make_case(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200
    session_id = client.post("/api/sessions/start", json={"case_id": 1}).json()["id"]
    for step, text in ANSWER_TEXTS.items():
        client.post(f"/api/sessions/{session_id}/answers", json={"step": step, "answer_text": text})
    assert client.post(f"/api/sessions/{session_id}/submit").status_code == 200

    assert ai_audit.flush() is True
    # Rows landed in the in-memory audit store, not in a file database.
    audit_session = ai_audit._session_factory()
    try:
        assert audit_session.query(AIInvocation).count() >= 1
    finally:
        audit_session.close()
