from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Case, CaseSession, Student
from app.routes.cases import create_case_from_payload, update_case_from_payload
from app.services.serializers import (
    ABILITY_LABELS,
    CORE_ABILITIES,
    serialize_case,
    serialize_case_summary,
    serialize_profile,
)

router = APIRouter(prefix="/api/teacher", tags=["teacher"])


@router.get("/dashboard")
def get_teacher_dashboard(db: Session = Depends(get_db)) -> dict:
    students = db.query(Student).all()
    completed = db.query(CaseSession).filter(CaseSession.status == "completed").all()
    score_rows = [session.score for session in completed if session.score]
    averages = _class_averages(students)
    weak_dimensions = _weak_dimensions(averages)
    return {
        "student_count": len(students),
        "completed_session_count": len(completed),
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
        },
        "weak_dimensions": weak_dimensions,
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
        return {key: 0 for key in CORE_ABILITIES}
    return {
        key: round(
            sum(getattr(student.competency_profile, key) for student in students) / len(students),
            1,
        )
        for key in CORE_ABILITIES
    }


def _weak_dimensions(averages: dict) -> list[dict]:
    rows = []
    for key in CORE_ABILITIES:
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
    }
    return mapping[weakest]
