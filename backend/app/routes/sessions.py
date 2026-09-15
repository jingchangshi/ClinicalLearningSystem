import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_student_access, student_id_from_user
from app.core.access_policy import MAX_COACH_TURNS_PER_SESSION
from app.core.ai_audit import ai_invocation
from app.core.rate_limit import enforce
from app.core.reasoning_steps import REQUIRED_REASONING_STEPS, REQUIRED_STEP_KEYS, missing_reasoning_steps
from app.database import get_db
from app.models import (
    Case,
    CaseSession,
    LearningRecommendation,
    Score,
    Student,
    StudentAnswer,
    TutorTurn,
    User,
)
from app.services.competency_update_service import update_competency_from_case
from app.schemas import AnswerCreate, CoachRequest, SessionStartRequest, TutorRequest
from app.services.llm_service import generate_learning_recommendation, score_student_answer
from app.services.recommendation_service import determine_pathway_stage
from app.services.tutor_service import build_reasoning_state, next_tutor_question
from app.core import llm_config
from app.services.serializers import (
    dumps_json,
    serialize_case,
    serialize_case_for_student,
    serialize_case_summary,
    serialize_profile,
    serialize_score,
    serialize_student,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("/start")
def start_session(
    payload: SessionStartRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    student_id = student_id_from_user(user, payload.student_id)
    if not db.get(Student, student_id):
        raise HTTPException(status_code=404, detail="Student not found")
    if not db.get(Case, payload.case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    session = CaseSession(student_id=student_id, case_id=payload.case_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"id": session.id, "session_id": session.id, "status": session.status}


@router.get("/{session_id}")
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    session = _get_session(db, session_id)
    require_student_access(session.student_id, user)
    return _serialize_session(session)


@router.post("/{session_id}/answers")
def save_answer(
    session_id: int,
    payload: AnswerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    session = _get_session(db, session_id)
    require_student_access(session.student_id, user)
    if session.status == "completed":
        raise HTTPException(status_code=409, detail="Session already submitted")
    if payload.step not in REQUIRED_STEP_KEYS:
        raise HTTPException(
            status_code=400,
            detail={"detail": "Unknown reasoning step", "allowed_steps": REQUIRED_STEP_KEYS},
        )
    answer_text = payload.answer_text.strip()
    if not answer_text:
        raise HTTPException(status_code=400, detail="answer_text must not be empty")

    # One logical answer per (session, step): re-saving replaces the previous text.
    answer = (
        db.query(StudentAnswer)
        .filter(StudentAnswer.session_id == session.id, StudentAnswer.step == payload.step)
        .one_or_none()
    )
    if answer is None:
        answer = StudentAnswer(session_id=session.id, step=payload.step, answer_text=answer_text)
        db.add(answer)
    else:
        answer.answer_text = answer_text
        answer.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(answer)
    return {
        "id": answer.id,
        "session_id": answer.session_id,
        "step": answer.step,
        "answer_text": answer.answer_text,
        "created_at": answer.created_at,
        "updated_at": answer.updated_at,
    }


@router.post("/{session_id}/coach")
def coach(
    session_id: int,
    payload: CoachRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Single-question convenience endpoint. Kept for existing clients; the
    multi-turn tutor below is the real formative coaching path."""

    session = _get_session(db, session_id)
    require_student_access(session.student_id, user)
    answer_text = payload.answer_text
    if payload.answer_text.strip() and _answer_text(session, payload.step) != payload.answer_text.strip():
        # Keep the tutor reasoning about the same text the student just saw.
        answer_text = payload.answer_text
    result = _record_tutor_turn(db, session, payload.step, message=None, answer_override=answer_text)
    question = result["tutor_question"] or "本阶段的追问已结束，请补充你的回答后继续训练。"
    return {
        "id": result["turns"][-1]["id"] if result["turns"] else None,
        "session_id": session.id,
        "role": "assistant",
        "message": question,
        "reasoning_step": payload.step,
        "created_at": result["turns"][-1]["created_at"] if result["turns"] else None,
    }


@router.post("/{session_id}/tutor")
def tutor_turn(
    session_id: int,
    payload: TutorRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    session = _get_session(db, session_id)
    require_student_access(session.student_id, user)
    enforce("coach", f"user:{user.id}")
    if session.status == "completed":
        raise HTTPException(status_code=409, detail="Session already submitted")
    if payload.step not in REQUIRED_STEP_KEYS:
        raise HTTPException(
            status_code=400,
            detail={"detail": "Unknown reasoning step", "allowed_steps": REQUIRED_STEP_KEYS},
        )
    return _record_tutor_turn(db, session, payload.step, message=payload.message)


@router.get("/{session_id}/tutor")
def get_tutor_conversation(
    session_id: int,
    step: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    session = _get_session(db, session_id)
    require_student_access(session.student_id, user)
    if step not in REQUIRED_STEP_KEYS:
        raise HTTPException(
            status_code=400,
            detail={"detail": "Unknown reasoning step", "allowed_steps": REQUIRED_STEP_KEYS},
        )
    turns = _tutor_turns(db, session.id, step)
    state = build_reasoning_state(
        serialize_case_for_student(session.case), step, _tutor_analysis_text(session, step, turns), turns
    )
    return {"step": step, "turns": turns, "state": state}


@router.post("/{session_id}/submit")
def submit_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    session = _get_session(db, session_id)
    require_student_access(session.student_id, user)
    enforce("submit", f"user:{user.id}")
    if session.status == "completed" and session.score:
        return _submission_response(session, session.score)
    answers_by_step = {answer.step: answer for answer in session.answers}
    missing_steps = missing_reasoning_steps(
        [{"step": answer.step, "answer_text": answer.answer_text} for answer in session.answers]
    )
    if missing_steps:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "All required reasoning steps must be answered before submission",
                "missing_steps": missing_steps,
            },
        )

    case = serialize_case(session.case)
    answers = [
        {"step": step, "answer_text": answers_by_step[step].answer_text} for step in REQUIRED_STEP_KEYS
    ]
    with ai_invocation(
        "case_evaluation",
        session_id=session.id,
        student_id=session.student_id,
        evidence_ref=f"case_session:{session.id}",
    ):
        score_payload = score_student_answer(case, answers, case["rubric"])
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
        evaluation_mode=score_payload["evaluation_mode"],
        provider=llm_config.LLM_PROVIDER if score_payload["evaluation_mode"] == "ai" else None,
        model=(
            llm_config.LLM_MODEL
            if score_payload["evaluation_mode"] == "ai" and llm_config.LLM_API_KEY
            else None
        ),
        rule_score=score_payload["rule_score"],
        ai_score=score_payload["ai_score"],
        degraded=score_payload["degraded"],
        evaluation_detail_json=dumps_json(score_payload["evaluation_detail"]),
    )
    db.add(score)
    update_competency_from_case(db, session.student_id, score_payload, session.id)
    profile_dict = serialize_profile(session.student.competency_profile)
    session.student.current_stage = determine_pathway_stage(profile_dict)
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.flush()
    # Persist the graded result before calling the model again: on SQLite a write
    # transaction blocks every other writer, and holding one across a multi-second
    # model call made concurrent requests (and the audit writer) hit lock timeouts.
    db.commit()

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
    return _submission_response(session, score, recommendation)


@router.get("/{session_id}/result")
def get_result(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    session = _get_session(db, session_id)
    require_student_access(session.student_id, user)
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
                "updated_at": answer.updated_at,
            }
            for answer in session.answers
        ],
        "required_steps": REQUIRED_REASONING_STEPS,
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


def _answer_text(session: CaseSession, step: str) -> str:
    for answer in session.answers:
        if answer.step == step:
            return answer.answer_text
    return ""


def _tutor_turns(db: Session, session_id: int, step: str) -> list[dict]:
    rows = (
        db.query(TutorTurn)
        .filter(TutorTurn.session_id == session_id, TutorTurn.step == step)
        .order_by(TutorTurn.turn_index.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "step": row.step,
            "turn_index": row.turn_index,
            "role": row.role,
            "message": row.message,
            "state": json.loads(row.tutor_state_json or "{}"),
            "created_at": row.created_at,
        }
        for row in rows
    ]


def _tutor_analysis_text(session: CaseSession, step: str, turns: list[dict]) -> str:
    """What the tutor reasons about: the saved answer plus the student's replies."""

    parts = [_answer_text(session, step)]
    parts.extend(turn["message"] for turn in turns if turn["role"] == "student")
    return "\n".join(part for part in parts if part)


def _record_tutor_turn(
    db: Session,
    session: CaseSession,
    step: str,
    message: str | None,
    answer_override: str | None = None,
) -> dict:
    turns = _tutor_turns(db, session.id, step)
    next_index = (turns[-1]["turn_index"] + 1) if turns else 0

    session_tutor_turns = (
        db.query(TutorTurn)
        .filter(TutorTurn.session_id == session.id, TutorTurn.role == "tutor")
        .count()
    )
    if session_tutor_turns >= MAX_COACH_TURNS_PER_SESSION:
        raise HTTPException(
            status_code=429,
            detail=f"Coaching limit reached for this session ({MAX_COACH_TURNS_PER_SESSION} questions).",
        )

    student_message = (message or "").strip()
    if student_message:
        db.add(
            TutorTurn(
                session_id=session.id,
                step=step,
                turn_index=next_index,
                role="student",
                message=student_message[:2000],
                tutor_state_json="{}",
            )
        )
        next_index += 1
        db.commit()
        turns = _tutor_turns(db, session.id, step)

    analysis_text = answer_override if answer_override is not None else _tutor_analysis_text(session, step, turns)
    state = build_reasoning_state(serialize_case_for_student(session.case), step, analysis_text, turns)
    completion = state["completion_state"]

    if completion in {"coverage_sufficient", "max_turns_reached"}:
        db.commit()
        return {
            "step": step,
            "turns": turns,
            "state": state,
            "tutor_question": None,
            "stopped_reason": completion,
        }

    with ai_invocation(
        "tutor_question",
        session_id=session.id,
        student_id=session.student_id,
        evidence_ref=f"case_session:{session.id}:step:{step}",
    ):
        question = next_tutor_question(serialize_case(session.case), step, analysis_text, state)
    # The stored snapshot describes the conversation including this question.
    state = {**state, "turn_count": state["turn_count"] + 1}
    db.add(
        TutorTurn(
            session_id=session.id,
            step=step,
            turn_index=next_index,
            role="tutor",
            message=question,
            tutor_state_json=dumps_json(state),
        )
    )
    db.commit()
    return {
        "step": step,
        "turns": _tutor_turns(db, session.id, step),
        "state": state,
        "tutor_question": question,
        "stopped_reason": None,
    }


def _serialize_session(session: CaseSession) -> dict:
    return {
        "id": session.id,
        "student": serialize_student(session.student),
        "case": serialize_case_for_student(session.case),
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


def _submission_response(session: CaseSession, score: Score, recommendation: dict | None = None) -> dict:
    return {
        "score_id": score.id,
        "session_id": session.id,
        "summary": {
            "total_score": score.total_score,
            "strengths": score.strengths,
            "weaknesses": score.weaknesses,
            "evaluation_mode": score.evaluation_mode,
            "degraded": score.degraded,
            "next_recommendation": recommendation,
        },
    }
