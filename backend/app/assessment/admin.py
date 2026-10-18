"""Study-administrator operations: scheduling, window control, scoring lock, audit.

Admins schedule and lock; they can never rate, adjudicate, review a form, sit an
exam, or alter a submitted review (the only path is the audited ``reopen``).
"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.assessment.access import fail, require_admin
from app.assessment.audit import audit, event
from app.assessment.blinding import blinding_risk, ensure_research_code, new_blind_code
from app.assessment.design import Design, design_for
from app.assessment.forms import form_rubric, get_form, load, require_published
from app.assessment.rating import live_reviews, sitting_disagreement
from app.assessment.student import effective_end, expire_if_needed
from app.assessment.timeutil import iso_z, to_utc_naive, utcnow
from app.assessment_models import (
    AssessmentAdjudication, AssessmentAuditLog, AssessmentForm, AssessmentEvent, AssessmentFinalScore, AssessmentReview,
    AssessmentSitting, ResearchCode, StudyCohort, StudyEnrollment,
)
from app.database import get_db
from app.models import Student, User
from app.research import DATA_ORIGINS, FORM_ORDERS

router = APIRouter(prefix="/admin")
GROUPS = ("CLINPATH", "CBL")


def _aware(value: datetime) -> datetime:
    try:
        return to_utc_naive(value)
    except ValueError as exc:
        raise ValueError(str(exc)) from None


class SittingIn(BaseModel):
    student_id: int
    form_id: int
    cohort_code: str = Field(min_length=1, max_length=70)
    study_group: str
    timepoint: str
    window_start: datetime
    window_end: datetime
    rater_a_id: int
    rater_b_id: int
    adjudicator_user_id: int | None = None
    data_origin: str = "pilot_test"
    form_order: str | None = None

    @field_validator("window_start", "window_end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _aware(v)


class ExtendIn(BaseModel):
    new_window_end: datetime
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("new_window_end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _aware(v)


class RetakeIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)
    window_start: datetime
    window_end: datetime
    form_id: int | None = None

    @field_validator("window_start", "window_end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _aware(v)


class ReopenIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


def teacher_user(db: Session, user_id: int | None, what: str) -> User:
    u = db.get(User, user_id) if user_id is not None else None
    if u is None or u.role != "teacher" or u.teacher_id is None:
        raise fail(400, "not_teacher", f"{what} must be a real teacher account")
    return u


def get_sitting(db: Session, sitting_id: int) -> AssessmentSitting:
    s = db.get(AssessmentSitting, sitting_id)
    if s is None:
        raise fail(404, "sitting_not_found", "Sitting not found")
    return s


def final_of(db: Session, sitting_id: int) -> AssessmentFinalScore | None:
    return db.query(AssessmentFinalScore).filter_by(sitting_id=sitting_id).first()


@router.post("/sittings")
def assign(payload: SittingIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return _assign(payload, db, admin)


def _assign(payload: SittingIn, db: Session, admin: User, *, retake_of: AssessmentSitting | None = None,
            commit: bool = True) -> dict:
    group = payload.study_group.upper()
    if group not in GROUPS or payload.timepoint not in ("T0", "T1"):
        raise fail(400, "bad_group_or_timepoint", "Invalid study group or timepoint")
    if payload.data_origin not in DATA_ORIGINS:
        raise fail(400, "bad_data_origin", f"data_origin must be one of {DATA_ORIGINS}")
    if payload.form_order is not None and payload.form_order not in FORM_ORDERS:
        raise fail(400, "bad_form_order", "form_order must be X or Y")
    if payload.window_start >= payload.window_end:
        raise fail(400, "bad_window", "Invalid window")
    if payload.rater_a_id == payload.rater_b_id:
        raise fail(400, "two_raters_required", "Two different raters required")
    ra, rb = teacher_user(db, payload.rater_a_id, "Rater A"), teacher_user(db, payload.rater_b_id, "Rater B")
    if ra.teacher_id == rb.teacher_id:
        raise fail(400, "two_raters_required", "Two different raters required")
    if payload.adjudicator_user_id is not None:
        adj = teacher_user(db, payload.adjudicator_user_id, "Adjudicator")
        if adj.teacher_id in (ra.teacher_id, rb.teacher_id):
            raise fail(400, "adjudicator_is_rater", "The adjudicator cannot be one of the raters")
    form = get_form(db, payload.form_id)
    require_published(form)
    if db.get(Student, payload.student_id) is None:
        raise fail(404, "student_not_found", "Student not found")
    cohort = db.query(StudyCohort).filter_by(cohort_code=payload.cohort_code).first()
    if cohort is not None and cohort.data_origin != payload.data_origin:
        raise fail(409, "data_origin_mismatch", "Sitting data_origin must equal its cohort's data_origin")
    enrolment = None
    if cohort is not None:
        enrolment = db.query(StudyEnrollment).filter_by(student_id=payload.student_id, cohort_id=cohort.id).first()
        if enrolment is None or enrolment.status != "enrolled":
            raise fail(409, "not_enrolled", "Student is not enrolled in this cohort")
    design = design_for(db, payload.cohort_code, payload.student_id, payload.data_origin)
    if payload.data_origin == "real_study" and (cohort is None or design is None):
        raise fail(409, "allocation_required", "Real-study sittings need a registered cohort and frozen allocations")
    form_order = payload.form_order
    if design is not None:
        if design.study_group != group:
            raise fail(409, "group_contradicts_allocation", "Study group must follow the frozen allocation record")
        if form_order and design.form_order and form_order != design.form_order:
            raise fail(409, "form_order_contradicts_allocation", "Form order must follow the frozen record")
        form_order = design.form_order or form_order
    live = db.query(AssessmentSitting).filter(AssessmentSitting.student_id == payload.student_id,
                                              AssessmentSitting.status != "voided").all()
    if any(r.timepoint == payload.timepoint for r in live):
        raise fail(409, "timepoint_assigned", "Student timepoint already assigned")
    if any(r.form_id == form.id for r in live):
        raise fail(409, "same_form_twice", "T0 and T1 must use different forms")
    # A seven-student teaching batch is indivisible: no within-batch allocation.
    batch = db.query(AssessmentSitting).filter(AssessmentSitting.cohort_code == payload.cohort_code,
                                               AssessmentSitting.status != "voided").all()
    if any(r.study_group != group for r in batch):
        raise fail(409, "cohort_split", "Cohort group assignment is immutable; cannot split a batch")
    if any(r.data_origin != payload.data_origin for r in batch):
        raise fail(409, "data_origin_mixed", "A cohort cannot mix data origins")
    limit = cohort.expected_size if cohort else 7
    if len({r.student_id for r in batch} | {payload.student_id}) > limit:
        raise fail(409, "cohort_full", f"A clerkship cohort cannot contain more than {limit} students")
    if any(r.cohort_code != payload.cohort_code or r.study_group != group for r in live):
        raise fail(409, "longitudinal_mismatch", "Student's T0/T1 must share the same cohort and allocation")
    if form_order and any(r.form_order and r.form_order != form_order for r in live):
        raise fail(409, "form_order_mismatch", "Student's T0/T1 must share the same form order")
    sitting = AssessmentSitting(
        student_id=payload.student_id, form_id=form.id, cohort_code=payload.cohort_code, study_group=group,
        timepoint=payload.timepoint, blind_code=new_blind_code(), rater_a_id=ra.id, rater_b_id=rb.id,
        adjudicator_user_id=payload.adjudicator_user_id, window_start=payload.window_start,
        window_end=payload.window_end, data_origin=payload.data_origin, form_order=form_order,
        allocation_id=design.allocation_id if design else None,
        blinding_risk=blinding_risk(db, payload.cohort_code, [ra.id, rb.id] +
                                    ([payload.adjudicator_user_id] if payload.adjudicator_user_id else [])),
        attempt_no=(retake_of.attempt_no + 1) if retake_of else 1, retake_of_id=retake_of.id if retake_of else None)
    db.add(sitting)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise fail(409, "timepoint_assigned", "Student timepoint already assigned") from None
    ensure_research_code(db, payload.student_id)
    audit(db, admin, "sitting.create" if retake_of is None else "sitting.retake", "sitting", sitting.id,
          {"form_id": form.id, "form_version": form.version, "cohort_code": payload.cohort_code, "group": group,
           "timepoint": payload.timepoint, "blinding_risk": sitting.blinding_risk, "data_origin": payload.data_origin,
           "retake_of": retake_of.id if retake_of else None})
    if commit:
        db.commit()
    return {"id": sitting.id, "status": sitting.status, "blinding_risk": sitting.blinding_risk,
            "attempt_no": sitting.attempt_no}


def _row(db: Session, s: AssessmentSitting) -> dict:
    code = db.query(ResearchCode).filter_by(student_id=s.student_id).first()
    reviews = live_reviews(db, s.id)
    fin = final_of(db, s.id)
    d = sitting_disagreement(db, s)
    return {"id": s.id, "study_student_code": code.study_student_code if code else None, "student_id": s.student_id,
            "cohort_code": s.cohort_code, "study_group": s.study_group, "timepoint": s.timepoint,
            "form_id": s.form_id, "status": s.status, "attempt_no": s.attempt_no, "data_origin": s.data_origin,
            "window_start": iso_z(s.window_start), "window_end": iso_z(effective_end(s)),
            "submitted_at": iso_z(s.submitted_at), "blinding_risk": s.blinding_risk, "blind_code": s.blind_code,
            "reviews": len(reviews), "disagreement": d, "adjudicated": db.query(AssessmentAdjudication)
            .filter_by(sitting_id=s.id).first() is not None,
            "final_score": fin.final_score if fin else None, "scoring_provenance": fin.provenance if fin else None,
            "dataset_lock_id": fin.dataset_lock_id if fin else None}


@router.get("/sittings")
def list_sittings(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [_row(db, s) for s in db.query(AssessmentSitting).order_by(AssessmentSitting.id)]


@router.get("/sittings/{sitting_id}")
def sitting_detail(sitting_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    s = get_sitting(db, sitting_id)
    events = db.query(AssessmentEvent).filter_by(sitting_id=s.id).order_by(AssessmentEvent.id).all()
    return {**_row(db, s), "events": [{"type": e.event_type, "at": iso_z(e.created_at), "detail": json.loads(e.detail_json)}
                                       for e in events]}


@router.post("/sittings/{sitting_id}/extend")
def extend(sitting_id: int, payload: ExtendIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Controlled extension of one student's window (e.g. a documented outage)."""
    s = get_sitting(db, sitting_id)
    if s.status in ("submitted", "voided"):
        raise fail(409, "not_extendable", "Submitted or voided sittings cannot be extended")
    if payload.new_window_end <= effective_end(s) or payload.new_window_end <= utcnow():
        raise fail(400, "bad_window", "New end must be later than the current end and in the future")
    old = effective_end(s)
    s.extended_until = payload.new_window_end
    if s.status == "expired":
        s.status, s.closed_reason = ("in_progress" if s.started_at else "assigned"), None
    event(db, s.id, "window_extended", {"from": iso_z(old), "to": iso_z(payload.new_window_end), "reason": payload.reason})
    audit(db, admin, "sitting.extend", "sitting", s.id, {"from": iso_z(old), "to": iso_z(payload.new_window_end),
                                                         "reason": payload.reason})
    db.commit()
    return {"id": s.id, "status": s.status, "window_end": iso_z(effective_end(s))}


@router.post("/sittings/{sitting_id}/retake")
def retake(sitting_id: int, payload: RetakeIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Void an unscored attempt and open a fresh one; the dataset keeps exactly one live attempt."""
    s = get_sitting(db, sitting_id)
    if s.status == "voided":
        raise fail(409, "already_voided", "Sitting already voided")
    if live_reviews(db, s.id) or final_of(db, s.id):
        raise fail(409, "already_scored", "A scored attempt cannot be retaken")
    if payload.window_start >= payload.window_end:
        raise fail(400, "bad_window", "Invalid window")
    body = SittingIn.model_construct(student_id=s.student_id, form_id=payload.form_id or s.form_id, cohort_code=s.cohort_code,
                     study_group=s.study_group, timepoint=s.timepoint, window_start=payload.window_start,
                     window_end=payload.window_end, rater_a_id=s.rater_a_id, rater_b_id=s.rater_b_id,
                     adjudicator_user_id=s.adjudicator_user_id, data_origin=s.data_origin, form_order=s.form_order)
    s.status, s.voided_at, s.void_reason, s.closed_reason = "voided", utcnow(), payload.reason, "voided_for_retake"
    event(db, s.id, "voided_for_retake", {"reason": payload.reason})
    db.flush()  # free the (student, timepoint) slot before the new attempt is inserted
    return _assign(body, db, admin, retake_of=s)


@router.post("/sweep-expired")
def sweep_expired(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    n = 0
    for s in db.query(AssessmentSitting).filter(AssessmentSitting.status.in_(("assigned", "in_progress"))).all():
        n += int(expire_if_needed(db, s))
    return {"expired": n}


@router.post("/reviews/{review_id}/reopen")
def reopen_review(review_id: int, payload: ReopenIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """The only way a submitted review stops counting: void it with a reason, leaving the row and an audit entry."""
    r = db.get(AssessmentReview, review_id)
    if r is None:
        raise fail(404, "review_not_found", "Review not found")
    if r.voided_at is not None:
        raise fail(409, "already_voided", "Review already voided")
    if final_of(db, r.sitting_id) or db.query(AssessmentAdjudication).filter_by(sitting_id=r.sitting_id).first():
        raise fail(409, "scoring_locked", "Scoring is locked (adjudicated or final); open a new dataset version instead")
    r.voided_at, r.voided_by_user_id, r.void_reason = utcnow(), admin.id, payload.reason
    event(db, r.sitting_id, "review_voided", {"review_id": r.id})
    audit(db, admin, "review.reopen", "review", r.id, {"sitting_id": r.sitting_id, "reason": payload.reason})
    db.commit()
    return {"status": "voided", "review_id": r.id}


@router.post("/sittings/{sitting_id}/finalize")
def finalize(sitting_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    s = get_sitting(db, sitting_id)
    existing = final_of(db, s.id)
    if existing:
        return _final_view(existing, already=True)
    if s.status != "submitted":
        raise fail(409, "not_submitted", "Only submitted sittings can be scored")
    reviews = live_reviews(db, s.id)
    if len(reviews) != 2:
        raise fail(409, "two_reviews_required", "Both raters must submit before the score can be locked")
    d = sitting_disagreement(db, s)
    a, b = reviews
    rubric = form_rubric(db.get(AssessmentForm, s.form_id))
    adj = db.query(AssessmentAdjudication).filter_by(sitting_id=s.id).first()
    if d["flagged"] and adj is None:
        raise fail(409, "adjudication_required", "Raters disagree beyond the threshold; adjudication is required")
    if d["flagged"]:
        final, prov = adj.total_score, "adjudicated"
    else:
        final, prov = round((a.total_score + b.total_score) / 2, 2), "dual_mean"
    row = AssessmentFinalScore(sitting_id=s.id, final_score=final, provenance=prov, review_a_id=a.id, review_b_id=b.id,
                               adjudication_id=adj.id if adj else None, rubric_version=rubric["rubric_version"],
                               weights_json=json.dumps(rubric["weights"]), disagreement_json=json.dumps(d),
                               locked_by_user_id=admin.id)
    db.add(row)
    audit(db, admin, "final_score.lock", "sitting", s.id, {"provenance": prov, "final_score": final})
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        return _final_view(final_of(db, s.id), already=True)
    return _final_view(row, already=False)


def _final_view(f: AssessmentFinalScore, already: bool) -> dict:
    return {"sitting_id": f.sitting_id, "final_score": f.final_score, "scoring_provenance": f.provenance,
            "locked_at": iso_z(f.locked_at), "already_locked": already}


@router.get("/audit")
def audit_log(action: str | None = None, limit: int = 200, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    q = db.query(AssessmentAuditLog)
    if action:
        q = q.filter_by(action=action)
    rows = q.order_by(AssessmentAuditLog.id.desc()).limit(max(1, min(limit, 1000))).all()
    return [{"id": r.id, "at": iso_z(r.created_at), "actor_user_id": r.actor_user_id, "actor_role": r.actor_role,
             "action": r.action, "target": f"{r.target_type}:{r.target_id}", "detail": json.loads(r.detail_json)}
            for r in rows]


@router.get("/identity-map")
def identity_map(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Study code -> student. Separate from every export and written to the audit log."""
    rows = db.query(ResearchCode, Student).join(Student, Student.id == ResearchCode.student_id).all()
    audit(db, admin, "identity_map.read", "research_codes", "all", {"rows": len(rows)})
    db.commit()
    return [{"study_student_code": c.study_student_code, "student_id": st.id, "name": st.name,
             "student_no": st.student_no} for c, st in rows]


class WindowIn(BaseModel):
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return _aware(v)


class BulkScheduleIn(BaseModel):
    data_origin: str
    forms: dict[str, int]  # {"A01": form_id, "A02": form_id}
    windows: dict[str, dict[str, WindowIn]]  # cohort_code -> {"T0": window, "T1": window}
    rater_a_id: int
    rater_b_id: int
    adjudicator_user_id: int | None = None


@router.get("/design/assignments")
def design_assignments(data_origin: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Who is in which cohort, arm and form order, as frozen by the allocation records."""
    if data_origin not in DATA_ORIGINS:
        raise fail(400, "bad_data_origin", f"data_origin must be one of {DATA_ORIGINS}")
    rows = []
    for c in db.query(StudyCohort).filter_by(data_origin=data_origin).order_by(StudyCohort.cohort_code):
        for e in db.query(StudyEnrollment).filter_by(cohort_id=c.id).order_by(StudyEnrollment.student_id):
            d = design_for(db, c.cohort_code, e.student_id, data_origin)
            code = db.query(ResearchCode).filter_by(student_id=e.student_id).first()
            rows.append({"student_id": e.student_id, "study_student_code": code.study_student_code if code else None,
                         "cohort_code": c.cohort_code, "enrollment_status": e.status,
                         "study_group": d.study_group if d else None, "form_order": d.form_order if d else None})
    audit(db, admin, "design.read", "design", data_origin, {"rows": len(rows)})
    db.commit()
    return rows


@router.post("/design/schedule")
def schedule_study(payload: BulkScheduleIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Create every enrolled student's T0 and T1 sitting from the frozen records, all-or-nothing.

    T0/T1 forms follow the student's frozen form order (X: A01 then A02, Y: A02 then A01).
    A repeat call is idempotent only when every sitting it would create already exists and
    is still untouched (same form, arm, form order and window); anything else — a started
    or submitted sitting, a changed window, a different form — is refused, so the planner
    can never produce a duplicate or a silently different schedule.
    """
    from app.research import FORM_BY_ORDER

    if payload.data_origin not in DATA_ORIGINS:
        raise fail(400, "bad_data_origin", f"data_origin must be one of {DATA_ORIGINS}")
    if set(payload.forms) != {"A01", "A02"}:
        raise fail(400, "bad_forms", "forms must map exactly A01 and A02 to published form ids")
    if payload.forms["A01"] == payload.forms["A02"]:
        raise fail(400, "bad_forms", "T0 and T1 must be two different forms")
    # Resolve both forms once, before any sitting is staged: an unapproved or unknown
    # form is an input error, not something to discover 90 rows into the plan.
    for form_id in payload.forms.values():
        require_published(get_form(db, form_id))
    cohorts = db.query(StudyCohort).filter_by(data_origin=payload.data_origin).order_by(StudyCohort.cohort_code).all()
    if not cohorts:
        raise fail(409, "no_cohorts", f"No cohort is registered with data_origin={payload.data_origin}")
    unknown = sorted(set(payload.windows) - {c.cohort_code for c in cohorts})
    if unknown:
        raise fail(400, "unknown_cohort", f"windows given for unknown cohorts: {unknown}")

    plan: list[tuple[StudyCohort, StudyEnrollment, Design, str, WindowIn]] = []
    per_cohort: dict[str, int] = {}
    for c in cohorts:
        win = payload.windows.get(c.cohort_code)
        if not win or set(win) != {"T0", "T1"}:
            raise fail(400, "missing_window", f"Cohort {c.cohort_code} needs both a T0 and a T1 window")
        if win["T1"].start <= win["T0"].end:
            raise fail(400, "bad_timepoint_order", f"Cohort {c.cohort_code}: the T0 window must close before T1 opens")
        enrolled = (db.query(StudyEnrollment).filter_by(cohort_id=c.id, status="enrolled")
                    .order_by(StudyEnrollment.student_id).all())
        if not enrolled:
            raise fail(409, "cohort_empty", f"Cohort {c.cohort_code} has no enrolled students")
        per_cohort[c.cohort_code] = len(enrolled)
        for e in enrolled:
            d = design_for(db, c.cohort_code, e.student_id, payload.data_origin)
            if d is None or d.form_order is None:
                raise fail(409, "allocation_required", "Freeze form order and group allocation first")
            for tp in ("T0", "T1"):
                plan.append((c, e, d, tp, win[tp]))

    student_ids = sorted({e.student_id for _, e, _, _, _ in plan})
    # A student may hold at most one live sitting per timepoint; index by both keys.
    existing = {(r.student_id, r.timepoint): r for r in db.query(AssessmentSitting).filter(
        AssessmentSitting.status != "voided", AssessmentSitting.student_id.in_(student_ids))}
    made, already = [], []
    try:
        for c, e, d, tp, win in plan:
            form_id = payload.forms[FORM_BY_ORDER[d.form_order][tp]]
            cur = existing.get((e.student_id, tp))
            if cur is not None:
                same = (cur.form_id == form_id and cur.cohort_code == c.cohort_code and cur.study_group == d.study_group
                        and cur.form_order == d.form_order and cur.data_origin == payload.data_origin
                        and cur.window_start == win.start and cur.window_end == win.end)
                if not same or cur.status != "assigned":
                    raise fail(409, "schedule_conflict",
                               f"Student {e.student_id} {tp} is already scheduled differently; "
                               "void or extend that sitting instead of re-planning")
                already.append(cur.id)
                continue
            body = SittingIn.model_construct(
                student_id=e.student_id, form_id=form_id, cohort_code=c.cohort_code, study_group=d.study_group,
                timepoint=tp, window_start=win.start, window_end=win.end, rater_a_id=payload.rater_a_id,
                rater_b_id=payload.rater_b_id, adjudicator_user_id=payload.adjudicator_user_id,
                data_origin=payload.data_origin, form_order=d.form_order)
            made.append(_assign(body, db, admin, commit=False)["id"])
    except Exception:
        # Nothing is committed before the whole plan succeeds; drop the staged rows and audit entries.
        db.rollback()
        raise
    audit(db, admin, "design.schedule", "design", payload.data_origin,
          {"created": len(made), "existing": len(already), "cohorts": per_cohort})
    db.commit()
    return {"created": len(made), "existing": len(already), "students": len(student_ids),
            "cohorts": per_cohort, "sitting_ids": made, "existing_ids": already}
