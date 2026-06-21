from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role, require_student_access
from app.database import get_db
from app.models import (
    Case,
    ClinicalSkill,
    CompetencyProfile,
    GuidelineDocument,
    KnowledgeUnit,
    LearningRecommendation,
    SPCase,
    Student,
    User,
)
from app.services.recommendation_service import (
    PATHWAY_STAGES,
    build_learning_pathway,
    choose_recommendation,
    determine_pathway_stage,
    weakest_abilities,
)
from app.services.learning_evidence_service import build_student_evidence_summary
from app.services.serializers import (
    ABILITY_LABELS,
    serialize_case_summary,
    serialize_guideline_summary,
    serialize_knowledge_summary,
    serialize_profile,
    serialize_skill_summary,
    serialize_sp_case_summary,
    serialize_student,
)

router = APIRouter(prefix="/api/students", tags=["students"])
student_router = APIRouter(prefix="/api/student", tags=["student"])


def _current_student_id(user: User) -> int:
    if user.role != "student" or user.student_id is None:
        raise HTTPException(status_code=403, detail="Student account is required")
    return user.student_id


@student_router.get("/me")
def get_current_student(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return serialize_student(_get_student(db, _current_student_id(user)))


@student_router.get("/competency")
def get_current_competency(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    student = _get_student(db, _current_student_id(user))
    return serialize_profile(student.competency_profile)


@student_router.get("/dashboard")
def get_current_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return _dashboard_payload(db, _current_student_id(user))


@student_router.get("/pathway")
def get_current_pathway(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return _pathway_payload(db, _current_student_id(user))


@student_router.get("/knowledge-progress")
def get_current_knowledge_progress(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    from app.routes.knowledge import knowledge_progress_payload

    return knowledge_progress_payload(db, _current_student_id(user))


@router.get("")
def list_students(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    if user.role == "student":
        student = db.get(Student, user.student_id)
        return [serialize_student(student)] if student else []
    require_role(["teacher"])(user)
    return [serialize_student(student) for student in db.query(Student).all()]


@router.get("/{student_id}")
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    require_student_access(student_id, user)
    return serialize_student(_get_student(db, student_id))


@router.get("/{student_id}/competency")
def get_competency(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    require_student_access(student_id, user)
    student = _get_student(db, student_id)
    return serialize_profile(student.competency_profile)


@router.get("/{student_id}/dashboard")
def get_dashboard(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    require_student_access(student_id, user)
    return _dashboard_payload(db, student_id)


def _dashboard_payload(db: Session, student_id: int) -> dict:
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
        "recommendation_details": recommendations[:3],
        "recent_advice": recent["recommendation_reason"] if recent else "请先完成推荐病例训练。",
        "learning_evidence": build_student_evidence_summary(db, student_id)["evidence_summary"],
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
def get_pathway(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    require_student_access(student_id, user)
    return _pathway_payload(db, student_id)


def _pathway_payload(db: Session, student_id: int) -> dict:
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
    weak_keys = weakest_abilities(profile, limit=4, use_expanded=True)
    knowledge_suggestions = _knowledge_suggestions(db, weak_keys)
    learning_pathway = build_learning_pathway(
        profile,
        {
            "cases": cases,
            "knowledge_units": [serialize_knowledge_summary(unit) for unit in db.query(KnowledgeUnit).all()],
            "clinical_skills": [serialize_skill_summary(skill) for skill in db.query(ClinicalSkill).all()],
            "guidelines": [serialize_guideline_summary(guideline) for guideline in db.query(GuidelineDocument).all()],
            "sp_cases": [serialize_sp_case_summary(sp_case) for sp_case in db.query(SPCase).all()],
        },
    )
    return {
        "student": serialize_student(student),
        "competency": profile,
        "pathway_stages": PATHWAY_STAGES,
        "current_stage": learning_pathway["current_stage"],
        "completed_cases": completed,
        "recommended_case": recommendation["case"],
        "recommendation_reason": recommendation["reason"],
        "weak_abilities": [
            {"key": key, "label": ABILITY_LABELS[key], "score": profile[key]}
            for key in learning_pathway["weak_abilities"]
        ],
        "recommended_tasks": learning_pathway["recommended_tasks"],
        "learning_evidence": build_student_evidence_summary(db, student_id)["evidence_summary"],
        "knowledge_suggestions": knowledge_suggestions,
        "next_stage_goal": _next_stage_goal(learning_pathway["current_stage"]),
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


def _knowledge_suggestions(db: Session, weak_keys: list[str]) -> list[dict]:
    units = db.query(KnowledgeUnit).all()
    if not units:
        return []
    preferred_titles = []
    if "medical_knowledge" in weak_keys:
        preferred_titles.append("SLE核心诊断线索")
    if "key_information" in weak_keys or "differential_diagnosis" in weak_keys:
        preferred_titles.append("发热皮疹的鉴别诊断")
    if "clinical_decision" in weak_keys:
        preferred_titles.append("免疫抑制治疗安全监测")
    suggestions = []
    for title in preferred_titles:
        unit = next((item for item in units if item.title == title), None)
        if unit:
            suggestions.append(
                {
                    "unit": serialize_knowledge_summary(unit),
                    "reason": f"当前能力画像提示{', '.join(ABILITY_LABELS[key] for key in weak_keys)}需要加强，建议先完成该知识单元。",
                }
            )
    return suggestions[:2] or [
        {
            "unit": serialize_knowledge_summary(units[0]),
            "reason": "建议通过基础知识学习巩固病例训练前置概念。",
        }
    ]
