"""Deterministic replay of immutable learning evidence and teacher corrections."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import LearningEvidenceEvent, Student, TeacherScoreReview
from app.services.serializers import CORE_ABILITIES, loads_json

COMPETENCY_PROJECTOR_VERSION = "v1"
UPDATE_WEIGHT = 0.3


def reproject_competencies(db: Session, student_id: int) -> None:
    student = db.get(Student, student_id)
    if not student or not student.competency_profile:
        raise ValueError("Student competency profile not found")
    events = (
        db.query(LearningEvidenceEvent)
        .filter(LearningEvidenceEvent.student_id == student_id)
        .order_by(LearningEvidenceEvent.created_at.asc(), LearningEvidenceEvent.id.asc())
        .all()
    )
    profile = student.competency_profile
    corrections = {
        review.evidence_event_id: loads_json(review.confirmed_dimensions_json, {})
        for review in db.query(TeacherScoreReview)
        .join(LearningEvidenceEvent)
        .filter(LearningEvidenceEvent.student_id == student_id)
        .order_by(TeacherScoreReview.created_at.asc(), TeacherScoreReview.id.asc())
        .all()
    }
    replayed: set[str] = set()
    values: dict[str, float] = {}
    for event in events:
        updates = loads_json(event.competency_updates_json, {})
        replacement = corrections.get(event.id, {})
        for key, update in updates.items():
            if key not in replayed:
                values[key] = float(update.get("before", getattr(profile, key)))
                replayed.add(key)
            module_score = float(replacement.get(key, update.get("module_score", values[key])))
            values[key] = round(values[key] * (1 - UPDATE_WEIGHT) + module_score * UPDATE_WEIGHT, 1)
    for key, value in values.items():
        setattr(profile, key, value)
    profile.updated_at = datetime.utcnow()


def confirmed_total(dimensions: dict[str, float]) -> float:
    return round(sum(dimensions[key] for key in CORE_ABILITIES) / len(CORE_ABILITIES), 1)
