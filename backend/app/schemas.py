from datetime import datetime

from pydantic import BaseModel


class StudentRead(BaseModel):
    id: int
    name: str
    student_no: str
    class_name: str
    current_stage: str


class CaseRead(BaseModel):
    id: int
    title: str
    disease_category: str
    difficulty: str
    learning_objectives: list[str]
    chief_complaint: str
    history: str
    physical_exam: str
    lab_results: str
    imaging: str
    standard_diagnosis: str
    differential_diagnosis: list[str]
    treatment_plan: str
    rubric: dict


class CaseCreate(BaseModel):
    title: str
    disease_category: str
    difficulty: str
    learning_objectives: list[str]
    chief_complaint: str
    history: str
    physical_exam: str
    lab_results: str
    imaging: str
    standard_diagnosis: str
    differential_diagnosis: list[str]
    treatment_plan: str
    rubric: dict


class CompetencyRead(BaseModel):
    medical_knowledge: float
    key_information: float
    differential_diagnosis: float
    evidence_integration: float
    clinical_decision: float
    evidence_based_medicine: float
    learning_engagement: float
    updated_at: datetime


class SessionStartRequest(BaseModel):
    student_id: int
    case_id: int


class AnswerCreate(BaseModel):
    step: str
    answer_text: str


class CoachRequest(BaseModel):
    step: str
    answer_text: str


class ScoreRead(BaseModel):
    id: int
    total_score: float
    medical_knowledge: float
    key_information: float
    differential_diagnosis: float
    evidence_integration: float
    clinical_decision: float
    evidence_based_medicine: float
    feedback: str
    strengths: str
    weaknesses: str
    created_at: datetime


class KnowledgeUnitRead(BaseModel):
    id: int
    title: str
    category: str
    level: str
    learning_objectives: list[str]
    content: str
    key_points: list[str]
    quiz_items: list[dict]
    related_case_ids: list[int]
    created_at: datetime


class KnowledgeProgressRead(BaseModel):
    id: int
    student_id: int
    knowledge_unit_id: int
    status: str
    quiz_score: float
    mastery_score: float
    updated_at: datetime


class ClinicalSkillRead(BaseModel):
    id: int
    title: str
    category: str
    difficulty: str
    indication: str
    contraindication: str
    steps: list[str]
    common_errors: list[str]
    scoring_rubric: dict
    created_at: datetime


class SkillSessionRead(BaseModel):
    id: int
    student_id: int
    skill_id: int
    status: str
    submitted_steps: list[str] | None
    score: float | None
    feedback: str | None
    created_at: datetime
    completed_at: datetime | None


class GuidelineDocumentRead(BaseModel):
    id: int
    title: str
    organization: str
    year: int
    disease_category: str
    source_type: str
    summary: str
    recommendations: list[dict]
    pico_examples: list[dict]
    created_at: datetime


class GuidelineLearningSessionRead(BaseModel):
    id: int
    student_id: int
    guideline_id: int
    clinical_question: str
    pico: str
    answer: str
    score: float | None
    feedback: str | None
    created_at: datetime


class SPCaseRead(BaseModel):
    id: int
    title: str
    disease_category: str
    difficulty: str
    patient_profile: dict
    opening_statement: str
    hidden_history: dict
    emotional_style: str
    expected_tasks: list[str]
    scoring_rubric: dict
    created_at: datetime


class SPSessionRead(BaseModel):
    id: int
    student_id: int
    sp_case_id: int
    status: str
    transcript: list[dict]
    diagnosis_summary: str | None
    communication_score: float | None
    history_taking_score: float | None
    reasoning_score: float | None
    humanistic_care_score: float | None
    total_score: float | None
    feedback: str | None
    started_at: datetime
    completed_at: datetime | None


class GeneratedCaseDraftRead(BaseModel):
    id: int
    teacher_prompt: str
    generated_payload: dict
    status: str
    created_at: datetime
