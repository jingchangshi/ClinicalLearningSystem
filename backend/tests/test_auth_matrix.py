"""Backend authorization is the only source of truth for role and ownership."""

import jwt
import pytest

from app.auth import JWT_ALGORITHM, JWT_SECRET
from app.models import Teacher, User
from app.auth import hash_password

from tests.factories import make_case, make_student


@pytest.fixture
def accounts(db_factory):
    db = db_factory()
    make_case(db)
    student, _ = make_student(db, username="learner")
    other, _ = make_student(db, name="Other", username="other")
    teacher = Teacher(name="Teacher", teacher_no="T001", department="Medicine")
    db.add(teacher)
    db.flush()
    db.add(User(username="teacher", password_hash=hash_password("secret1"), role="teacher", teacher_id=teacher.id))
    db.commit()
    ids = {"student": student.id, "other": other.id}
    db.close()
    return ids


def test_valid_login_sets_httponly_cookie(client, accounts):
    response = client.post("/api/auth/login", json={"username": "learner", "password": "secret1"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "student"
    cookie_header = response.headers["set-cookie"]
    assert "HttpOnly" in cookie_header
    assert "access_token=" in cookie_header


def test_invalid_password_is_rejected(client, accounts):
    assert client.post("/api/auth/login", json={"username": "learner", "password": "wrong"}).status_code == 401


def test_missing_cookie_is_unauthenticated(client, accounts):
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        "a.b.c",
        # Correct shape, wrong signature: the role claim must never be trusted.
        jwt.encode({"sub": "1", "role": "teacher", "username": "x"}, "wrong-secret", algorithm=JWT_ALGORITHM),
        jwt.encode({"sub": "999", "role": "student", "username": "ghost"}, JWT_SECRET, algorithm=JWT_ALGORITHM),
    ],
)
def test_forged_or_unknown_tokens_are_rejected(client, accounts, token):
    client.cookies.set("access_token", token)
    assert client.get("/api/auth/me").status_code == 401


def test_student_cannot_reach_teacher_apis(client, accounts):
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200
    assert client.get("/api/teacher/dashboard").status_code == 403
    assert client.get("/api/system/ai-status").status_code == 403
    assert client.get("/api/teacher/reviewable-evidence").status_code == 403


def test_student_cannot_read_another_student(client, accounts):
    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200
    assert client.get(f"/api/students/{accounts['other']}/dashboard").status_code == 403
    assert client.get(f"/api/students/{accounts['other']}/competency").status_code == 403
    assert client.get(f"/api/students/{accounts['other']}/pathway").status_code == 403


def test_unauthenticated_cannot_read_student_data(client, accounts):
    assert client.get("/api/students").status_code == 401
    assert client.get("/api/student/dashboard").status_code == 401
    assert client.get("/api/student/pathway").status_code == 401
