from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GuidelineDocument, GuidelineLearningSession, Student
from app.services.guideline_scoring import score_guideline_pico, update_evidence_profile
from app.services.serializers import (
    loads_json,
    serialize_guideline,
    serialize_guideline_session,
    serialize_guideline_summary,
)

router = APIRouter(prefix="/api", tags=["guidelines"])


class PicoSubmitRequest(BaseModel):
    student_id: int
    clinical_question: str
    pico: str
    answer: str


@router.get("/guidelines")
def list_guidelines(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_guideline_summary(guideline) for guideline in db.query(GuidelineDocument).all()]


@router.get("/guidelines/{guideline_id}")
def get_guideline(guideline_id: int, db: Session = Depends(get_db)) -> dict:
    guideline = db.get(GuidelineDocument, guideline_id)
    if not guideline:
        raise HTTPException(status_code=404, detail="Guideline not found")
    return serialize_guideline(guideline)


@router.post("/guidelines/{guideline_id}/pico")
def submit_pico(
    guideline_id: int,
    payload: PicoSubmitRequest,
    db: Session = Depends(get_db),
) -> dict:
    guideline = db.get(GuidelineDocument, guideline_id)
    if not guideline:
        raise HTTPException(status_code=404, detail="Guideline not found")
    student = db.get(Student, payload.student_id)
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
        student_id=payload.student_id,
        guideline_id=guideline_id,
        clinical_question=payload.clinical_question,
        pico=payload.pico,
        answer=payload.answer,
        score=result["score"],
        feedback=result["feedback"],
    )
    db.add(session)
    update_evidence_profile(student.competency_profile, result["score"])
    db.commit()
    db.refresh(session)

    return {
        "score": result["score"],
        "feedback": result["feedback"],
        "recommended_answer": result["recommended_answer"],
        "detail": result["detail"],
        "session": serialize_guideline_session(session),
    }
