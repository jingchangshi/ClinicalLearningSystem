"""Read-only linkage from the research export to the training and teaching records.

Training and Assessment stay separate domains. The Assessment export must not call
training scoring, the tutor, competency updates or recommendation ranking; it needs
the *evidence* those domains already wrote. This module is the Research layer's
read-only join: it queries the training tables and the CBL teaching register and
returns coded indicators, and it never writes a row, never calls a service and
never recomputes a score.

Every indicator is derived from a stored row. Where a row does not exist the result
says ``undetermined`` with a reason — an absent training record is never reported as
zero training, and an unregistered CBL teaching log is never reported as "no
teaching". The payload carries no *generation* timestamp, so the same database
state always produces the same frozen bytes for the same dataset version.
"""
from __future__ import annotations

import json
from datetime import datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.assessment_models import StudyCohort
from app.core.reasoning_steps import REQUIRED_STEP_KEYS
from app.models import (
    AIInvocation,
    CaseSession,
    CompetencyProfile,
    LearningEvidenceEvent,
    LearningRecommendation,
    Score,
    StudentAnswer,
    TeachingIntervention,
    TutorTurn,
)
from app.research import STUDY_GROUP_CBL
from app.research import teaching_log as teaching_log_module
from app.research.study_access import access_for
from app.research.teaching_log import NOT_REGISTERED, REGISTERED, TeachingLog, TeachingLogStatus

LINKAGE_VERSION = "training-linkage-v1"
TUTOR_TASK = "tutor_question"
EVALUATION_TASK = "case_evaluation"
SOURCES = {
    "independent_assessment": ["assessment_sittings", "assessment_final_scores", "study_allocations"],
    "training": ["case_sessions", "student_answers", "scores", "tutor_turns", "ai_invocations",
                 "learning_recommendations", "learning_evidence_events", "competency_profiles",
                 "teaching_interventions"],
    "teaching_log": ["cbl_teaching_log"],
    "study_allocation": ["study_cohorts", "study_enrollments", "study_allocations"],
    "research_metadata": ["linkage_version", "window", "missing"],
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _bounds(access) -> tuple[datetime, datetime] | None:
    if access.window_start is None or access.window_end is None:
        return None
    return (datetime.combine(access.window_start, time.min),
            datetime.combine(access.window_end, time.max))


def _within(value: datetime | None, bounds) -> bool:
    return value is not None and (bounds is None or bounds[0] <= value <= bounds[1])


def _score_payload(score: Score) -> dict:
    return {
        "total_score": score.total_score,
        "medical_knowledge": score.medical_knowledge,
        "key_information": score.key_information,
        "differential_diagnosis": score.differential_diagnosis,
        "evidence_integration": score.evidence_integration,
        "clinical_decision": score.clinical_decision,
        "evidence_based_medicine": score.evidence_based_medicine,
        "evaluation_mode": score.evaluation_mode,
        "degraded": score.degraded,
        "created_at": _iso(score.created_at),
    }


def _process(db: Session, student_id: int, bounds) -> dict:
    """The ClinPath process indicators over one window (``bounds=None`` ⇒ every stored row)."""
    sessions = (db.query(CaseSession).filter(CaseSession.student_id == student_id)
                .order_by(CaseSession.id).all())
    touched = [s for s in sessions if _within(s.started_at, bounds) or _within(s.completed_at, bounds)]
    completed = [s for s in touched if s.status == "completed" and _within(s.completed_at, bounds)]
    session_ids = [s.id for s in touched]
    completed_ids = [s.id for s in completed]

    answered = {}
    if completed_ids:
        rows = db.query(StudentAnswer.session_id, StudentAnswer.step).filter(
            StudentAnswer.session_id.in_(completed_ids)).all()
        for sid, step in rows:
            answered.setdefault(sid, set()).add(step)
    five_stage = [s for s in completed if set(REQUIRED_STEP_KEYS) <= answered.get(s.id, set())]

    scores = {}
    if completed_ids:
        for row in db.query(Score).filter(Score.session_id.in_(completed_ids)):
            scores[row.session_id] = row

    tutor_shown = 0
    if session_ids:
        tutor_shown = (db.query(func.count(TutorTurn.id))
                       .filter(TutorTurn.session_id.in_(session_ids), TutorTurn.role == "tutor").scalar()) or 0

    invocations = []
    if session_ids:
        invocations = [row for row in db.query(AIInvocation).filter(AIInvocation.session_id.in_(session_ids))
                       if _within(row.created_at, bounds)]
    tutor_invocations = [row for row in invocations if row.task_type == TUTOR_TASK]
    fallback = [row for row in invocations if row.fallback_used]
    fallback_by_task: dict[str, int] = {}
    for row in fallback:
        fallback_by_task[row.task_type] = fallback_by_task.get(row.task_type, 0) + 1

    recommendations = [r for r in db.query(LearningRecommendation)
                       .filter(LearningRecommendation.student_id == student_id)
                       .order_by(LearningRecommendation.id).all()
                       if _within(r.created_at, bounds)]
    completed_by_case = {}
    for session in completed:
        completed_by_case.setdefault(session.case_id, []).append(session)
    tasks = []
    for rec in recommendations:
        done = [s for s in completed_by_case.get(rec.recommended_case_id, [])
                if s.completed_at and rec.created_at and s.completed_at >= rec.created_at]
        tasks.append({
            "case_id": rec.recommended_case_id, "pathway_stage": rec.pathway_stage,
            "recommended_at": _iso(rec.created_at), "completed": bool(done),
            "completed_at": _iso(min(s.completed_at for s in done)) if done else None,
        })
    done_count = sum(1 for t in tasks if t["completed"])

    evidence = [e for e in db.query(LearningEvidenceEvent)
                .filter(LearningEvidenceEvent.student_id == student_id)
                .order_by(LearningEvidenceEvent.id).all()
                if _within(e.created_at, bounds)]
    profile = db.query(CompetencyProfile).filter_by(student_id=student_id).first()
    captured_sessions = set(session_ids)

    interventions = []
    for row in db.query(TeachingIntervention).order_by(TeachingIntervention.id).all():
        if not _within(row.created_at, bounds):
            continue
        targets = _targets(row.target_students_json)
        if student_id in targets:
            interventions.append(row)
    intervention_types: dict[str, int] = {}
    for row in interventions:
        intervention_types[row.intervention_type] = intervention_types.get(row.intervention_type, 0) + 1

    started = [s.started_at for s in touched if s.started_at]
    finished = [s.completed_at for s in completed if s.completed_at]
    return {
        "completed_formative_cases": len({s.case_id for s in five_stage}),
        "completed_five_stage_runs": len(five_stage),
        "sessions_started": len([s for s in touched if _within(s.started_at, bounds)]),
        "tutor_questions_shown": int(tutor_shown),
        # Two distinct measures, never added together: audited model invocations
        # (one row per learning event) and the questions the student actually saw
        # (a rule-fallback question is shown but is not an AI invocation).
        "ai_tutor_invocations": len(tutor_invocations),
        "ai_tutor_provider_calls": sum(row.calls for row in tutor_invocations),
        "ai_tutor_successful": sum(1 for row in tutor_invocations if row.success),
        "rule_fallback_count": len(fallback),
        "rule_fallback_by_task": fallback_by_task,
        "training_scores": [
            {"case_id": s.case_id, "completed_at": _iso(s.completed_at), **_score_payload(scores[s.id])}
            for s in sorted(five_stage, key=lambda s: (s.completed_at or datetime.min, s.id)) if s.id in scores
        ],
        "profile_evidence": {
            "has_profile_row": profile is not None,
            "profile_updated_at": _iso(profile.updated_at) if profile else None,
            "evidence_events": len(evidence),
            "evidence_events_linked_to_sessions": sum(1 for e in evidence if e.session_id in captured_sessions),
            "score_evaluation_modes": _counts(scores[s.id].evaluation_mode for s in five_stage if s.id in scores),
            "degraded_scores": sum(1 for s in five_stage if s.id in scores and scores[s.id].degraded),
        },
        "d4_d5_recommendations": {
            "status": "observed" if tasks else "no_recommendation_in_window",
            "recommended_tasks": tasks,
            "completion": {"numerator": done_count, "denominator": len(tasks),
                           "rate": (done_count / len(tasks)) if tasks else None},
        },
        "teacher_interventions": {"count": len(interventions), "types": intervention_types},
        "actual_training_window": {
            "first_started_at": _iso(min(started)) if started else None,
            "last_completed_at": _iso(max(finished)) if finished else None,
            "basis": "case_sessions.started_at and case_sessions.completed_at",
        },
    }


def _counts(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out


def _targets(target_students_json: str | None) -> set[int]:
    try:
        raw = json.loads(target_students_json or "[]")
    except (TypeError, ValueError):
        return set()
    if not isinstance(raw, list):
        return set()
    return {int(v) for v in raw if isinstance(v, (int, str)) and str(v).isdigit()}


def _cbl_teaching(cohort_code: str | None, bounds, log: TeachingLog | None,
                  status: TeachingLogStatus, data_origin: str | None) -> dict:
    register = status.provenance()
    base = {"register": register,
            "interpretation": "absence_of_a_log_entry_is_not_evidence_of_absence_of_teaching"}
    if status.status == NOT_REGISTERED:
        return {**base, "status": "not_registered", "reason": "cbl_teaching_log_not_registered", "entries": []}
    if status.status != REGISTERED or log is None:
        return {**base, "status": "invalid", "reason": "cbl_teaching_log_invalid", "entries": []}
    # A synthetic or pilot register must never describe a real-study row (and vice versa).
    if data_origin and log.data_origin != data_origin:
        return {**base, "status": "origin_mismatch", "reason": "teaching_log_data_origin_mismatch",
                "entries": []}
    entries = log.for_cohort(cohort_code) if cohort_code else []
    if bounds is not None:
        entries = [e for e in entries if bounds[0].date() <= e.date <= bounds[1].date()]
    if not entries:
        return {**base, "status": "no_entries_for_cohort", "reason": "no_logged_teaching_for_cohort",
                "entries": [], "window_filter_applied": bounds is not None}
    topics: list[str] = []
    for entry in sorted(entries, key=lambda e: (e.date, e.case_topic)):
        if entry.case_topic not in topics:
            topics.append(entry.case_topic)
    return {
        **base, "status": "observed", "entries": [
            {"date": e.date.isoformat(), "case_topic": e.case_topic, "duration_minutes": e.duration_minutes,
             "supervising_teacher": e.supervising_teacher, "completed": e.completed,
             "overlaps_assessment_case_topic": e.overlaps_assessment_case_topic, "notes": e.notes}
            for e in sorted(entries, key=lambda e: (e.date, e.case_topic))],
        "total_minutes": sum(e.duration_minutes for e in entries),
        "completed_sessions": sum(1 for e in entries if e.completed),
        "case_topics": ";".join(topics),
        "overlap_days": sum(1 for e in entries if e.overlaps_assessment_case_topic),
        "window_filter_applied": bounds is not None,
    }


def batch_indices(db: Session, origin: str) -> dict[str, int]:
    """Chronological batch order (1..n) from the cohorts' recorded start dates.

    The order is the study's own timetable, so it is derived only when every cohort of
    this origin has a date. A partial timetable yields no index at all: guessing an
    order from cohort codes would invent the exposure-order sensitivity analysis.
    """
    cohorts = db.query(StudyCohort).filter_by(data_origin=origin).all()
    starts = {c.cohort_code: (c.actual_start or c.planned_start) for c in cohorts}
    if not starts or any(value is None for value in starts.values()):
        return {}
    ordered = sorted(starts, key=lambda code: (starts[code], code))
    return {code: index + 1 for index, code in enumerate(ordered)}


def training_linkage(
    db: Session,
    *,
    student_id: int,
    cohort_code: str | None = None,
    data_origin: str | None = None,
    log: TeachingLog | None = None,
    log_status: TeachingLogStatus | None = None,
) -> dict:
    """One coded linkage payload for a research row. Read-only; no student identity."""
    access = access_for(db, student_id)
    cohort = db.query(StudyCohort).filter_by(cohort_code=cohort_code).first() if cohort_code else None
    bounds = _bounds(access)
    warnings: list[str] = []
    if cohort is not None and access.cohort_code and cohort.cohort_code != access.cohort_code:
        warnings.append("sitting_cohort_differs_from_enrollment")
    if cohort is None and cohort_code:
        warnings.append("sitting_cohort_not_registered")
    if cohort is not None and data_origin and cohort.data_origin != data_origin:
        warnings.append("sitting_origin_differs_from_cohort")

    missing: list[dict] = []
    if bounds is None:
        reason = "cohort_teaching_window_not_recorded" if cohort is not None else "student_not_enrolled_in_a_study_cohort"
        process = {"status": "undetermined", "reason": reason, "observed_all_records": _process(db, student_id, None)}
        missing.append({"indicator": "clinpath_process", "reason": reason})
    else:
        process = {"status": "observed", **_process(db, student_id, bounds)}

    if log_status is None:
        log, log_status = teaching_log_module.load()
    cbl = _cbl_teaching(cohort_code, bounds, log, log_status, data_origin)
    if cbl["status"] != "observed":
        missing.append({"indicator": "cbl_teaching", "reason": cbl["reason"]})

    intervention_count = (process.get("teacher_interventions") or {}).get("count")
    if process["status"] != "observed":
        intervention_count = None
        missing.append({"indicator": "intervention_count", "reason": process["reason"]})

    return {
        "linkage_version": LINKAGE_VERSION,
        "study": access.as_dict(),
        "window": {
            "start": access.window_start.isoformat() if access.window_start else None,
            "end": access.window_end.isoformat() if access.window_end else None,
            "source": access.window_source, "state": access.window_state,
            "filter_applied": bounds is not None,
        },
        "clinpath_process": process,
        "cbl_teaching": cbl,
        "intervention_count": intervention_count,
        "warnings": warnings,
        "missing": missing,
        "sources": SOURCES,
    }


def export_fields(linkage: dict) -> tuple[str | None, int | None, str | None]:
    """(training_exposure, intervention_count, cbl_case_topics) for the frozen dataset row."""
    process = linkage["clinpath_process"]
    group = linkage.get("study", {}).get("study_group")
    if process["status"] != "observed":
        return None, None, None
    if group == STUDY_GROUP_CBL:
        teaching = linkage["cbl_teaching"]
        exposure = None
        if teaching["status"] == "observed":
            exposure = f"cbl_logged_sessions={len(teaching['entries'])};minutes={teaching['total_minutes']}"
        return exposure, linkage["intervention_count"], (teaching.get("case_topics") or None)
    exposure = (f"clinpath_cases={process['completed_formative_cases']};"
                f"five_stage_runs={process['completed_five_stage_runs']};"
                f"ai_tutor_invocations={process['ai_tutor_invocations']}")
    return exposure, linkage["intervention_count"], None
