from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user, student_id_from_user
from app.database import get_db
from app.models import GuidelineDocument, GuidelineLearningSession, Student, User
from app.services.competency_update_service import update_competency_from_guideline
from app.services.guideline_scoring import score_guideline_pico
from app.services.serializers import (
    loads_json,
    serialize_guideline,
    serialize_guideline_session,
    serialize_guideline_summary,
)

router = APIRouter(prefix="/api", tags=["guidelines"])


class PicoSubmitRequest(BaseModel):
    student_id: int | None = None
    clinical_question: str
    pico: str
    answer: str


@router.get("/guidelines")
def list_guidelines(db: Session = Depends(get_db), _user: User = Depends(get_current_user)) -> list[dict]:
    return [serialize_guideline_summary(guideline) for guideline in db.query(GuidelineDocument).all()]


@router.get("/guidelines/{guideline_id}")
def get_guideline(
    guideline_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    guideline = db.get(GuidelineDocument, guideline_id)
    if not guideline:
        raise HTTPException(status_code=404, detail="Guideline not found")
    return serialize_guideline(guideline)


@router.post("/guidelines/{guideline_id}/pico")
def submit_pico(
    guideline_id: int,
    payload: PicoSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    guideline = db.get(GuidelineDocument, guideline_id)
    if not guideline:
        raise HTTPException(status_code=404, detail="Guideline not found")
    student_id = student_id_from_user(user, payload.student_id)
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    recommendations = loads_json(guideline.recommendations, [])
    pico_examples = loads_json(guideline.pico_examples, [])
    result = score_guideline_pico(
        serialize_guideline(guideline),
        payload.model_dump(),
        recommendations,
        pico_examples,
    )

    session = GuidelineLearningSession(
        student_id=student_id,
        guideline_id=guideline_id,
        clinical_question=payload.clinical_question,
        pico=payload.pico,
        answer=payload.answer,
        score=result["score"],
        feedback=result["feedback"],
    )
    db.add(session)
    db.flush()
    update_competency_from_guideline(db, student_id, result["score"], result["detail"], session.id)
    db.commit()
    db.refresh(session)

    return {
        "score": result["score"],
        "feedback": result["feedback"],
        "recommended_answer": result["recommended_answer"],
        "detail": result["detail"],
        "session": serialize_guideline_session(session),
    }
