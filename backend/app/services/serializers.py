import json
from typing import Any

from app.models import Case, CompetencyProfile, Score, Student

ABILITY_LABELS = {
    "medical_knowledge": "医学知识",
    "key_information": "关键信息提取",
    "differential_diagnosis": "鉴别诊断",
    "evidence_integration": "证据整合",
    "clinical_decision": "临床决策",
    "evidence_based_medicine": "循证医学",
    "learning_engagement": "学习投入",
}

CORE_ABILITIES = [
    "medical_knowledge",
    "key_information",
    "differential_diagnosis",
    "evidence_integration",
    "clinical_decision",
    "evidence_based_medicine",
]


def loads_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def dumps_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def serialize_student(student: Student) -> dict:
    return {
        "id": student.id,
        "name": student.name,
        "student_no": student.student_no,
        "class_name": student.class_name,
        "current_stage": student.current_stage,
    }


def serialize_case(case: Case) -> dict:
    return {
        "id": case.id,
        "title": case.title,
        "disease_category": case.disease_category,
        "difficulty": case.difficulty,
        "learning_objectives": loads_json(case.learning_objectives, []),
        "chief_complaint": case.chief_complaint,
        "history": case.history,
        "physical_exam": case.physical_exam,
        "lab_results": case.lab_results,
        "imaging": case.imaging,
        "standard_diagnosis": case.standard_diagnosis,
        "differential_diagnosis": loads_json(case.differential_diagnosis, []),
        "treatment_plan": case.treatment_plan,
        "rubric": loads_json(case.rubric, {}),
    }


def serialize_case_summary(case: Case) -> dict:
    return {
        "id": case.id,
        "title": case.title,
        "disease_category": case.disease_category,
        "difficulty": case.difficulty,
        "chief_complaint": case.chief_complaint,
        "learning_objectives": loads_json(case.learning_objectives, []),
    }


def serialize_profile(profile: CompetencyProfile) -> dict:
    return {
        "medical_knowledge": profile.medical_knowledge,
        "key_information": profile.key_information,
        "differential_diagnosis": profile.differential_diagnosis,
        "evidence_integration": profile.evidence_integration,
        "clinical_decision": profile.clinical_decision,
        "evidence_based_medicine": profile.evidence_based_medicine,
        "learning_engagement": profile.learning_engagement,
        "updated_at": profile.updated_at,
        "chart_data": [
            {"dimension": ABILITY_LABELS[key], "score": getattr(profile, key)}
            for key in CORE_ABILITIES
        ],
    }


def serialize_score(score: Score) -> dict:
    return {
        "id": score.id,
        "total_score": score.total_score,
        "medical_knowledge": score.medical_knowledge,
        "key_information": score.key_information,
        "differential_diagnosis": score.differential_diagnosis,
        "evidence_integration": score.evidence_integration,
        "clinical_decision": score.clinical_decision,
        "evidence_based_medicine": score.evidence_based_medicine,
        "feedback": score.feedback,
        "strengths": score.strengths,
        "weaknesses": score.weaknesses,
        "created_at": score.created_at,
        "chart_data": [
            {"dimension": ABILITY_LABELS[key], "score": getattr(score, key)}
            for key in CORE_ABILITIES
        ],
    }
