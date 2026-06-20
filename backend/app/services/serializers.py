import json
from typing import Any

from app.models import (
    Case,
    ClinicalSkill,
    CompetencyProfile,
    GuidelineDocument,
    GuidelineLearningSession,
    KnowledgeProgress,
    KnowledgeUnit,
    Score,
    SkillSession,
    SPCase,
    SPSession,
    Student,
)

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


def serialize_knowledge_unit(unit: KnowledgeUnit) -> dict:
    return {
        "id": unit.id,
        "title": unit.title,
        "category": unit.category,
        "level": unit.level,
        "learning_objectives": loads_json(unit.learning_objectives, []),
        "content": unit.content,
        "key_points": loads_json(unit.key_points, []),
        "quiz_items": loads_json(unit.quiz_items, []),
        "related_case_ids": loads_json(unit.related_case_ids, []),
        "created_at": unit.created_at,
    }


def serialize_knowledge_summary(unit: KnowledgeUnit) -> dict:
    return {
        "id": unit.id,
        "title": unit.title,
        "category": unit.category,
        "level": unit.level,
        "learning_objectives": loads_json(unit.learning_objectives, []),
        "key_points": loads_json(unit.key_points, []),
        "related_case_ids": loads_json(unit.related_case_ids, []),
    }


def serialize_knowledge_progress(progress: KnowledgeProgress) -> dict:
    return {
        "id": progress.id,
        "student_id": progress.student_id,
        "knowledge_unit_id": progress.knowledge_unit_id,
        "status": progress.status,
        "quiz_score": progress.quiz_score,
        "mastery_score": progress.mastery_score,
        "updated_at": progress.updated_at,
        "knowledge_unit": serialize_knowledge_summary(progress.knowledge_unit),
    }


def serialize_skill(skill: ClinicalSkill) -> dict:
    return {
        "id": skill.id,
        "title": skill.title,
        "category": skill.category,
        "difficulty": skill.difficulty,
        "indication": skill.indication,
        "contraindication": skill.contraindication,
        "steps": loads_json(skill.steps, []),
        "common_errors": loads_json(skill.common_errors, []),
        "scoring_rubric": loads_json(skill.scoring_rubric, {}),
        "created_at": skill.created_at,
    }


def serialize_skill_summary(skill: ClinicalSkill) -> dict:
    return {
        "id": skill.id,
        "title": skill.title,
        "category": skill.category,
        "difficulty": skill.difficulty,
        "indication": skill.indication,
        "common_errors": loads_json(skill.common_errors, []),
    }


def serialize_skill_session(session: SkillSession) -> dict:
    return {
        "id": session.id,
        "student_id": session.student_id,
        "skill_id": session.skill_id,
        "status": session.status,
        "submitted_steps": loads_json(session.submitted_steps or "[]", []),
        "score": session.score,
        "feedback": session.feedback,
        "created_at": session.created_at,
        "completed_at": session.completed_at,
        "skill": serialize_skill_summary(session.skill),
    }


def serialize_guideline(guideline: GuidelineDocument) -> dict:
    return {
        "id": guideline.id,
        "title": guideline.title,
        "organization": guideline.organization,
        "year": guideline.year,
        "disease_category": guideline.disease_category,
        "source_type": guideline.source_type,
        "summary": guideline.summary,
        "recommendations": loads_json(guideline.recommendations, []),
        "pico_examples": loads_json(guideline.pico_examples, []),
        "created_at": guideline.created_at,
    }


def serialize_guideline_summary(guideline: GuidelineDocument) -> dict:
    return {
        "id": guideline.id,
        "title": guideline.title,
        "organization": guideline.organization,
        "year": guideline.year,
        "disease_category": guideline.disease_category,
        "source_type": guideline.source_type,
        "summary": guideline.summary,
    }


def serialize_guideline_session(session: GuidelineLearningSession) -> dict:
    return {
        "id": session.id,
        "student_id": session.student_id,
        "guideline_id": session.guideline_id,
        "clinical_question": session.clinical_question,
        "pico": session.pico,
        "answer": session.answer,
        "score": session.score,
        "feedback": session.feedback,
        "created_at": session.created_at,
        "guideline": serialize_guideline_summary(session.guideline),
    }


def serialize_sp_case(sp_case: SPCase) -> dict:
    return {
        "id": sp_case.id,
        "title": sp_case.title,
        "disease_category": sp_case.disease_category,
        "difficulty": sp_case.difficulty,
        "patient_profile": loads_json(sp_case.patient_profile, {}),
        "opening_statement": sp_case.opening_statement,
        "hidden_history": loads_json(sp_case.hidden_history, {}),
        "emotional_style": sp_case.emotional_style,
        "expected_tasks": loads_json(sp_case.expected_tasks, []),
        "scoring_rubric": loads_json(sp_case.scoring_rubric, {}),
        "created_at": sp_case.created_at,
    }


def serialize_sp_case_summary(sp_case: SPCase) -> dict:
    return {
        "id": sp_case.id,
        "title": sp_case.title,
        "disease_category": sp_case.disease_category,
        "difficulty": sp_case.difficulty,
        "patient_profile": loads_json(sp_case.patient_profile, {}),
        "opening_statement": sp_case.opening_statement,
        "emotional_style": sp_case.emotional_style,
        "expected_tasks": loads_json(sp_case.expected_tasks, []),
    }


def serialize_sp_session(session: SPSession) -> dict:
    return {
        "id": session.id,
        "student_id": session.student_id,
        "sp_case_id": session.sp_case_id,
        "status": session.status,
        "transcript": loads_json(session.transcript, []),
        "diagnosis_summary": session.diagnosis_summary,
        "communication_score": session.communication_score,
        "history_taking_score": session.history_taking_score,
        "reasoning_score": session.reasoning_score,
        "humanistic_care_score": session.humanistic_care_score,
        "total_score": session.total_score,
        "feedback": session.feedback,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "sp_case": serialize_sp_case_summary(session.sp_case),
    }
