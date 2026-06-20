from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    student_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    class_name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(100), nullable=False)

    sessions: Mapped[list["CaseSession"]] = relationship(back_populates="student")
    competency_profile: Mapped["CompetencyProfile"] = relationship(
        back_populates="student", uselist=False, cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["LearningRecommendation"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    disease_category: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    learning_objectives: Mapped[str] = mapped_column(Text, nullable=False)
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False)
    history: Mapped[str] = mapped_column(Text, nullable=False)
    physical_exam: Mapped[str] = mapped_column(Text, nullable=False)
    lab_results: Mapped[str] = mapped_column(Text, nullable=False)
    imaging: Mapped[str] = mapped_column(Text, nullable=False)
    standard_diagnosis: Mapped[str] = mapped_column(Text, nullable=False)
    differential_diagnosis: Mapped[str] = mapped_column(Text, nullable=False)
    treatment_plan: Mapped[str] = mapped_column(Text, nullable=False)
    rubric: Mapped[str] = mapped_column(Text, nullable=False)

    sessions: Mapped[list["CaseSession"]] = relationship(back_populates="case")


class CaseSession(Base):
    __tablename__ = "case_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student: Mapped["Student"] = relationship(back_populates="sessions")
    case: Mapped["Case"] = relationship(back_populates="sessions")
    answers: Mapped[list["StudentAnswer"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    ai_messages: Mapped[list["AIMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    score: Mapped["Score"] = relationship(
        back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("case_sessions.id"), nullable=False)
    step: Mapped[str] = mapped_column(String(100), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["CaseSession"] = relationship(back_populates="answers")


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("case_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_step: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["CaseSession"] = relationship(back_populates="ai_messages")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("case_sessions.id"), nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    medical_knowledge: Mapped[float] = mapped_column(Float, nullable=False)
    key_information: Mapped[float] = mapped_column(Float, nullable=False)
    differential_diagnosis: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_integration: Mapped[float] = mapped_column(Float, nullable=False)
    clinical_decision: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_based_medicine: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    strengths: Mapped[str] = mapped_column(Text, nullable=False)
    weaknesses: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["CaseSession"] = relationship(back_populates="score")


class CompetencyProfile(Base):
    __tablename__ = "competency_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    medical_knowledge: Mapped[float] = mapped_column(Float, nullable=False)
    key_information: Mapped[float] = mapped_column(Float, nullable=False)
    differential_diagnosis: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_integration: Mapped[float] = mapped_column(Float, nullable=False)
    clinical_decision: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_based_medicine: Mapped[float] = mapped_column(Float, nullable=False)
    learning_engagement: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["Student"] = relationship(back_populates="competency_profile")


class LearningRecommendation(Base):
    __tablename__ = "learning_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    recommended_case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), nullable=False)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    pathway_stage: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["Student"] = relationship(back_populates="recommendations")
    recommended_case: Mapped["Case"] = relationship()
