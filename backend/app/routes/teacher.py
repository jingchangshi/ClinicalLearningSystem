import csv
import io
import logging
import os

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.core.ai_audit import ai_invocation
from app.core.deidentify import scan_case_payload
from app.database import get_db
from app.models import (
    Case,
    CaseSession,
    GuidelineLearningSession,
    LearningEvidenceEvent,
    SPSession,
    Student,
    Score,
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
    student_case_sessions,
)
from app.services.llm_service import llm_service
from app.services import ai_enrichment
from app.services.pathway_context import load_pathway_catalog
from app.services.recommendation_service import build_learning_pathway, determine_pathway_stage, choose_recommendation
from app.services.competency_projector import COMPETENCY_PROJECTOR_VERSION, confirmed_total, reproject_competencies
from app.services.display_labels import module_label, stage_label
from app.services.serializers import (
    ABILITY_LABELS,
    ALL_COMPETENCIES,
    CORE_ABILITIES,
    dumps_json,
    loads_json,
    serialize_case,
    serialize_case_summary,
    serialize_guideline_session,
    serialize_profile,
    serialize_sp_session,
    serialize_student,
)

logger = logging.getLogger("clinpath.teacher")

router = APIRouter(
    prefix="/api/teacher",
    tags=["teacher"],
    dependencies=[Depends(require_role(["teacher"]))],
)


class InterventionCreate(BaseModel):
    title: str
    target_ability: str
    target_students: list[int]
    intervention_type: str
    description: str


class ReviewCreate(BaseModel):
    evidence_event_id: int
    confirmed_dimensions: dict[str, float] = Field(min_length=6, max_length=6)
    comment: str = Field(min_length=1)

    def model_post_init(self, __context: object) -> None:
        if set(self.confirmed_dimensions) != set(CORE_ABILITIES):
            raise ValueError("confirmed_dimensions must contain exactly the six core competencies")
        if any(score < 0 or score > 100 for score in self.confirmed_dimensions.values()):
            raise ValueError("dimension scores must be between 0 and 100")


@router.get("/dashboard")
def get_teacher_dashboard(db: Session = Depends(get_db)) -> dict:
    students = db.query(Student).all()
    completed = db.query(CaseSession).filter(CaseSession.status == "completed").all()
    score_rows = [session.score for session in completed if session.score]
    averages = _class_averages(students)
    weak_dimensions = _weak_dimensions(averages)
    training_summary = build_class_training_summary(db)
    teaching_interventions = _teaching_interventions(weak_dimensions)
    # Reading the dashboard must not wait for a model. The deterministic summary
    # is always available; a *current* cached insight replaces it when one exists
    # (generated after a learning event, or by the explicit refresh action).
    insight = ai_enrichment.current_teacher_insight(db)
    return {
        "student_count": len(students),
        "completed_session_count": len(completed),
        **training_summary,
        "class_average_total_score": round(
            sum(score.total_score for score in score_rows) / len(score_rows), 1
        )
        if score_rows
        else 0,
        "average_improvement": _average_improvement(completed),
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
        "teaching_insight_summary": (
            insight["payload"]["insight"]
            if insight
            else _teaching_insight_fallback(weak_dimensions, training_summary)
        ),
        "teaching_insight_source": "ai" if insight else "rule",
        "teaching_insight_generated_at": insight["generated_at"] if insight else None,
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


@router.post("/dashboard/refresh-insight")
def refresh_teacher_insight(db: Session = Depends(get_db)) -> dict:
    """Explicit, deliberate AI generation. GET stays read-only.

    A teacher reloading the dashboard must not spend provider quota; asking for a
    fresh insight is a separate decision, so it is a POST that persists its own
    result.
    """

    text = ai_enrichment.regenerate_teacher_insight(db, build_teacher_insight_text)
    if text is None:
        return {
            "teaching_insight_summary": None,
            "teaching_insight_source": "rule",
            "degraded": True,
            "message": "AI 洞察暂不可用，已保留规则化教学建议。",
        }
    return {"teaching_insight_summary": text, "teaching_insight_source": "ai", "degraded": False}


def build_teacher_insight_text(db: Session) -> str | None:
    """Generate the class insight now. ``None`` means the model did not answer.

    A rule answer must never be stored as an AI insight, so the audit event's
    ``fallback_used`` flag decides whether there is anything to persist.
    """

    students = db.query(Student).all()
    weak_dimensions = _weak_dimensions(_class_averages(students))
    training_summary = build_class_training_summary(db)
    with ai_invocation("teacher_insight", evidence_ref="teacher_dashboard") as invocation:
        text = llm_service.generate_teacher_insight(
            weak_dimensions,
            training_summary,
            _teaching_insight_fallback(weak_dimensions, training_summary),
        )
        if invocation.fallback_used:
            return None
    return text


@router.get("/students/{student_id}/learning-profile")
def get_student_learning_profile(student_id: int, db: Session = Depends(get_db)) -> dict:
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    profile = serialize_profile(student.competency_profile)
    learning_pathway = build_learning_pathway(profile, load_pathway_catalog(db))
    enrichment = ai_enrichment.current_pathway_enrichment(db, student_id)
    explanation_source = ai_enrichment.apply_task_explanations(
        learning_pathway["recommended_tasks"], enrichment
    )
    completed_sessions = [
        {
            "session_id": session.id,
            "case": serialize_case_summary(session.case),
            "score": session.score.total_score if session.score else None,
            "completed_at": session.completed_at,
        }
        for session in student_case_sessions(db, student_id)
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
        "explanation_source": explanation_source,
        "explanation_generated_at": enrichment["generated_at"] if enrichment else None,
        "completed_sessions": completed_sessions,
        "latest_sp": serialize_sp_session(latest_sp) if latest_sp else None,
        "latest_guideline": serialize_guideline_session(latest_guideline) if latest_guideline else None,
        "growth_trend": build_growth_trend(db, student_id),
    }


# The demo page shows a readable slice; the download and the JSON contract keep
# every record. `preview_limit` is what the page renders before 查看全部.
RESEARCH_PREVIEW_LIMIT = 20


def _research_rows(db: Session) -> list[dict]:
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
                "module_label": module_label(event.module_type),
                "score": event.score,
                "competency_before": {key: value.get("before") for key, value in updates.items()},
                "competency_after": {key: value.get("after") for key, value in updates.items()},
                "created_at": event.created_at,
            }
        )
    return rows


def _research_summary(rows: list[dict]) -> dict:
    dates = sorted(str(row["created_at"])[:10] for row in rows)
    labels: list[str] = []
    for row in rows:
        if row["module_label"] not in labels:
            labels.append(row["module_label"])
    return {
        "student_count": len({row["student_code"] for row in rows}),
        "record_count": len(rows),
        "module_labels": labels,
        "date_range": {"start": dates[0] if dates else None, "end": dates[-1] if dates else None},
        "preview_limit": RESEARCH_PREVIEW_LIMIT,
        "preview_count": min(RESEARCH_PREVIEW_LIMIT, len(rows)),
    }


@router.get("/export/research-data")
def export_research_data(db: Session = Depends(get_db)) -> dict:
    rows = _research_rows(db)
    # Newest first: a single prolific student must not bury every other one.
    preview = sorted(rows, key=lambda row: row["created_at"], reverse=True)[:RESEARCH_PREVIEW_LIMIT]
    return {
        "format": "json",
        "anonymous": True,
        "rows": rows,
        "preview_rows": preview,
        "summary": _research_summary(rows),
    }


@router.get("/export/research-data.csv")
def export_research_data_csv(db: Session = Depends(get_db)) -> Response:
    """The complete anonymised dataset as a spreadsheet a teacher can open.

    The BOM is there so Excel on a Chinese Windows install reads the headers as
    UTF-8 instead of mojibake.
    """

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["匿名学生编号", "班级", "学习模块", "训练得分", "记录时间"])
    for row in _research_rows(db):
        writer.writerow(
            [
                row["student_code"],
                row["class_name"],
                row["module_label"],
                "" if row["score"] is None else row["score"],
                str(row["created_at"]),
            ]
        )
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="clinpath-research-data.csv"'},
    )


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
def create_score_review(
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    reviewer=Depends(get_current_user),
) -> dict:
    event = db.get(LearningEvidenceEvent, payload.evidence_event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Evidence event not found")
    if event.event_type != "case_session_scored":
        raise HTTPException(status_code=400, detail="Only case score evidence can be reviewed")
    score = db.query(Score).filter(Score.session_id == event.source_id).first()
    if not score:
        raise HTTPException(status_code=404, detail="Original score not found")
    teacher_score = confirmed_total(payload.confirmed_dimensions)
    authoritative_ai_score = score.ai_score if score.ai_score is not None else score.total_score
    try:
        score.teacher_confirmed_score = teacher_score
        score.teacher_override_reason = payload.comment
        review = TeacherScoreReview(
            evidence_event_id=event.id,
            reviewer_user_id=reviewer.id,
            ai_score=authoritative_ai_score,
            teacher_score=teacher_score,
            comment=payload.comment,
            agreement_delta=round(teacher_score - authoritative_ai_score, 1),
            confirmed_dimensions_json=dumps_json(payload.confirmed_dimensions),
            projector_version=COMPETENCY_PROJECTOR_VERSION,
        )
        db.add(review)
        db.flush()
        db.add(LearningEvidenceEvent(
            student_id=event.student_id, module_type="case", module_id=event.module_id,
            session_id=event.session_id, event_type="teacher_score_confirmed",
            source_table="teacher_score_reviews", source_id=review.id, score=teacher_score,
            competency_updates_json="{}", evidence_payload_json=dumps_json({"original_evidence_event_id": event.id, "dimensions": payload.confirmed_dimensions}),
        ))
        reproject_competencies(db, event.student_id)
        student = db.get(Student, event.student_id)
        profile = serialize_profile(student.competency_profile)
        student.current_stage = determine_pathway_stage(profile)
        cases = [serialize_case_summary(case) for case in db.query(Case).all()]
        recommendation = choose_recommendation(profile, [], cases)
        # A fresh recommendation makes the corrected profile immediately authoritative.
        from app.models import LearningRecommendation
        db.add(LearningRecommendation(student_id=student.id, recommended_case_id=recommendation["case"]["id"], recommendation_reason=recommendation["reason"], pathway_stage=recommendation["pathway_stage"]))
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(review)
    # A teacher-confirmed score is a new piece of evidence: the cached class
    # insight and this learner's explanation are both out of date now.
    ai_enrichment.schedule_student(event.student_id)
    return _serialize_review(review)


@router.get("/reviews")
def list_score_reviews(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(TeacherScoreReview).order_by(TeacherScoreReview.created_at.desc()).all()
    return [_serialize_review(row) for row in rows]


@router.get("/reviewable-evidence")
def list_reviewable_evidence(db: Session = Depends(get_db)) -> list[dict]:
    events = (
        db.query(LearningEvidenceEvent)
        .filter(LearningEvidenceEvent.event_type == "case_session_scored")
        .order_by(LearningEvidenceEvent.created_at.desc())
        .all()
    )
    rows = []
    for event in events:
        score = db.query(Score).filter(Score.session_id == event.source_id).first()
        student = db.get(Student, event.student_id)
        if not score or not student:
            continue
        rows.append({
            "evidence_event_id": event.id,
            "student_id": student.id,
            "student_name": student.name,
            "case_session_id": event.source_id,
            "ai_score": score.ai_score if score.ai_score is not None else score.total_score,
            "teacher_confirmed_score": score.teacher_confirmed_score,
            "dimensions": {key: getattr(score, key) for key in CORE_ABILITIES},
            "created_at": event.created_at,
        })
    return rows


@router.get("/cases")
def teacher_list_cases(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_case(case) for case in db.query(Case).all()]


@router.post("/cases")
def teacher_create_case(payload: dict, db: Session = Depends(get_db)) -> dict:
    report = _deidentification_gate(payload)
    return {**serialize_case(create_case_from_payload(payload, db)), "deidentification": report}


@router.put("/cases/{case_id}")
def teacher_update_case(case_id: int, payload: dict, db: Session = Depends(get_db)) -> dict:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    report = _deidentification_gate(payload)
    return {**serialize_case(update_case_from_payload(case, payload, db)), "deidentification": report}


def _deidentification_gate(payload: dict) -> dict:
    """Warn on identifier-shaped input; block it only when the deployment asks.

    The model boundary is already enforced (``llm_service`` redacts every prompt),
    so this is about what enters the case bank itself.
    """

    report = scan_case_payload(payload)
    if not report["clean"]:
        logger.warning(
            "case authoring: possible identifiers in fields %s",
            [finding["field"] for finding in report["findings"]],
        )
        if os.getenv("REQUIRE_CASE_DEIDENTIFICATION", "false").strip().lower() in {"1", "true", "yes", "on"}:
            raise HTTPException(
                status_code=400,
                detail={
                    "detail": "Case text appears to contain patient identifiers",
                    "fields": report["findings"],
                },
            )
    return report


@router.delete("/cases/{case_id}")
def teacher_delete_case(case_id: int, db: Session = Depends(get_db)) -> dict:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    db.delete(case)
    db.commit()
    return {"ok": True}


def _class_averages(students: list[Student]) -> dict:
    profiles = [student.competency_profile for student in students if student.competency_profile]
    if not profiles:
        return {key: 0 for key in ALL_COMPETENCIES}
    return {
        key: round(
            sum(getattr(profile, key) for profile in profiles) / len(profiles),
            1,
        )
        for key in ALL_COMPETENCIES
    }


def _average_improvement(completed_sessions: list[CaseSession]) -> float:
    by_student: dict[int, list[CaseSession]] = {}
    for session in sorted(completed_sessions, key=lambda item: item.completed_at or item.started_at):
        if session.score:
            by_student.setdefault(session.student_id, []).append(session)
    deltas = []
    for sessions in by_student.values():
        if len(sessions) < 2:
            continue
        baseline = sessions[0].score.total_score
        latest = sessions[-1].score.total_score
        deltas.append(latest - baseline)
    return round(sum(deltas) / len(deltas), 1) if deltas else 0


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


def _teaching_insight_fallback(weak_dimensions: list[dict], training_summary: dict) -> str:
    total = training_summary.get("training_total_count", 0)
    if not weak_dimensions:
        return f"当前累计训练 {total} 次，班级暂无明显共性短板，可提高复杂病例和循证训练比例。"
    weak_text = "、".join(row["label"] for row in weak_dimensions[:2])
    return f"当前累计训练 {total} 次，班级主要短板集中在{weak_text}。建议围绕这些维度安排小课、病例复盘和再训练评价。"


def _student_row(student: Student) -> dict:
    profile = serialize_profile(student.competency_profile)
    weakest = min(CORE_ABILITIES, key=lambda key: profile[key])
    completed = [session for session in student.sessions if session.status == "completed" and session.score]
    return {
        "id": student.id,
        "name": student.name,
        "current_stage": student.current_stage,
        "current_stage_label": stage_label(student.current_stage),
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
        "confirmed_dimensions": loads_json(review.confirmed_dimensions_json, {}),
        "projector_version": review.projector_version,
        "created_at": review.created_at,
    }
