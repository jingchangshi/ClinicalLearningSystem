import pytest
from pydantic import ValidationError

from app.routes.auth import RegisterRequest


def test_public_registration_only_accepts_student():
    assert RegisterRequest(username="learner", password="secret1", role="student").role == "student"
    with pytest.raises(ValidationError):
        RegisterRequest(username="teacher", password="secret1", role="teacher")
    with pytest.raises(ValidationError):
        RegisterRequest(username="attacker", password="secret1", role="admin")
