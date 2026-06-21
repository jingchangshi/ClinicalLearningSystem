from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ClinicalSkill, SkillSession, Student
from app.services.competency_update_service import update_competency_from_skill
from app.services.serializers import (
    dumps_json,
    loads_json,
    serialize_skill,
    serialize_skill_session,
    serialize_skill_summary,
)

router = APIRouter(prefix="/api", tags=["skills"])


class SkillSessionStartRequest(BaseModel):
    student_id: int


class SkillSessionSubmitRequest(BaseModel):
    submitted_steps: list[str]


@router.get("/skills")
def list_skills(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_skill_summary(skill) for skill in db.query(ClinicalSkill).all()]


@router.get("/skills/{skill_id}")
def get_skill(skill_id: int, db: Session = Depends(get_db)) -> dict:
    skill = db.get(ClinicalSkill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return serialize_skill(skill)


@router.post("/skills/{skill_id}/sessions/start")
def start_skill_session(
    skill_id: int,
    payload: SkillSessionStartRequest,
    db: Session = Depends(get_db),
) -> dict:
    if not db.get(Student, payload.student_id):
        raise HTTPException(status_code=404, detail="Student not found")
    if not db.get(ClinicalSkill, skill_id):
        raise HTTPException(status_code=404, detail="Skill not found")
    session = SkillSession(student_id=payload.student_id, skill_id=skill_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return serialize_skill_session(session)


@router.post("/skill-sessions/{session_id}/submit")
def submit_skill_session(
    session_id: int,
    payload: SkillSessionSubmitRequest,
    db: Session = Depends(get_db),
) -> dict:
    session = db.get(SkillSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Skill session not found")

    expected_steps = loads_json(session.skill.steps, [])
    common_errors = loads_json(session.skill.common_errors, [])
    result = _score_steps(expected_steps, payload.submitted_steps, common_errors)
    session.submitted_steps = dumps_json(payload.submitted_steps)
    session.score = result["score"]
    session.feedback = result["feedback"]
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.flush()
    update_competency_from_skill(db, session.student_id, result["score"], result["detail"], session.id)
    db.commit()
    db.refresh(session)

    return {
        **result,
        "session": serialize_skill_session(session),
    }


def _score_steps(expected_steps: list[str], submitted_steps: list[str], common_errors: list[str]) -> dict:
    normalized_expected = [_normalize(step) for step in expected_steps]
    normalized_submitted = [_normalize(step) for step in submitted_steps if step.strip()]
    matched_sequence = _matched_expected_indices(normalized_expected, normalized_submitted)
    matched_indices = set(matched_sequence)
    missed_steps = [
        step for index, step in enumerate(expected_steps) if index not in matched_indices
    ]
    completeness_score = _percentage(len(matched_indices), len(expected_steps))
    order_score = _order_score(matched_sequence)
    safety_score = _safety_score(normalized_submitted)
    score = round(completeness_score * 0.55 + order_score * 0.25 + safety_score * 0.2, 1)

    triggered_errors = [
        error for error in common_errors if _contains_keywords(normalized_submitted, _normalize(error))
    ]
    feedback = _skill_feedback(score, missed_steps, safety_score, triggered_errors)
    return {
        "score": score,
        "feedback": feedback,
        "missed_steps": missed_steps,
        "common_errors": triggered_errors or common_errors[:2],
        "detail": {
            "completeness_score": completeness_score,
            "order_score": order_score,
            "safety_score": safety_score,
        },
    }


def _matched_expected_indices(expected: list[str], submitted: list[str]) -> list[int]:
    matched: list[int] = []
    for answer in submitted:
        for index, step in enumerate(expected):
            if index in matched:
                continue
            if _step_matches(step, answer):
                matched.append(index)
                break
    return matched


def _step_matches(expected_step: str, submitted_step: str) -> bool:
    expected_tokens = _tokens(expected_step)
    if not expected_tokens:
        return False
    hits = sum(1 for token in expected_tokens if token in submitted_step)
    return hits >= max(1, min(2, len(expected_tokens)))


def _tokens(value: str) -> list[str]:
    return [token for token in value.replace("，", " ").replace("、", " ").split() if len(token) >= 2]


def _normalize(value: str) -> str:
    return value.strip().lower()


def _percentage(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(value / total * 100, 1)


def _order_score(matched_indices: list[int]) -> float:
    if len(matched_indices) <= 1:
        return 100.0 if matched_indices else 0.0
    ordered_pairs = sum(
        1 for left, right in zip(matched_indices, matched_indices[1:]) if left <= right
    )
    return round(ordered_pairs / (len(matched_indices) - 1) * 100, 1)


def _safety_score(submitted_steps: list[str]) -> float:
    joined = " ".join(submitted_steps)
    safety_keywords = ["无菌", "消毒", "知情", "同意", "禁忌", "凝血", "轻柔", "送检", "压迫", "记录"]
    hits = sum(1 for keyword in safety_keywords if keyword in joined)
    return round(min(100.0, hits / 4 * 100), 1)


def _contains_keywords(submitted_steps: list[str], error: str) -> bool:
    return any(token in " ".join(submitted_steps) for token in _tokens(error))


def _skill_feedback(score: float, missed_steps: list[str], safety_score: float, errors: list[str]) -> str:
    messages = []
    if score >= 85:
        messages.append("技能流程完整，顺序和安全意识较稳定。")
    elif score >= 70:
        messages.append("主要步骤基本覆盖，但仍需强化流程连贯性。")
    else:
        messages.append("关键步骤遗漏较多，建议按标准流程重新练习。")
    if missed_steps:
        messages.append(f"需补充：{'；'.join(missed_steps[:3])}。")
    if safety_score < 80:
        messages.append("需更明确体现知情同意、禁忌证评估、无菌/安全监测和标本处理。")
    if errors:
        messages.append(f"注意避免：{'；'.join(errors[:2])}。")
    return "".join(messages)
