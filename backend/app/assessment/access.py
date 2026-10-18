"""Role gates for the assessment API.

``app.auth.require_role`` lets an admin through every role gate. That is wrong
here: a study admin must not be able to rate, review a form, sit an exam or
adjudicate, so these gates test the *exact* role.
"""
from fastapi import Depends, HTTPException

from app.auth import get_current_user
from app.models import User


def fail(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message})


def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != "student" or user.student_id is None:
        raise fail(403, "student_required", "Student account required")
    return user


def require_teacher(user: User = Depends(get_current_user)) -> User:
    # A real teacher account: its own Teacher row, never an admin acting as a teacher.
    if user.role != "teacher" or user.teacher_id is None:
        raise fail(403, "teacher_required", "Teacher account required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise fail(403, "admin_required", "Study administrator required")
    return user


def require_author(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("teacher", "admin"):
        raise fail(403, "author_required", "Teacher or administrator required")
    return user
