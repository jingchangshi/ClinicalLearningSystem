from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    teacher_no: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="teacher", uselist=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["Student | None"] = relationship(back_populates="user")
    teacher: Mapped["Teacher | None"] = relationship(back_populates="user")


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
    knowledge_progress: Mapped[list["KnowledgeProgress"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    skill_sessions: Mapped[list["SkillSession"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    guideline_sessions: Mapped[list["GuidelineLearningSession"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    sp_sessions: Mapped[list["SPSession"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    user: Mapped["User"] = relationship(back_populates="student", uselist=False)


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
    skill_operation: Mapped[float] = mapped_column(Float, default=75, nullable=False)
    key_information: Mapped[float] = mapped_column(Float, nullable=False)
    differential_diagnosis: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_integration: Mapped[float] = mapped_column(Float, nullable=False)
    clinical_decision: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_based_medicine: Mapped[float] = mapped_column(Float, nullable=False)
    communication: Mapped[float] = mapped_column(Float, default=75, nullable=False)
    humanistic_care: Mapped[float] = mapped_column(Float, default=75, nullable=False)
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


class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(50), nullable=False)
    learning_objectives: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    key_points: Mapped[str] = mapped_column(Text, nullable=False)
    quiz_items: Mapped[str] = mapped_column(Text, nullable=False)
    related_case_ids: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    progress: Mapped[list["KnowledgeProgress"]] = relationship(
        back_populates="knowledge_unit", cascade="all, delete-orphan"
    )


class KnowledgeProgress(Base):
    __tablename__ = "knowledge_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    knowledge_unit_id: Mapped[int] = mapped_column(ForeignKey("knowledge_units.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="not_started")
    quiz_score: Mapped[float] = mapped_column(Float, default=0)
    mastery_score: Mapped[float] = mapped_column(Float, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["Student"] = relationship(back_populates="knowledge_progress")
    knowledge_unit: Mapped["KnowledgeUnit"] = relationship(back_populates="progress")


class ClinicalSkill(Base):
    __tablename__ = "clinical_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    indication: Mapped[str] = mapped_column(Text, nullable=False)
    contraindication: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[str] = mapped_column(Text, nullable=False)
    common_errors: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_rubric: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["SkillSession"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )


class SkillSession(Base):
    __tablename__ = "skill_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    skill_id: Mapped[int] = mapped_column(ForeignKey("clinical_skills.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="in_progress")
    submitted_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student: Mapped["Student"] = relationship(back_populates="skill_sessions")
    skill: Mapped["ClinicalSkill"] = relationship(back_populates="sessions")


class GuidelineDocument(Base):
    __tablename__ = "guideline_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    organization: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    disease_category: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommendations: Mapped[str] = mapped_column(Text, nullable=False)
    pico_examples: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["GuidelineLearningSession"]] = relationship(
        back_populates="guideline", cascade="all, delete-orphan"
    )


class GuidelineLearningSession(Base):
    __tablename__ = "guideline_learning_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    guideline_id: Mapped[int] = mapped_column(ForeignKey("guideline_documents.id"), nullable=False)
    clinical_question: Mapped[str] = mapped_column(Text, nullable=False)
    pico: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    student: Mapped["Student"] = relationship(back_populates="guideline_sessions")
    guideline: Mapped["GuidelineDocument"] = relationship(back_populates="sessions")


class SPCase(Base):
    __tablename__ = "sp_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    disease_category: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    patient_profile: Mapped[str] = mapped_column(Text, nullable=False)
    opening_statement: Mapped[str] = mapped_column(Text, nullable=False)
    hidden_history: Mapped[str] = mapped_column(Text, nullable=False)
    emotional_style: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_tasks: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_rubric: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sessions: Mapped[list["SPSession"]] = relationship(
        back_populates="sp_case", cascade="all, delete-orphan"
    )


class SPSession(Base):
    __tablename__ = "sp_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    sp_case_id: Mapped[int] = mapped_column(ForeignKey("sp_cases.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="in_progress")
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    diagnosis_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    communication_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    history_taking_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    humanistic_care_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    student: Mapped["Student"] = relationship(back_populates="sp_sessions")
    sp_case: Mapped["SPCase"] = relationship(back_populates="sessions")


class GeneratedCaseDraft(Base):
    __tablename__ = "generated_case_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    generated_payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LearningEvidenceEvent(Base):
    __tablename__ = "learning_evidence_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    module_type: Mapped[str] = mapped_column(String(50), nullable=False)
    module_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_table: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    competency_updates_json: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TeachingIntervention(Base):
    __tablename__ = "teaching_interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    target_ability: Mapped[str] = mapped_column(String(100), nullable=False)
    target_students_json: Mapped[str] = mapped_column(Text, nullable=False)
    intervention_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TeacherScoreReview(Base):
    __tablename__ = "teacher_score_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evidence_event_id: Mapped[int] = mapped_column(ForeignKey("learning_evidence_events.id"), nullable=False)
    ai_score: Mapped[float] = mapped_column(Float, nullable=False)
    teacher_score: Mapped[float] = mapped_column(Float, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    agreement_delta: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
