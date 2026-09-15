import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, serialize_user, verify_password
from app.database import get_db
from app.models import CompetencyProfile, Student, Teacher, User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    # Teacher and administrator accounts are provisioned server-side only.
    role: Literal["student"] = "student"
    student_id: int | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


def _auth_response(response: Response, user: User) -> dict:
    token = create_access_token(user)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 12,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    )
    return {"token_type": "cookie", "user": serialize_user(user)}


@router.post("/register")
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="Username already exists")
    student_id = payload.student_id
    if payload.role == "student":
        if student_id is None:
            student = _create_registered_student(db, payload.username)
            student_id = student.id
        elif not db.get(Student, student_id):
            raise HTTPException(status_code=400, detail="Valid student_id is required")
        if db.query(User).filter(User.student_id == student_id).first():
            raise HTTPException(status_code=409, detail="Student already has a user")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        student_id=student_id if payload.role == "student" else None,
        teacher_id=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _auth_response(response, user)


def _create_registered_student(db: Session, username: str) -> Student:
    student = Student(
        name=username,
        student_no=_unique_no(db, Student, "student_no", "REGS"),
        class_name="注册用户",
        current_stage="stage_1_basic_knowledge",
    )
    db.add(student)
    db.flush()
    db.add(
        CompetencyProfile(
            student_id=student.id,
            medical_knowledge=60,
            key_information=60,
            differential_diagnosis=60,
            evidence_integration=60,
            clinical_decision=60,
            evidence_based_medicine=60,
            learning_engagement=60,
        )
    )
    db.flush()
    return student


def _unique_no(db: Session, model: type[Student], field: str, prefix: str) -> str:
    next_id = (db.query(model).count() or 0) + 1
    while True:
        value = f"{prefix}{next_id:06d}"
        if not db.query(model).filter(getattr(model, field) == value).first():
            return value
        next_id += 1


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return _auth_response(response, user)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key="access_token", path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return serialize_user(user)
