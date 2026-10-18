"""Independent assessment persistence; intentionally separate from CaseSession/Score."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class AssessmentForm(Base):
    __tablename__ = "assessment_forms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    stages_json: Mapped[str] = mapped_column(Text, nullable=False)
    key_json: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_json: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="PENDING_REAL_REVIEW", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AssessmentSitting(Base):
    __tablename__ = "assessment_sittings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    form_id: Mapped[int] = mapped_column(ForeignKey("assessment_forms.id"), nullable=False)
    cohort_code: Mapped[str] = mapped_column(String(70), nullable=False)
    study_group: Mapped[str] = mapped_column(String(20), nullable=False)
    timepoint: Mapped[str] = mapped_column(String(5), nullable=False)
    blind_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="assigned", nullable=False)
    stage_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    __table_args__ = (UniqueConstraint("student_id", "timepoint", name="uq_assess_student_timepoint"),)

class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sitting_id: Mapped[int] = mapped_column(ForeignKey("assessment_sittings.id"), nullable=False)
    stage_index: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("sitting_id", "stage_index", name="uq_assess_answer_stage"),)

class AssessmentReview(Base):
    __tablename__ = "assessment_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sitting_id: Mapped[int] = mapped_column(ForeignKey("assessment_sittings.id"), nullable=False)
    rater_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    scores_json: Mapped[str] = mapped_column(Text, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("sitting_id", "rater_user_id", name="uq_assess_independent_rater"),)
