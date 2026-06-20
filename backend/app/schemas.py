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
