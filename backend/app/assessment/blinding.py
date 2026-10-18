"""What a blinded rater may see, in what order, and when blinding cannot be claimed."""
import hashlib
import json
import re
import secrets

from sqlalchemy.orm import Session

from app.assessment_models import ResearchCode, StudyCohort
from app.core.deidentify import redact_phi
from app.models import Student

RISK_TEACHES_COHORT = "TEACHES_COHORT"
RISK_NO_CONFLICT_RECORDED = "NO_CONFLICT_RECORDED"
RISK_UNVERIFIED = "UNVERIFIED_NO_COHORT_ROSTER"
# NO_CONFLICT_RECORDED only means "no conflict is on file"; it is never reported as "blind".
REDACTED = "[已去标识]"


def blinding_risk(db: Session, cohort_code: str, rater_ids: list[int]) -> str:
    cohort = db.query(StudyCohort).filter_by(cohort_code=cohort_code).first()
    if cohort is None:
        return RISK_UNVERIFIED
    teaching = set(json.loads(cohort.teaching_user_ids_json or "[]"))
    return RISK_TEACHES_COHORT if teaching & set(rater_ids) else RISK_NO_CONFLICT_RECORDED


def blind_order_key(rater_user_id: int, blind_code: str) -> str:
    """Stable per-rater shuffle: unrelated to submission order, sitting id or timepoint."""
    return hashlib.sha256(f"{rater_user_id}:{blind_code}".encode()).hexdigest()


def redact_answer(text: str, student: Student) -> tuple[str, int]:
    """Best-effort removal of identifiers the student typed into an answer.

    Students are told not to write identifying information; this is a safety net, not
    an anonymisation guarantee. The raw answer stays stored untouched.
    """
    count = 0
    for needle in {student.name.strip(), student.student_no.strip()}:
        if needle and needle in text:
            count += text.count(needle)
            text = text.replace(needle, REDACTED)
    text, kinds = redact_phi(text)
    return text, count + len(kinds)


def new_blind_code() -> str:
    return secrets.token_urlsafe(24)


def ensure_research_code(db: Session, student_id: int) -> str:
    row = db.query(ResearchCode).filter_by(student_id=student_id).first()
    if row is None:
        while True:
            code = "S" + secrets.token_hex(4).upper()
            if not db.query(ResearchCode).filter_by(study_student_code=code).first():
                break
        row = ResearchCode(student_id=student_id, study_student_code=code)
        db.add(row)
        db.flush()
    return row.study_student_code
