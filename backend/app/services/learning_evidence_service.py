from sqlalchemy.orm import Session

from app.models import (
    CaseSession,
    GuidelineLearningSession,
    KnowledgeProgress,
    SkillSession,
    SPSession,
    Student,
)


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
                "key_information": profile.key_information,
                "differential_diagnosis": profile.differential_diagnosis,
                "evidence_integration": profile.evidence_integration,
                "clinical_decision": profile.clinical_decision,
                "evidence_based_medicine": profile.evidence_based_medicine,
            }
        )
    return rows


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
