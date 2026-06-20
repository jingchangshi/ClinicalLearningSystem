from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SPCase, SPSession, Student
from app.services.serializers import (
    dumps_json,
    loads_json,
    serialize_sp_case,
    serialize_sp_case_summary,
    serialize_sp_session,
)
from app.services.sp_patient import generate_patient_reply, load_sp_case_payload, score_sp_session

router = APIRouter(prefix="/api", tags=["sp"])


class SPSessionStartRequest(BaseModel):
    student_id: int
    sp_case_id: int


class SPMessageRequest(BaseModel):
    message: str


class SPSubmitRequest(BaseModel):
    diagnosis_summary: str


@router.get("/sp-cases")
def list_sp_cases(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_sp_case_summary(sp_case) for sp_case in db.query(SPCase).all()]


@router.get("/sp-cases/{sp_case_id}")
def get_sp_case(sp_case_id: int, db: Session = Depends(get_db)) -> dict:
    sp_case = db.get(SPCase, sp_case_id)
    if not sp_case:
        raise HTTPException(status_code=404, detail="SP case not found")
    return serialize_sp_case(sp_case)


@router.post("/sp-sessions/start")
def start_sp_session(payload: SPSessionStartRequest, db: Session = Depends(get_db)) -> dict:
    if not db.get(Student, payload.student_id):
        raise HTTPException(status_code=404, detail="Student not found")
    sp_case = db.get(SPCase, payload.sp_case_id)
    if not sp_case:
        raise HTTPException(status_code=404, detail="SP case not found")

    transcript = [{"role": "patient", "message": sp_case.opening_statement}]
    session = SPSession(
        student_id=payload.student_id,
        sp_case_id=payload.sp_case_id,
        transcript=dumps_json(transcript),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "session_id": session.id,
        "opening_statement": sp_case.opening_statement,
        "session": serialize_sp_session(session),
    }


@router.post("/sp-sessions/{session_id}/message")
def send_sp_message(
    session_id: int,
    payload: SPMessageRequest,
    db: Session = Depends(get_db),
) -> dict:
    session = _get_sp_session(db, session_id)
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="SP session already completed")
    transcript = loads_json(session.transcript, [])
    student_message = payload.message.strip()
    if not student_message:
        raise HTTPException(status_code=400, detail="Message is required")

    transcript.append({"role": "student", "message": student_message})
    patient_reply = generate_patient_reply(
        load_sp_case_payload(session.sp_case),
        transcript,
        student_message,
    )
    transcript.append({"role": "patient", "message": patient_reply})
    session.transcript = dumps_json(transcript)
    db.commit()
    db.refresh(session)
    return {"patient_reply": patient_reply, "transcript": transcript}


@router.post("/sp-sessions/{session_id}/submit")
def submit_sp_session(
    session_id: int,
    payload: SPSubmitRequest,
    db: Session = Depends(get_db),
) -> dict:
    session = _get_sp_session(db, session_id)
    transcript = loads_json(session.transcript, [])
    scoring = score_sp_session(
        load_sp_case_payload(session.sp_case),
        transcript,
        payload.diagnosis_summary,
    )
    session.diagnosis_summary = payload.diagnosis_summary
    session.communication_score = scoring["communication_score"]
    session.history_taking_score = scoring["history_taking_score"]
    session.reasoning_score = scoring["reasoning_score"]
    session.humanistic_care_score = scoring["humanistic_care_score"]
    session.total_score = scoring["total_score"]
    session.feedback = scoring["feedback"]
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return {
        **scoring,
        "session": serialize_sp_session(session),
    }


@router.get("/sp-sessions/{session_id}/result")
def get_sp_result(session_id: int, db: Session = Depends(get_db)) -> dict:
    return serialize_sp_session(_get_sp_session(db, session_id))


def _get_sp_session(db: Session, session_id: int) -> SPSession:
    session = db.get(SPSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="SP session not found")
    return session
