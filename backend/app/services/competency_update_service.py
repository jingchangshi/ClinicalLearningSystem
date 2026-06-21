from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import CompetencyProfile, LearningEvidenceEvent, Student
from app.services.serializers import dumps_json

UPDATE_WEIGHT = 0.3
AI_FORMATIVE_NOTICE = "AI形成性评价，仅供教学参考，最终评价由教师确认。"


def update_competency_from_knowledge(
    db: Session,
    student_id: int,
    quiz_score: float,
    source_id: int,
) -> LearningEvidenceEvent:
    return _update_competency(
        db,
        student_id=student_id,
        module_type="knowledge",
        module_id=None,
        session_id=None,
        event_type="knowledge_quiz_submitted",
        source_table="knowledge_progress",
        source_id=source_id,
        score=quiz_score,
        updates={"medical_knowledge": quiz_score},
        payload={"quiz_score": quiz_score, "notice": AI_FORMATIVE_NOTICE},
    )


def update_competency_from_skill(
    db: Session,
    student_id: int,
    score: float,
    detail: dict,
    source_id: int,
) -> LearningEvidenceEvent:
    return _update_competency(
        db,
        student_id=student_id,
        module_type="skill",
        module_id=None,
        session_id=source_id,
        event_type="skill_session_submitted",
        source_table="skill_sessions",
        source_id=source_id,
        score=score,
        updates={"skill_operation": score, "clinical_decision": detail.get("safety_score", score)},
        payload={**detail, "notice": AI_FORMATIVE_NOTICE},
    )


def update_competency_from_case(
    db: Session,
    student_id: int,
    score: dict,
    source_id: int,
) -> LearningEvidenceEvent:
    updates = {
        "medical_knowledge": score["medical_knowledge"],
        "key_information": score["key_information"],
        "differential_diagnosis": score["differential_diagnosis"],
        "evidence_integration": score["evidence_integration"],
        "clinical_decision": score["clinical_decision"],
        "evidence_based_medicine": score["evidence_based_medicine"],
    }
    return _update_competency(
        db,
        student_id=student_id,
        module_type="case",
        module_id=None,
        session_id=source_id,
        event_type="case_session_scored",
        source_table="case_sessions",
        source_id=source_id,
        score=score["total_score"],
        updates=updates,
        payload={**score, "notice": AI_FORMATIVE_NOTICE},
    )


def update_competency_from_guideline(
    db: Session,
    student_id: int,
    score: float,
    detail: dict,
    source_id: int,
) -> LearningEvidenceEvent:
    clinical_decision_score = round(
        (detail.get("clinical_applicability", score) + detail.get("risk_individualization", score)) / 2,
        1,
    )
    return _update_competency(
        db,
        student_id=student_id,
        module_type="guideline",
        module_id=None,
        session_id=source_id,
        event_type="guideline_pico_submitted",
        source_table="guideline_learning_sessions",
        source_id=source_id,
        score=score,
        updates={"evidence_based_medicine": score, "clinical_decision": clinical_decision_score},
        payload={**detail, "notice": AI_FORMATIVE_NOTICE},
    )


def update_competency_from_sp(
    db: Session,
    student_id: int,
    scoring: dict,
    source_id: int,
) -> LearningEvidenceEvent:
    return _update_competency(
        db,
        student_id=student_id,
        module_type="sp",
        module_id=None,
        session_id=source_id,
        event_type="sp_osce_submitted",
        source_table="sp_sessions",
        source_id=source_id,
        score=scoring["total_score"],
        updates={
            "key_information": scoring["history_taking_score"],
            "differential_diagnosis": scoring["reasoning_score"],
            "communication": scoring["communication_score"],
            "humanistic_care": scoring["humanistic_care_score"],
        },
        payload={**scoring, "notice": AI_FORMATIVE_NOTICE},
    )


def _update_competency(
    db: Session,
    *,
    student_id: int,
    module_type: str,
    module_id: int | None,
    session_id: int | None,
    event_type: str,
    source_table: str,
    source_id: int,
    score: float | None,
    updates: dict[str, float],
    payload: dict[str, Any],
) -> LearningEvidenceEvent:
    student = db.get(Student, student_id)
    if not student or not student.competency_profile:
        raise ValueError("Student competency profile not found")
    profile = student.competency_profile
    competency_updates = {}
    for key, module_score in updates.items():
        before = _profile_value(profile, key)
        after = round(before * (1 - UPDATE_WEIGHT) + module_score * UPDATE_WEIGHT, 1)
        setattr(profile, key, after)
        competency_updates[key] = {
            "before": before,
            "after": after,
            "delta": round(after - before, 1),
            "module_score": round(module_score, 1),
        }
    profile.learning_engagement = min(100, round(profile.learning_engagement + 2, 1))
    profile.updated_at = datetime.utcnow()
    event = LearningEvidenceEvent(
        student_id=student_id,
        module_type=module_type,
        module_id=module_id,
        session_id=session_id,
        event_type=event_type,
        source_table=source_table,
        source_id=source_id,
        score=score,
        competency_updates_json=dumps_json(competency_updates),
        evidence_payload_json=dumps_json(payload),
    )
    db.add(event)
    db.flush()
    return event


def _profile_value(profile: CompetencyProfile, key: str) -> float:
    value = getattr(profile, key, None)
    if value is None:
        return 75
    return float(value)
