from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_student_access, student_id_from_user
from app.database import get_db
from app.models import KnowledgeProgress, KnowledgeUnit, Student, User
from app.services.competency_update_service import update_competency_from_knowledge
from app.services.serializers import (
    loads_json,
    serialize_knowledge_progress,
    serialize_knowledge_summary,
    serialize_knowledge_unit,
)

router = APIRouter(prefix="/api", tags=["knowledge"])


class QuizSubmitRequest(BaseModel):
    student_id: int | None = None
    answers: list[str]


@router.get("/knowledge")
def list_knowledge(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[dict]:
    return [serialize_knowledge_summary(unit) for unit in db.query(KnowledgeUnit).all()]


@router.get("/knowledge/{unit_id}")
def get_knowledge(
    unit_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    unit = db.get(KnowledgeUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Knowledge unit not found")
    return serialize_knowledge_unit(unit)


@router.get("/students/{student_id}/knowledge-progress")
def get_student_knowledge_progress(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    require_student_access(student_id, user)
    return knowledge_progress_payload(db, student_id)


def knowledge_progress_payload(db: Session, student_id: int) -> list[dict]:
    if not db.get(Student, student_id):
        raise HTTPException(status_code=404, detail="Student not found")
    _ensure_progress_rows(db, student_id)
    rows = (
        db.query(KnowledgeProgress)
        .filter(KnowledgeProgress.student_id == student_id)
        .order_by(KnowledgeProgress.knowledge_unit_id.asc())
        .all()
    )
    return [serialize_knowledge_progress(row) for row in rows]


@router.post("/knowledge/{unit_id}/quiz")
def submit_quiz(
    unit_id: int,
    payload: QuizSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    unit = db.get(KnowledgeUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Knowledge unit not found")
    student_id = student_id_from_user(user, payload.student_id)
    if not db.get(Student, student_id):
        raise HTTPException(status_code=404, detail="Student not found")

    progress = _get_or_create_progress(db, student_id, unit_id)
    quiz_score = _score_quiz(loads_json(unit.quiz_items, []), payload.answers)
    mastery_score = round((progress.mastery_score or 0) * 0.6 + quiz_score * 0.4, 1)
    progress.quiz_score = quiz_score
    progress.mastery_score = mastery_score
    progress.status = "completed" if mastery_score >= 80 else "in_progress"
    progress.updated_at = datetime.utcnow()
    db.flush()
    update_competency_from_knowledge(db, student_id, quiz_score, progress.id)
    db.commit()
    db.refresh(progress)

    return {
        "quiz_score": quiz_score,
        "mastery_score": mastery_score,
        "feedback": _quiz_feedback(quiz_score, mastery_score),
        "updated_progress": serialize_knowledge_progress(progress),
    }


def _ensure_progress_rows(db: Session, student_id: int) -> None:
    unit_ids = [unit.id for unit in db.query(KnowledgeUnit).all()]
    existing_ids = {
        row.knowledge_unit_id
        for row in db.query(KnowledgeProgress).filter(KnowledgeProgress.student_id == student_id)
    }
    for unit_id in unit_ids:
        if unit_id not in existing_ids:
            db.add(KnowledgeProgress(student_id=student_id, knowledge_unit_id=unit_id))
    db.commit()


def _get_or_create_progress(db: Session, student_id: int, unit_id: int) -> KnowledgeProgress:
    progress = (
        db.query(KnowledgeProgress)
        .filter(
            KnowledgeProgress.student_id == student_id,
            KnowledgeProgress.knowledge_unit_id == unit_id,
        )
        .first()
    )
    if progress:
        return progress
    progress = KnowledgeProgress(student_id=student_id, knowledge_unit_id=unit_id)
    db.add(progress)
    db.flush()
    return progress


def _score_quiz(quiz_items: list[dict], answers: list[str]) -> float:
    if not quiz_items:
        return 0.0
    total = 0.0
    for index, item in enumerate(quiz_items):
        answer = answers[index] if index < len(answers) else ""
        keywords = item.get("answer_keywords", [])
        if not keywords:
            continue
        hits = sum(1 for keyword in keywords if str(keyword).lower() in answer.lower())
        total += min(1.0, hits / max(1, min(2, len(keywords))))
    return round(total / len(quiz_items) * 100, 1)


def _quiz_feedback(quiz_score: float, mastery_score: float) -> str:
    if mastery_score >= 80:
        return "本单元掌握度达到完成标准。建议结合相关病例进行迁移应用。"
    if quiz_score >= 70:
        return "本次测验表现较好，但累计掌握度仍需巩固。建议复盘关键点后再次测验。"
    return "关键概念掌握仍不稳定。建议重新阅读学习目标和关键点，重点补充标准答案关键词。"
