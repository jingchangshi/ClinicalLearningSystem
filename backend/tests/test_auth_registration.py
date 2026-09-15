import pytest
from pydantic import ValidationError

from app.routes.auth import RegisterRequest


def test_public_registration_only_accepts_student_or_teacher():
    assert RegisterRequest(username="learner", password="secret1", role="student").role == "student"
    assert RegisterRequest(username="teacher", password="secret1", role="teacher").role == "teacher"
    with pytest.raises(ValidationError):
        RegisterRequest(username="attacker", password="secret1", role="admin")
