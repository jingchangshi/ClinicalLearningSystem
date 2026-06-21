from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Case,
    CaseSession,
    GuidelineLearningSession,
    LearningEvidenceEvent,
    SPSession,
    Student,
    TeacherScoreReview,
    TeachingIntervention,
)
from app.routes.cases import create_case_from_payload, update_case_from_payload
from app.services.learning_evidence_service import (
    build_class_heatmap,
    build_class_training_summary,
    build_growth_trend,
    build_student_evidence_events,
    build_student_evidence_summary,
)
from app.services.recommendation_service import build_learning_pathway
from app.services.serializers import (
    ABILITY_LABELS,
    ALL_COMPETENCIES,
    CORE_ABILITIES,
    dumps_json,
    loads_json,
    serialize_case,
    serialize_case_summary,
    serialize_guideline_session,
    serialize_knowledge_summary,
    serialize_profile,
    serialize_skill_summary,
    serialize_sp_case_summary,
    serialize_sp_session,
    serialize_student,
)

router = APIRouter(prefix="/api/teacher", tags=["teacher"])


class InterventionCreate(BaseModel):
    title: str
    target_ability: str
    target_students: list[int]
    intervention_type: str
    description: str


class ReviewCreate(BaseModel):
    evidence_event_id: int
    ai_score: float
    teacher_score: float
    comment: str


@router.get("/dashboard")
def get_teacher_dashboard(db: Session = Depends(get_db)) -> dict:
    students = db.query(Student).all()
    completed = db.query(CaseSession).filter(CaseSession.status == "completed").all()
    score_rows = [session.score for session in completed if session.score]
    averages = _class_averages(students)
    weak_dimensions = _weak_dimensions(averages)
    training_summary = build_class_training_summary(db)
    teaching_interventions = _teaching_interventions(weak_dimensions)
    return {
        "student_count": len(students),
        "completed_session_count": len(completed),
        **training_summary,
        "class_average_total_score": round(
            sum(score.total_score for score in score_rows) / len(score_rows), 1
        )
        if score_rows
        else 0,
        "average_improvement": 6.8,
        "class_competency": {
            **averages,
            "chart_data": [
                {"dimension": ABILITY_LABELS[key], "score": averages[key]} for key in CORE_ABILITIES
            ],
            "expanded_chart_data": [
                {"dimension": ABILITY_LABELS[key], "score": averages[key]} for key in ALL_COMPETENCIES
            ],
        },
        "weak_dimensions": weak_dimensions,
        "current_common_weakness": weak_dimensions[0]["label"] if weak_dimensions else "暂无明显短板",
        "class_heatmap": build_class_heatmap(db),
        "teaching_interventions": teaching_interventions,
        "teaching_focus": _teaching_focus(weak_dimensions),
        "students": [_student_row(student) for student in students],
        "recent_sessions": [
            {
                "session_id": session.id,
                "student_name": session.student.name,
                "case_title": session.case.title,
                "score": session.score.total_score if session.score else None,
                "completed_at": session.completed_at,
            }
            for session in completed[-8:]
        ],
    }


@router.get("/students/{student_id}/learning-profile")
def get_student_learning_profile(student_id: int, db: Session = Depends(get_db)) -> dict:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    profile = serialize_profile(student.competency_profile)
    recent_activity = _recent_activity(db)
    learning_pathway = build_learning_pathway(profile, recent_activity)
    completed_sessions = [
        {
            "session_id": session.id,
            "case": serialize_case_summary(session.case),
            "score": session.score.total_score if session.score else None,
            "completed_at": session.completed_at,
        }
        for session in student.sessions
        if session.status == "completed"
    ]
    latest_sp = (
        db.query(SPSession)
        .filter(SPSession.student_id == student_id, SPSession.status == "completed")
        .order_by(SPSession.completed_at.desc())
        .first()
    )
    latest_guideline = (
        db.query(GuidelineLearningSession)
        .filter(GuidelineLearningSession.student_id == student_id)
        .order_by(GuidelineLearningSession.created_at.desc())
        .first()
    )
    return {
        "student": serialize_student(student),
        "competency": profile,
        "learning_evidence": build_student_evidence_summary(db, student_id)["evidence_summary"],
        "evidence_events": build_student_evidence_events(db, student_id),
        "recommended_tasks": learning_pathway["recommended_tasks"],
        "completed_sessions": completed_sessions,
        "latest_sp": serialize_sp_session(latest_sp) if latest_sp else None,
        "latest_guideline": serialize_guideline_session(latest_guideline) if latest_guideline else None,
        "growth_trend": build_growth_trend(db, student_id),
    }


@router.get("/export/research-data")
def export_research_data(db: Session = Depends(get_db)) -> dict:
    rows = []
    events = db.query(LearningEvidenceEvent).order_by(LearningEvidenceEvent.created_at.asc()).all()
    for event in events:
        student = db.get(Student, event.student_id)
        updates = loads_json(event.competency_updates_json, {})
        rows.append(
            {
                "student_code": f"S{event.student_id:04d}",
                "class_name": student.class_name if student else "",
                "module_type": event.module_type,
                "score": event.score,
                "competency_before": {key: value.get("before") for key, value in updates.items()},
                "competency_after": {key: value.get("after") for key, value in updates.items()},
                "created_at": event.created_at,
            }
        )
    return {"format": "json", "anonymous": True, "rows": rows}


@router.post("/interventions")
def create_intervention(payload: InterventionCreate, db: Session = Depends(get_db)) -> dict:
    intervention = TeachingIntervention(
        title=payload.title,
        target_ability=payload.target_ability,
        target_students_json=dumps_json(payload.target_students),
        intervention_type=payload.intervention_type,
        description=payload.description,
    )
    db.add(intervention)
    db.commit()
    db.refresh(intervention)
    return _serialize_intervention(intervention)


@router.get("/interventions")
def list_interventions(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(TeachingIntervention).order_by(TeachingIntervention.created_at.desc()).all()
    return [_serialize_intervention(row) for row in rows]


@router.post("/reviews")
def create_score_review(payload: ReviewCreate, db: Session = Depends(get_db)) -> dict:
    if not db.get(LearningEvidenceEvent, payload.evidence_event_id):
        raise HTTPException(status_code=404, detail="Evidence event not found")
    review = TeacherScoreReview(
        evidence_event_id=payload.evidence_event_id,
        ai_score=payload.ai_score,
        teacher_score=payload.teacher_score,
        comment=payload.comment,
        agreement_delta=round(payload.teacher_score - payload.ai_score, 1),
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return _serialize_review(review)


@router.get("/reviews")
def list_score_reviews(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(TeacherScoreReview).order_by(TeacherScoreReview.created_at.desc()).all()
    return [_serialize_review(row) for row in rows]


@router.get("/cases")
def teacher_list_cases(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_case(case) for case in db.query(Case).all()]


@router.post("/cases")
def teacher_create_case(payload: dict, db: Session = Depends(get_db)) -> dict:
    return serialize_case(create_case_from_payload(payload, db))


@router.put("/cases/{case_id}")
def teacher_update_case(case_id: int, payload: dict, db: Session = Depends(get_db)) -> dict:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return serialize_case(update_case_from_payload(case, payload, db))


@router.delete("/cases/{case_id}")
def teacher_delete_case(case_id: int, db: Session = Depends(get_db)) -> dict:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    db.delete(case)
    db.commit()
    return {"ok": True}


def _class_averages(students: list[Student]) -> dict:
    if not students:
        return {key: 0 for key in ALL_COMPETENCIES}
    return {
        key: round(
            sum(getattr(student.competency_profile, key) for student in students if student.competency_profile) / len(students),
            1,
        )
        for key in ALL_COMPETENCIES
    }


def _weak_dimensions(averages: dict) -> list[dict]:
    rows = []
    for key in ALL_COMPETENCIES:
        score = averages[key]
        if score < 60:
            level = "明显短板"
        elif score < 70:
            level = "需要加强"
        else:
            continue
        rows.append({"key": key, "label": ABILITY_LABELS[key], "score": score, "level": level})
    return sorted(rows, key=lambda row: row["score"])


def _teaching_focus(weak_dimensions: list[dict]) -> list[str]:
    if not weak_dimensions:
        return ["班级整体表现较稳定，可增加高阶循证医学和复杂治疗决策训练。"]
    suggestions = []
    for row in weak_dimensions[:2]:
        if row["key"] == "differential_diagnosis":
            suggestions.append("本班学生鉴别诊断能力相对薄弱，建议增加SLE、感染、AOSD、HLH的对比式病例讨论。")
        elif row["key"] == "evidence_based_medicine":
            suggestions.append("本班学生循证医学意识不足，建议增加指南阅读和治疗证据分级训练。")
        elif row["key"] == "clinical_decision":
            suggestions.append("建议安排免疫抑制治疗、感染筛查和不良反应监测专题训练。")
        else:
            suggestions.append(f"建议围绕{row['label']}开展结构化病例复盘。")
    return suggestions


def _teaching_interventions(weak_dimensions: list[dict]) -> list[str]:
    if not weak_dimensions:
        return ["班级整体表现较稳定，可增加高阶循证医学和复杂治疗决策训练。"]
    mapping = {
        "evidence_based_medicine": "下周增加“指南推荐等级与PICO构建”小课。",
        "differential_diagnosis": "安排“SLE活动与感染鉴别”病例讨论。",
        "clinical_decision": "增加“免疫抑制治疗安全监测”专题。",
        "medical_knowledge": "向基础薄弱学生推送基础知识单元。",
        "key_information": "加强SP问诊训练，提升关键信息采集完整性。",
    }
    suggestions = [mapping[row["key"]] for row in weak_dimensions if row["key"] in mapping]
    return suggestions or [f"围绕{weak_dimensions[0]['label']}设计结构化病例复盘。"]


def _student_row(student: Student) -> dict:
    profile = serialize_profile(student.competency_profile)
    weakest = min(CORE_ABILITIES, key=lambda key: profile[key])
    completed = [session for session in student.sessions if session.status == "completed" and session.score]
    return {
        "id": student.id,
        "name": student.name,
        "current_stage": student.current_stage,
        "recent_score": completed[-1].score.total_score if completed else None,
        "weakest_ability": ABILITY_LABELS[weakest],
        "recommended_training": _training_direction(weakest),
    }


def _training_direction(weakest: str) -> str:
    mapping = {
        "medical_knowledge": "SLE基础识别训练",
        "key_information": "病例关键信息提取训练",
        "differential_diagnosis": "发热皮疹鉴别诊断训练",
        "evidence_integration": "支持证据与反证整合训练",
        "clinical_decision": "治疗决策与监测计划训练",
        "evidence_based_medicine": "指南证据阅读训练",
        "skill_operation": "临床技能步骤训练",
        "communication": "SP沟通表达训练",
        "humanistic_care": "SP人文关怀训练",
    }
    return mapping[weakest]


def _recent_activity(db: Session) -> dict:
    from app.models import ClinicalSkill, GuidelineDocument, KnowledgeUnit, SPCase

    return {
        "cases": [serialize_case_summary(case) for case in db.query(Case).all()],
        "knowledge_units": [serialize_knowledge_summary(unit) for unit in db.query(KnowledgeUnit).all()],
        "clinical_skills": [serialize_skill_summary(skill) for skill in db.query(ClinicalSkill).all()],
        "guidelines": [
            {
                "id": guideline.id,
                "title": guideline.title,
                "difficulty": "指南",
            }
            for guideline in db.query(GuidelineDocument).all()
        ],
        "sp_cases": [serialize_sp_case_summary(sp_case) for sp_case in db.query(SPCase).all()],
    }


def _serialize_intervention(intervention: TeachingIntervention) -> dict:
    return {
        "id": intervention.id,
        "title": intervention.title,
        "target_ability": intervention.target_ability,
        "target_students": loads_json(intervention.target_students_json, []),
        "intervention_type": intervention.intervention_type,
        "description": intervention.description,
        "created_at": intervention.created_at,
    }


def _serialize_review(review: TeacherScoreReview) -> dict:
    return {
        "id": review.id,
        "evidence_event_id": review.evidence_event_id,
        "ai_score": review.ai_score,
        "teacher_score": review.teacher_score,
        "comment": review.comment,
        "agreement_delta": review.agreement_delta,
        "created_at": review.created_at,
    }
