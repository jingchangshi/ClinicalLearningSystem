from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AIMessage,
    Case,
    CaseSession,
    CompetencyProfile,
    LearningRecommendation,
    Score,
    Student,
    StudentAnswer,
)
from app.schemas import AnswerCreate, CoachRequest, SessionStartRequest
from app.services.llm_client import (
    generate_learning_recommendation,
    generate_reasoning_question,
    score_student_answer,
)
from app.services.recommendation_service import determine_pathway_stage
from app.services.serializers import (
    CORE_ABILITIES,
    dumps_json,
    serialize_case,
    serialize_case_summary,
    serialize_profile,
    serialize_score,
    serialize_student,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("/start")
def start_session(payload: SessionStartRequest, db: Session = Depends(get_db)) -> dict:
    if not db.get(Student, payload.student_id):
        raise HTTPException(status_code=404, detail="Student not found")
    if not db.get(Case, payload.case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    session = CaseSession(student_id=payload.student_id, case_id=payload.case_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "session_id": session.id, "status": session.status}


@router.get("/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)) -> dict:
    session = _get_session(db, session_id)
    return _serialize_session(session)


@router.post("/{session_id}/answers")
def save_answer(session_id: int, payload: AnswerCreate, db: Session = Depends(get_db)) -> dict:
    session = _get_session(db, session_id)
    answer = StudentAnswer(
        session_id=session.id,
        step=payload.step,
        answer_text=payload.answer_text,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return {
        "id": answer.id,
        "session_id": answer.session_id,
        "step": answer.step,
        "answer_text": answer.answer_text,
        "created_at": answer.created_at,
    }


@router.post("/{session_id}/coach")
def coach(session_id: int, payload: CoachRequest, db: Session = Depends(get_db)) -> dict:
    session = _get_session(db, session_id)
    question = generate_reasoning_question(
        serialize_case(session.case),
        payload.step,
        payload.answer_text,
    )
    message = AIMessage(
        session_id=session.id,
        role="assistant",
        message=question,
        reasoning_step=payload.step,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return {
        "id": message.id,
        "session_id": session.id,
        "role": message.role,
        "message": message.message,
        "reasoning_step": message.reasoning_step,
        "created_at": message.created_at,
    }


@router.post("/{session_id}/submit")
def submit_session(session_id: int, db: Session = Depends(get_db)) -> dict:
    session = _get_session(db, session_id)
    if not session.answers:
        raise HTTPException(status_code=400, detail="At least one answer is required")

    case = serialize_case(session.case)
    answers = [
        {"step": answer.step, "answer_text": answer.answer_text} for answer in session.answers
    ]
    score_payload = score_student_answer(case, answers, case["rubric"])
    if session.score:
        db.delete(session.score)
        db.flush()

    score = Score(
        session_id=session.id,
        total_score=score_payload["total_score"],
        medical_knowledge=score_payload["medical_knowledge"],
        key_information=score_payload["key_information"],
        differential_diagnosis=score_payload["differential_diagnosis"],
        evidence_integration=score_payload["evidence_integration"],
        clinical_decision=score_payload["clinical_decision"],
        evidence_based_medicine=score_payload["evidence_based_medicine"],
        feedback=score_payload["feedback"],
        strengths=score_payload["strengths"],
        weaknesses=score_payload["weaknesses"],
    )
    db.add(score)
    _update_competency(session.student.competency_profile, score_payload)
    profile_dict = serialize_profile(session.student.competency_profile)
    session.student.current_stage = determine_pathway_stage(profile_dict)
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.flush()

    cases = [serialize_case_summary(case_row) for case_row in db.query(Case).all()]
    recommendation = generate_learning_recommendation(profile_dict, [score_payload], cases)
    db.add(
        LearningRecommendation(
            student_id=session.student_id,
            recommended_case_id=recommendation["case"]["id"],
            recommendation_reason=recommendation["reason"],
            pathway_stage=recommendation["pathway_stage"],
        )
    )
    db.commit()
    db.refresh(score)
    return {
        "score_id": score.id,
        "session_id": session.id,
        "summary": {
            "total_score": score.total_score,
            "strengths": score.strengths,
            "weaknesses": score.weaknesses,
            "next_recommendation": recommendation,
        },
    }


@router.get("/{session_id}/result")
def get_result(session_id: int, db: Session = Depends(get_db)) -> dict:
    session = _get_session(db, session_id)
    if not session.score:
        raise HTTPException(status_code=404, detail="Score not found")
    latest_recommendation = (
        db.query(LearningRecommendation)
        .filter(LearningRecommendation.student_id == session.student_id)
        .order_by(LearningRecommendation.created_at.desc())
        .first()
    )
    return {
        "session": _serialize_session(session),
        "case": serialize_case_summary(session.case),
        "answers": [
            {
                "id": answer.id,
                "step": answer.step,
                "answer_text": answer.answer_text,
                "created_at": answer.created_at,
            }
            for answer in session.answers
        ],
        "score": serialize_score(session.score),
        "competency": serialize_profile(session.student.competency_profile),
        "recommendation": {
            "case": serialize_case_summary(latest_recommendation.recommended_case),
            "recommendation_reason": latest_recommendation.recommendation_reason,
            "pathway_stage": latest_recommendation.pathway_stage,
        }
        if latest_recommendation
        else None,
    }


def _get_session(db: Session, session_id: int) -> CaseSession:
    session = db.get(CaseSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _serialize_session(session: CaseSession) -> dict:
    return {
        "id": session.id,
        "student": serialize_student(session.student),
        "case": serialize_case(session.case),
        "status": session.status,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "answers": [
            {
                "id": answer.id,
                "step": answer.step,
                "answer_text": answer.answer_text,
                "created_at": answer.created_at,
            }
            for answer in session.answers
        ],
        "ai_messages": [
            {
                "id": message.id,
                "role": message.role,
                "message": message.message,
                "reasoning_step": message.reasoning_step,
                "created_at": message.created_at,
            }
            for message in session.ai_messages
        ],
    }


def _update_competency(profile: CompetencyProfile, score_payload: dict) -> None:
    for key in CORE_ABILITIES:
        setattr(profile, key, round(getattr(profile, key) * 0.7 + score_payload[key] * 0.3, 1))
    profile.learning_engagement = min(100, round(profile.learning_engagement + 3, 1))
    profile.updated_at = datetime.utcnow()
