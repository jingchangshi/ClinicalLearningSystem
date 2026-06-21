from sqlalchemy.orm import Session

from app.models import (
    CaseSession,
    GuidelineLearningSession,
    KnowledgeProgress,
    LearningEvidenceEvent,
    SkillSession,
    SPSession,
    Student,
)
from app.services.serializers import loads_json


def build_student_evidence_summary(db: Session, student_id: int) -> dict:
    knowledge = (
        db.query(KnowledgeProgress)
        .filter(KnowledgeProgress.student_id == student_id)
        .order_by(KnowledgeProgress.updated_at.desc())
        .all()
    )
    skills = (
        db.query(SkillSession)
        .filter(SkillSession.student_id == student_id)
        .order_by(SkillSession.created_at.desc())
        .all()
    )
    cases = (
        db.query(CaseSession)
        .filter(CaseSession.student_id == student_id)
        .order_by(CaseSession.started_at.desc())
        .all()
    )
    guidelines = (
        db.query(GuidelineLearningSession)
        .filter(GuidelineLearningSession.student_id == student_id)
        .order_by(GuidelineLearningSession.created_at.desc())
        .all()
    )
    sp_sessions = (
        db.query(SPSession)
        .filter(SPSession.student_id == student_id)
        .order_by(SPSession.started_at.desc())
        .all()
    )
    return {
        "student_id": student_id,
        "evidence_summary": [
            {
                "module": "knowledge",
                "label": "知识测验",
                "completed": sum(1 for item in knowledge if item.status == "completed"),
                "latest_score": _latest_value(knowledge, "quiz_score"),
            },
            {
                "module": "skill",
                "label": "技能步骤",
                "completed": sum(1 for item in skills if item.status == "completed"),
                "latest_score": _latest_value(skills, "score"),
            },
            {
                "module": "case",
                "label": "病例推理",
                "completed": sum(1 for item in cases if item.status == "completed"),
                "latest_score": _latest_case_score(cases),
            },
            {
                "module": "guideline",
                "label": "指南PICO",
                "completed": len(guidelines),
                "latest_score": _latest_value(guidelines, "score"),
            },
            {
                "module": "sp",
                "label": "SP问诊",
                "completed": sum(1 for item in sp_sessions if item.status == "completed"),
                "latest_score": _latest_value(sp_sessions, "total_score"),
            },
        ],
    }


def build_class_training_summary(db: Session) -> dict:
    knowledge = db.query(KnowledgeProgress).filter(KnowledgeProgress.status == "completed").count()
    skill = db.query(SkillSession).filter(SkillSession.status == "completed").count()
    case = db.query(CaseSession).filter(CaseSession.status == "completed").count()
    guideline = db.query(GuidelineLearningSession).count()
    sp = db.query(SPSession).filter(SPSession.status == "completed").count()
    return {
        "training_total_count": knowledge + skill + case + guideline + sp,
        "module_counts": {
            "knowledge": knowledge,
            "skill": skill,
            "case": case,
            "guideline": guideline,
            "sp": sp,
        },
    }


def build_class_heatmap(db: Session) -> list[dict]:
    rows = []
    for student in db.query(Student).all():
        profile = student.competency_profile
        if not profile:
            continue
        rows.append(
            {
                "student_id": student.id,
                "student_name": student.name,
                "medical_knowledge": profile.medical_knowledge,
                "skill_operation": profile.skill_operation,
                "key_information": profile.key_information,
                "differential_diagnosis": profile.differential_diagnosis,
                "evidence_integration": profile.evidence_integration,
                "clinical_decision": profile.clinical_decision,
                "evidence_based_medicine": profile.evidence_based_medicine,
                "communication": profile.communication,
                "humanistic_care": profile.humanistic_care,
            }
        )
    return rows


def build_student_evidence_events(db: Session, student_id: int) -> list[dict]:
    rows = (
        db.query(LearningEvidenceEvent)
        .filter(LearningEvidenceEvent.student_id == student_id)
        .order_by(LearningEvidenceEvent.created_at.desc())
        .limit(50)
        .all()
    )
    return [_serialize_event(row) for row in rows]


def build_growth_trend(db: Session, student_id: int) -> list[dict]:
    events = (
        db.query(LearningEvidenceEvent)
        .filter(LearningEvidenceEvent.student_id == student_id)
        .order_by(LearningEvidenceEvent.created_at.asc())
        .all()
    )
    trend = []
    for event in events:
        updates = loads_json(event.competency_updates_json, {})
        if not updates:
            continue
        trend.append(
            {
                "event_id": event.id,
                "module_type": event.module_type,
                "score": event.score,
                "created_at": event.created_at,
                "average_after": round(
                    sum(item.get("after", 0) for item in updates.values()) / len(updates),
                    1,
                ),
            }
        )
    return trend


def _serialize_event(event: LearningEvidenceEvent) -> dict:
    return {
        "id": event.id,
        "student_id": event.student_id,
        "module_type": event.module_type,
        "module_id": event.module_id,
        "session_id": event.session_id,
        "event_type": event.event_type,
        "source_table": event.source_table,
        "source_id": event.source_id,
        "score": event.score,
        "competency_updates": loads_json(event.competency_updates_json, {}),
        "evidence_payload": loads_json(event.evidence_payload_json, {}),
        "created_at": event.created_at,
    }


def latest_sp_scores(db: Session, student_id: int) -> dict:
    session = (
        db.query(SPSession)
        .filter(SPSession.student_id == student_id, SPSession.status == "completed")
        .order_by(SPSession.completed_at.desc())
        .first()
    )
    if not session:
        return {"communication": 75, "humanistic_care": 75}
    return {
        "communication": session.communication_score or 75,
        "humanistic_care": session.humanistic_care_score or 75,
    }


def _latest_value(items: list, attr: str) -> float | None:
    for item in items:
        value = getattr(item, attr)
        if value is not None:
            return round(value, 1)
    return None


def _latest_case_score(cases: list[CaseSession]) -> float | None:
    for session in cases:
        if session.score:
            return round(session.score.total_score, 1)
    return None
