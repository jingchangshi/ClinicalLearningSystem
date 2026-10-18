"""Independent assessment persistence; intentionally separate from CaseSession/Score.

Nothing here is imported by, or imports, the Training scoring / competency /
recommendation services. All times are naive UTC (``app.assessment.timeutil``).
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.assessment.timeutil import utcnow
from app.database import Base


class AssessmentForm(Base):
    """One frozen version of a standardised case + question set + rubric."""

    __tablename__ = "assessment_forms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    stages_json: Mapped[str] = mapped_column(Text, nullable=False)
    key_json: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_json: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="PENDING_REAL_REVIEW", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    supersedes_form_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_forms.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("code", "version", name="uq_assess_form_code_version"),)


class AssessmentFormReviewer(Base):
    """Teachers the study admin invited to review (and, as a side effect, to see) a form."""

    __tablename__ = "assessment_form_reviewers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("assessment_forms.id"), nullable=False)
    teacher_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("form_id", "teacher_user_id", name="uq_assess_form_reviewer"),)


class AssessmentFormReview(Base):
    __tablename__ = "assessment_form_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("assessment_forms.id"), nullable=False)
    teacher_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # The exact content this teacher saw; approval is void if the content differs.
    form_content_sha256: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("form_id", "teacher_user_id", name="uq_assess_form_teacher"),)


class AssessmentSitting(Base):
    __tablename__ = "assessment_sittings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    form_id: Mapped[int] = mapped_column(ForeignKey("assessment_forms.id"), nullable=False)
    cohort_code: Mapped[str] = mapped_column(String(70), nullable=False)
    study_group: Mapped[str] = mapped_column(String(20), nullable=False)
    timepoint: Mapped[str] = mapped_column(String(5), nullable=False)
    rater_a_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    rater_b_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    blind_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # assigned | in_progress | submitted | expired | voided
    status: Mapped[str] = mapped_column(String(20), default="assigned", nullable=False)
    stage_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    # --- additions (20261018_09) ---
    data_origin: Mapped[str] = mapped_column(String(20), default="pilot_test", nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    retake_of_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_sittings.id"))
    form_order: Mapped[str | None] = mapped_column(String(1))
    adjudicator_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    blinding_risk: Mapped[str] = mapped_column(String(40), default="UNVERIFIED_NO_COHORT_ROSTER", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_saved_at: Mapped[datetime | None] = mapped_column(DateTime)
    extended_until: Mapped[datetime | None] = mapped_column(DateTime)
    closed_reason: Mapped[str | None] = mapped_column(String(30))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime)
    void_reason: Mapped[str | None] = mapped_column(Text)
    allocation_id: Mapped[int | None] = mapped_column(ForeignKey("study_allocations.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (
        # One live attempt per student and timepoint; a voided attempt (controlled
        # retake) no longer counts, so the research dataset can never hold two.
        Index("uq_assess_live_student_timepoint", "student_id", "timepoint", unique=True,
              sqlite_where=text("status != 'voided'")),
    )


class AssessmentAnswer(Base):
    """The final, immutable answer for one stage."""

    __tablename__ = "assessment_answers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sitting_id: Mapped[int] = mapped_column(ForeignKey("assessment_sittings.id"), nullable=False)
    stage_index: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    answer_sha256: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint("sitting_id", "stage_index", name="uq_assess_answer_stage"),)


class AssessmentAnswerRevision(Base):
    """Append-only history of every draft save and the final submission per stage."""

    __tablename__ = "assessment_answer_revisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sitting_id: Mapped[int] = mapped_column(ForeignKey("assessment_sittings.id"), nullable=False)
    stage_index: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # draft | final
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("sitting_id", "stage_index", "revision_no", name="uq_assess_answer_revision"),)


class AssessmentEvent(Base):
    """Per-sitting lifecycle trace: starts, resumes, timeouts, interruptions, refusals."""

    __tablename__ = "assessment_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sitting_id: Mapped[int] = mapped_column(ForeignKey("assessment_sittings.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_assess_events_sitting", "sitting_id"),)


class AssessmentReview(Base):
    __tablename__ = "assessment_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sitting_id: Mapped[int] = mapped_column(ForeignKey("assessment_sittings.id"), nullable=False)
    rater_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    scores_json: Mapped[str] = mapped_column(Text, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # --- additions (20261018_09) ---
    rater_slot: Mapped[str | None] = mapped_column(String(1))  # "A" | "B"
    rubric_version: Mapped[str | None] = mapped_column(String(80))
    weights_json: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime)
    voided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    void_reason: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        Index("uq_assess_live_rater", "sitting_id", "rater_user_id", unique=True,
              sqlite_where=text("voided_at IS NULL")),
    )


class AssessmentAdjudication(Base):
    """A third-party decision on a flagged disagreement; never rewrites the raw reviews."""

    __tablename__ = "assessment_adjudications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sitting_id: Mapped[int] = mapped_column(ForeignKey("assessment_sittings.id"), nullable=False, unique=True)
    adjudicator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    review_a_id: Mapped[int] = mapped_column(ForeignKey("assessment_reviews.id"), nullable=False)
    review_b_id: Mapped[int] = mapped_column(ForeignKey("assessment_reviews.id"), nullable=False)
    trigger_json: Mapped[str] = mapped_column(Text, nullable=False)
    scores_json: Mapped[str] = mapped_column(Text, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    adjudicated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AssessmentFinalScore(Base):
    """The locked final score of a sitting, with where it came from."""

    __tablename__ = "assessment_final_scores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sitting_id: Mapped[int] = mapped_column(ForeignKey("assessment_sittings.id"), nullable=False, unique=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    provenance: Mapped[str] = mapped_column(String(20), nullable=False)  # dual_mean | adjudicated
    review_a_id: Mapped[int] = mapped_column(ForeignKey("assessment_reviews.id"), nullable=False)
    review_b_id: Mapped[int] = mapped_column(ForeignKey("assessment_reviews.id"), nullable=False)
    adjudication_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_adjudications.id"))
    rubric_version: Mapped[str | None] = mapped_column(String(80))
    weights_json: Mapped[str] = mapped_column(Text, nullable=False)
    disagreement_json: Mapped[str] = mapped_column(Text, nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    locked_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    dataset_lock_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_dataset_locks.id"))


class AssessmentDatasetLock(Base):
    """A frozen, reproducible research dataset version (snapshot is stored verbatim)."""

    __tablename__ = "assessment_dataset_locks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_version: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    locked_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class AssessmentAuditLog(Base):
    """Append-only log of administrative and score-affecting actions (ids, never answer bodies)."""

    __tablename__ = "assessment_audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(80), nullable=False)
    detail_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ResearchCode(Base):
    """Pseudonymous study code; the mapping to the student is admin-only and audited."""

    __tablename__ = "research_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, unique=True)
    study_student_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StudyCohort(Base):
    """One complete seven-student teaching batch (never split across arms)."""

    __tablename__ = "study_cohorts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cohort_code: Mapped[str] = mapped_column(String(70), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    expected_size: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    planned_start: Mapped[date | None] = mapped_column(Date)
    planned_end: Mapped[date | None] = mapped_column(Date)
    actual_start: Mapped[date | None] = mapped_column(Date)
    actual_end: Mapped[date | None] = mapped_column(Date)
    # Teachers who teach this batch: a rater in this list cannot be called blind.
    teaching_user_ids_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    study_admin_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    data_origin: Mapped[str] = mapped_column(String(20), default="pilot_test", nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StudyAllocation(Base):
    """An immutable record of a form-order or cluster-group draw (see app.research)."""

    __tablename__ = "study_allocations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # form_order | cluster_group
    allocation_version: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    mode: Mapped[str] = mapped_column(String(30), nullable=False)  # randomized | quasi_experimental
    protocol_version: Mapped[str] = mapped_column(String(60), nullable=False)
    record_json: Mapped[str] = mapped_column(Text, nullable=False)
    record_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(20), nullable=False)
    executed_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # One draw per kind and data origin: there is no redraw.
    __table_args__ = (UniqueConstraint("kind", "data_origin", name="uq_study_alloc_kind_origin"),)


class StudyEnrollment(Base):
    """Membership of a student in exactly one cohort (a student can never be in two arms)."""

    __tablename__ = "study_enrollments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cohort_id: Mapped[int] = mapped_column(ForeignKey("study_cohorts.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), default="enrolled", nullable=False)  # enrolled | withdrawn | missing
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    enrolled_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
