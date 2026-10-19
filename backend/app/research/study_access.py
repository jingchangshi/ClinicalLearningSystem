"""Server-side study access policy shared by the ClinPath training entry points.

The study assigns a *whole teaching batch* to an arm (``app.research.randomization``).
A batch that the frozen ``StudyAllocation`` puts in the CBL arm must not receive the
ClinPath-only formative intervention — session creation, AI tutoring, training
submission and personalised recommendations — while the study is running. Keeping
that rule here, as one small explicit function, is deliberate: hiding frontend
navigation is not access control, and a permission framework for two arms would be
more machinery than the rule needs.

The rules, in order:

* Not enrolled in any active cohort, or the cohort has no frozen group draw yet:
  no restriction. The arm is never guessed (§3.3.10).
* Frozen arm ``clinpath``: no restriction.
* Frozen arm ``cbl``: restricted until the batch's teaching window has been
  recorded as finished. Before the window opens the batch is already enrolled and
  its arm is fixed, so the intervention stays closed; once the window is closed the
  pre-determined teaching plan governs whether full training opens.

Refusals never mention the arm or the cohort: a student learns that the training
step is closed, not which group they are in.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.assessment_models import StudyAllocation, StudyCohort, StudyEnrollment
from app.research import STUDY_GROUP_CBL, STUDY_GROUP_CLINPATH

KIND_CLUSTER = "cluster_group"
WINDOW_OPEN, WINDOW_NOT_STARTED, WINDOW_CLOSED, WINDOW_UNDETERMINED = (
    "open", "not_started", "closed", "undetermined")

RESTRICTED_CODE = "study_training_restricted"
RESTRICTED_MESSAGE = (
    "当前研究教学安排下，本账号暂不能使用该训练功能；独立在线考核不受影响。"
    "请按课程安排参加常规教学，如有疑问请联系任课教师。"
)


@dataclass(frozen=True)
class StudyAccess:
    """One student's study-standing decision. ``reason`` is for staff/evidence, never for students."""

    student_id: int
    enrolled: bool
    cohort_code: str | None
    data_origin: str | None
    group: str | None
    window_start: date | None
    window_end: date | None
    window_source: str | None
    window_state: str
    reason: str

    @property
    def restricted(self) -> bool:
        return self.group == STUDY_GROUP_CBL and self.window_state != WINDOW_CLOSED

    def as_dict(self) -> dict:
        """The auditable form used by the Research export (admin-only)."""
        return {
            "enrolled": self.enrolled, "cohort_code": self.cohort_code,
            "data_origin": self.data_origin, "study_group": self.group,
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "window_source": self.window_source, "window_state": self.window_state,
            "restricted": self.restricted, "reason": self.reason,
        }


def _frozen_group(db: Session, cohort_code: str, origin: str) -> str | None:
    """The arm the immutable cluster draw names for this cohort, or None if not frozen.

    ``app.assessment.design.design_for`` derives the same value for the assessment
    schedule; both read the same one-shot record, and ``test_study_access_isolation``
    asserts the two agree, so they cannot drift apart silently.
    """
    row = db.query(StudyAllocation).filter_by(kind=KIND_CLUSTER, data_origin=origin).first()
    if row is None:
        return None
    record = json.loads(row.record_json)
    if cohort_code in record.get("clinpath_cohorts", ()):
        return STUDY_GROUP_CLINPATH
    if cohort_code in record.get("cbl_cohorts", ()):
        return STUDY_GROUP_CBL
    return None


def _window(cohort: StudyCohort) -> tuple[date | None, date | None, str | None]:
    """Recorded dates drive the window; actual dates supersede planned ones."""
    if cohort.actual_start and cohort.actual_end:
        return cohort.actual_start, cohort.actual_end, "actual"
    if cohort.planned_start and cohort.planned_end:
        return cohort.planned_start, cohort.planned_end, "planned"
    return None, None, None


def _window_state(start: date | None, end: date | None, today: date) -> str:
    if start is None or end is None:
        return WINDOW_UNDETERMINED
    if today < start:
        return WINDOW_NOT_STARTED
    if today > end:
        return WINDOW_CLOSED
    return WINDOW_OPEN


def access_for(db: Session, student_id: int, *, today: date | None = None) -> StudyAccess:
    """Resolve one student's standing. Reads enrollment, the frozen draw and the cohort dates."""
    today = today or datetime.utcnow().date()
    enrollment = (
        db.query(StudyEnrollment)
        .filter(StudyEnrollment.student_id == student_id, StudyEnrollment.status == "enrolled")
        .first()
    )
    if enrollment is None:
        return StudyAccess(student_id, False, None, None, None, None, None, None,
                           WINDOW_UNDETERMINED, "not_enrolled")
    cohort = db.get(StudyCohort, enrollment.cohort_id)
    if cohort is None:
        return StudyAccess(student_id, False, None, None, None, None, None, None,
                           WINDOW_UNDETERMINED, "enrollment_without_cohort")
    group = _frozen_group(db, cohort.cohort_code, cohort.data_origin)
    start, end, source = _window(cohort)
    state = _window_state(start, end, today)
    if group is None:
        reason = "study_group_not_frozen"
    elif group == STUDY_GROUP_CBL:
        reason = f"cbl_arm_window_{state}"
    else:
        reason = "clinpath_arm"
    return StudyAccess(student_id, True, cohort.cohort_code, cohort.data_origin, group,
                       start, end, source, state, reason)


def refusal() -> HTTPException:
    return HTTPException(status_code=403, detail={"code": RESTRICTED_CODE, "message": RESTRICTED_MESSAGE})


def require_training_access(db: Session, student_id: int, *, today: date | None = None) -> None:
    """Refuse when this student may not use the ClinPath formative intervention right now."""
    if access_for(db, student_id, today=today).restricted:
        raise refusal()


def require_student_self_training_access(db: Session, user, student_id: int) -> None:
    """Gate a personalisation/competency read only when the requester *is* that student.

    Teachers and the study administrator keep their staff view of every learner;
    the restriction is about what the student receives, not what staff can audit.
    """
    if user.role != "student":
        return
    require_training_access(db, student_id)
