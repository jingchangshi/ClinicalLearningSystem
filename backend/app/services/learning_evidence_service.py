from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.models import (
    Case,
    CaseSession,
    ClinicalSkill,
    GuidelineDocument,
    GuidelineLearningSession,
    KnowledgeProgress,
    KnowledgeUnit,
    LearningEvidenceEvent,
    SkillSession,
    SPCase,
    SPSession,
    Student,
)
from app.services.display_labels import (
    competency_changes,
    event_label,
    module_label,
)
from app.services.serializers import loads_json

# A teacher reads the evidence list to see a story, not to scroll a log. The
# page shows the newest few and expands on demand; nothing is deleted.
EVIDENCE_EVENT_PAGE_SIZE = 10
GROWTH_TREND_POINT_LIMIT = 40


def student_case_sessions(db: Session, student_id: int) -> list[CaseSession]:
    """Every case session of one learner, with its case and score already loaded.

    Touching ``session.case`` / ``session.score`` inside a loop is a lazy load per
    row: one pathway page issued 161 SQL statements that way, which dominated the
    request's CPU (and Python's GIL turns that CPU into latency for everyone
    else). Three statements total is the same data.
    """

    return (
        db.query(CaseSession)
        .options(selectinload(CaseSession.case), selectinload(CaseSession.score))
        .filter(CaseSession.student_id == student_id)
        .order_by(CaseSession.started_at.desc())
        .all()
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
                "label": module_label("knowledge"),
                "completed": sum(1 for item in knowledge if item.status == "completed"),
                "latest_score": _latest_value(knowledge, "quiz_score"),
            },
            {
                "module": "skill",
                "label": module_label("skill"),
                "completed": sum(1 for item in skills if item.status == "completed"),
                "latest_score": _latest_value(skills, "score"),
            },
            {
                "module": "case",
                "label": module_label("case"),
                "completed": sum(1 for item in cases if item.status == "completed"),
                "latest_score": _latest_case_score(cases),
            },
            {
                "module": "guideline",
                "label": module_label("guideline"),
                "completed": len(guidelines),
                "latest_score": _latest_value(guidelines, "score"),
            },
            {
                "module": "sp",
                "label": module_label("sp"),
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


def build_student_evidence_events(db: Session, student_id: int, limit: int | None = None) -> list[dict]:
    """One student's learning evidence, newest first, already readable.

    ``limit=None`` returns everything the page may expand to; the caller decides
    what to show by default. No row is dropped from the database — this is a
    presentation slice, and the counts next to ``查看全部`` come from the rows
    that were loaded.
    """

    rows = (
        db.query(LearningEvidenceEvent)
        .filter(LearningEvidenceEvent.student_id == student_id)
        .order_by(LearningEvidenceEvent.created_at.desc())
        .all()
    )
    if limit is not None:
        rows = rows[:limit]
    titles = _activity_titles(db, rows)
    return [_serialize_event(row, titles) for row in rows]


def build_growth_trend(db: Session, student_id: int) -> list[dict]:
    """Training score over time — a real series, not a stack of module cards.

    Only events that carry both a score and a competency change are points. A
    teacher-confirmed score is provenance for an existing result, not a new
    training session, so it never becomes a point of its own.
    """

    events = (
        db.query(LearningEvidenceEvent)
        .filter(LearningEvidenceEvent.student_id == student_id)
        .filter(LearningEvidenceEvent.event_type != "teacher_score_confirmed")
        .filter(LearningEvidenceEvent.score.isnot(None))
        .order_by(LearningEvidenceEvent.created_at.asc())
        .all()
    )
    points = []
    for event in events:
        updates = loads_json(event.competency_updates_json, {})
        if not updates:
            continue
        points.append(
            {
                "event_id": event.id,
                "module_type": event.module_type,
                "module_label": module_label(event.module_type),
                "event_type": event.event_type,
                "event_label": event_label(event.event_type),
                "score": event.score,
                "created_at": event.created_at,
                "competency_changes": competency_changes(updates),
            }
        )
    if len(points) <= GROWTH_TREND_POINT_LIMIT:
        return points
    return points[-GROWTH_TREND_POINT_LIMIT:]


def _activity_titles(db: Session, events: list[LearningEvidenceEvent]) -> dict[int, str]:
    """``{evidence_event_id: 训练内容}`` with one batched query per module.

    The source table name is an internal detail; the teacher needs the title of
    what was actually trained.
    """

    titles: dict[int, str] = {}
    by_source: dict[str, dict[int, str]] = {}

    case_session_ids = [event.session_id for event in events if event.module_type == "case" and event.session_id]
    if case_session_ids:
        rows = (
            db.query(CaseSession.id, Case.title)
            .join(Case, Case.id == CaseSession.case_id)
            .filter(CaseSession.id.in_(case_session_ids))
            .all()
        )
        by_source["case"] = {row[0]: row[1] for row in rows}

    knowledge_ids = [event.source_id for event in events if event.module_type == "knowledge"]
    if knowledge_ids:
        rows = (
            db.query(KnowledgeProgress.id, KnowledgeUnit.title)
            .join(KnowledgeUnit, KnowledgeUnit.id == KnowledgeProgress.knowledge_unit_id)
            .filter(KnowledgeProgress.id.in_(knowledge_ids))
            .all()
        )
        by_source["knowledge"] = {row[0]: row[1] for row in rows}

    skill_ids = [event.source_id for event in events if event.module_type == "skill"]
    if skill_ids:
        rows = (
            db.query(SkillSession.id, ClinicalSkill.title)
            .join(ClinicalSkill, ClinicalSkill.id == SkillSession.skill_id)
            .filter(SkillSession.id.in_(skill_ids))
            .all()
        )
        by_source["skill"] = {row[0]: row[1] for row in rows}

    guideline_ids = [event.source_id for event in events if event.module_type == "guideline"]
    if guideline_ids:
        rows = (
            db.query(GuidelineLearningSession.id, GuidelineDocument.title)
            .join(GuidelineDocument, GuidelineDocument.id == GuidelineLearningSession.guideline_id)
            .filter(GuidelineLearningSession.id.in_(guideline_ids))
            .all()
        )
        by_source["guideline"] = {row[0]: row[1] for row in rows}

    sp_ids = [event.source_id for event in events if event.module_type == "sp"]
    if sp_ids:
        rows = (
            db.query(SPSession.id, SPCase.title)
            .join(SPCase, SPCase.id == SPSession.sp_case_id)
            .filter(SPSession.id.in_(sp_ids))
            .all()
        )
        by_source["sp"] = {row[0]: row[1] for row in rows}

    for event in events:
        source_id = event.session_id if event.module_type == "case" else event.source_id
        title = by_source.get(event.module_type, {}).get(source_id)
        if title:
            titles[event.id] = title
    return titles


def _serialize_event(event: LearningEvidenceEvent, titles: dict[int, str] | None = None) -> dict:
    """What a teacher reads. Internal pointers stay out of the payload."""

    updates = loads_json(event.competency_updates_json, {})
    return {
        "id": event.id,
        "student_id": event.student_id,
        "module_type": event.module_type,
        "module_label": module_label(event.module_type),
        "activity_title": (titles or {}).get(event.id),
        "session_id": event.session_id,
        "event_type": event.event_type,
        "event_label": event_label(event.event_type),
        "score": event.score,
        "competency_changes": competency_changes(updates),
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
