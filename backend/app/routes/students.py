from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Case, CompetencyProfile, LearningRecommendation, Student
from app.services.recommendation_service import (
    PATHWAY_STAGES,
    choose_recommendation,
    determine_pathway_stage,
    weakest_abilities,
)
from app.services.serializers import (
    ABILITY_LABELS,
    serialize_case_summary,
    serialize_profile,
    serialize_student,
)

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("")
def list_students(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_student(student) for student in db.query(Student).all()]


@router.get("/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)) -> dict:
    return serialize_student(_get_student(db, student_id))


@router.get("/{student_id}/competency")
def get_competency(student_id: int, db: Session = Depends(get_db)) -> dict:
    student = _get_student(db, student_id)
    return serialize_profile(student.competency_profile)


@router.get("/{student_id}/dashboard")
def get_dashboard(student_id: int, db: Session = Depends(get_db)) -> dict:
    student = _get_student(db, student_id)
    profile = serialize_profile(student.competency_profile)
    cases = [serialize_case_summary(case) for case in db.query(Case).all()]
    recommendations = _recommendations_for_student(db, student_id, profile, cases)
    completed = [session for session in student.sessions if session.status == "completed"]
    recent = recommendations[0] if recommendations else None
    return {
        "student": serialize_student(student),
        "competency": profile,
        "recommended_cases": [item["case"] for item in recommendations[:3]],
        "recent_advice": recent["recommendation_reason"] if recent else "请先完成推荐病例训练。",
        "progress": {
            "completed_cases": len(completed),
            "in_progress_cases": len(student.sessions) - len(completed),
            "average_score": round(
                sum(session.score.total_score for session in completed if session.score) / len(completed),
                1,
            )
            if completed
            else 0,
        },
    }


@router.get("/{student_id}/pathway")
def get_pathway(student_id: int, db: Session = Depends(get_db)) -> dict:
    student = _get_student(db, student_id)
    profile = serialize_profile(student.competency_profile)
    cases = [serialize_case_summary(case) for case in db.query(Case).all()]
    completed = [
        {
            "session_id": session.id,
            "case": serialize_case_summary(session.case),
            "score": session.score.total_score if session.score else None,
            "completed_at": session.completed_at,
        }
        for session in student.sessions
        if session.status == "completed"
    ]
    recent_scores = [
        {
            "total_score": session.score.total_score,
            "medical_knowledge": session.score.medical_knowledge,
            "key_information": session.score.key_information,
            "differential_diagnosis": session.score.differential_diagnosis,
            "evidence_integration": session.score.evidence_integration,
            "clinical_decision": session.score.clinical_decision,
            "evidence_based_medicine": session.score.evidence_based_medicine,
        }
        for session in student.sessions
        if session.score
    ]
    recommendation = choose_recommendation(profile, recent_scores, cases)
    weak_keys = weakest_abilities(profile, limit=3)
    return {
        "student": serialize_student(student),
        "competency": profile,
        "pathway_stages": PATHWAY_STAGES,
        "current_stage": determine_pathway_stage(profile),
        "completed_cases": completed,
        "recommended_case": recommendation["case"],
        "recommendation_reason": recommendation["reason"],
        "weak_abilities": [
            {"key": key, "label": ABILITY_LABELS[key], "score": profile[key]} for key in weak_keys
        ],
        "next_stage_goal": _next_stage_goal(determine_pathway_stage(profile)),
    }


def _get_student(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


def _recommendations_for_student(
    db: Session, student_id: int, profile: dict, cases: list[dict]
) -> list[dict]:
    rows = (
        db.query(LearningRecommendation)
        .filter(LearningRecommendation.student_id == student_id)
        .order_by(LearningRecommendation.created_at.desc())
        .limit(3)
        .all()
    )
    if rows:
        return [
            {
                "case": serialize_case_summary(row.recommended_case),
                "recommendation_reason": row.recommendation_reason,
                "pathway_stage": row.pathway_stage,
            }
            for row in rows
        ]
    recommendation = choose_recommendation(profile, [], cases)
    return [
        {
            "case": recommendation["case"],
            "recommendation_reason": recommendation["reason"],
            "pathway_stage": recommendation["pathway_stage"],
        }
    ]


def _next_stage_goal(stage: str) -> str:
    goals = {
        "stage_1_basic_recognition": "能稳定识别SLE、AOSD、血管炎和炎性肌病的核心表现。",
        "stage_2_differential_reasoning": "能围绕感染、肿瘤和自身免疫病建立鉴别排除路径。",
        "stage_3_clinical_decision": "能制定免疫抑制治疗、感染筛查和随访监测计划。",
        "stage_4_evidence_based_learning": "能使用指南和证据等级支撑治疗决策。",
    }
    return goals[stage]
