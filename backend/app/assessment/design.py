"""Cohorts, enrollment and the frozen allocations that decide group and form order.

The random draws themselves live in ``app.research.randomization`` (pure code).
This module only persists their records, refuses a second draw, and exposes the
result to the scheduling code.
"""
import json
import secrets
from dataclasses import dataclass
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assessment.access import fail, require_admin
from app.assessment.audit import audit
from app.assessment.blinding import ensure_research_code
from app.assessment.timeutil import iso_z, utcnow
from app.assessment_models import ResearchCode, StudyAllocation, StudyCohort, StudyEnrollment
from app.database import get_db
from app.models import Student, User
from app.research import DATA_ORIGINS, MODE_QUASI, MODE_RANDOMIZED, ResearchError
from app.research.randomization import (
    assign_form_orders, draw_cluster_allocation, record_quasi_experimental_allocation,
    verify_allocation_record, verify_form_order_record,
)

router = APIRouter(prefix="/admin")
KIND_FORM_ORDER, KIND_CLUSTER = "form_order", "cluster_group"


class CohortIn(BaseModel):
    cohort_code: str = Field(min_length=1, max_length=70)
    label: str = Field(min_length=1, max_length=120)
    expected_size: int = Field(default=7, ge=1, le=7)
    planned_start: date | None = None
    planned_end: date | None = None
    teaching_user_ids: list[int] = []
    study_admin_user_id: int | None = None
    data_origin: str = "pilot_test"


class ActualDatesIn(BaseModel):
    actual_start: date
    actual_end: date


class EnrollIn(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=7)


class FormOrderIn(BaseModel):
    data_origin: str = "pilot_test"
    protocol_version: str = Field(min_length=1, max_length=60)
    seed: str | None = Field(default=None, min_length=8, max_length=128)  # server draws one if omitted


class ClusterIn(BaseModel):
    data_origin: str = "pilot_test"
    protocol_version: str = Field(min_length=1, max_length=60)
    mode: str = MODE_RANDOMIZED
    seed: str | None = Field(default=None, min_length=8, max_length=128)
    clinpath_cohorts: list[str] | None = None  # quasi_experimental only


@dataclass
class Design:
    study_group: str
    form_order: str | None
    allocation_id: int


def _origin(value: str) -> str:
    if value not in DATA_ORIGINS:
        raise fail(400, "bad_data_origin", f"data_origin must be one of {DATA_ORIGINS}")
    return value


def stored_allocation(db: Session, kind: str, origin: str) -> StudyAllocation | None:
    return db.query(StudyAllocation).filter_by(kind=kind, data_origin=origin).first()


def design_for(db: Session, cohort_code: str, student_id: int, origin: str) -> Design | None:
    """Group and form order dictated by the frozen records, or None if nothing is frozen yet."""
    cluster = stored_allocation(db, KIND_CLUSTER, origin)
    if cluster is None:
        return None
    rec = json.loads(cluster.record_json)
    group = "CLINPATH" if cohort_code in rec["clinpath_cohorts"] else "CBL" if cohort_code in rec["cbl_cohorts"] else None
    if group is None:
        return None
    order = None
    fo = stored_allocation(db, KIND_FORM_ORDER, origin)
    code = db.query(ResearchCode).filter_by(student_id=student_id).first()
    if fo is not None and code is not None:
        for sc, _, o in json.loads(fo.record_json)["assignments"]:
            if sc == code.study_student_code:
                order = o
    return Design(group, order, cluster.id)


@router.post("/cohorts")
def create_cohort(payload: CohortIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    _origin(payload.data_origin)
    if payload.planned_start and payload.planned_end and payload.planned_end < payload.planned_start:
        raise fail(400, "bad_dates", "planned_end precedes planned_start")
    for uid in payload.teaching_user_ids:
        u = db.get(User, uid)
        if u is None or u.role not in ("teacher", "admin"):
            raise fail(400, "bad_teacher", "teaching_user_ids must be staff accounts")
    if db.query(StudyCohort).filter_by(cohort_code=payload.cohort_code).first():
        raise fail(409, "cohort_exists", "Cohort code already exists")
    c = StudyCohort(cohort_code=payload.cohort_code, label=payload.label, expected_size=payload.expected_size,
                    planned_start=payload.planned_start, planned_end=payload.planned_end,
                    teaching_user_ids_json=json.dumps(sorted(set(payload.teaching_user_ids))),
                    study_admin_user_id=payload.study_admin_user_id or admin.id, data_origin=payload.data_origin,
                    created_by_user_id=admin.id)
    db.add(c)
    db.flush()
    audit(db, admin, "cohort.create", "cohort", c.cohort_code, {"data_origin": c.data_origin})
    db.commit()
    return _cohort(db, c)


def _cohort(db: Session, c: StudyCohort) -> dict:
    members = db.query(StudyEnrollment).filter_by(cohort_id=c.id).count()
    return {"id": c.id, "cohort_code": c.cohort_code, "label": c.label, "expected_size": c.expected_size,
            "enrolled": members, "planned_start": str(c.planned_start) if c.planned_start else None,
            "planned_end": str(c.planned_end) if c.planned_end else None,
            "actual_start": str(c.actual_start) if c.actual_start else None,
            "actual_end": str(c.actual_end) if c.actual_end else None,
            "teaching_user_ids": json.loads(c.teaching_user_ids_json), "data_origin": c.data_origin,
            "study_admin_user_id": c.study_admin_user_id}


@router.get("/cohorts")
def list_cohorts(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [_cohort(db, c) for c in db.query(StudyCohort).order_by(StudyCohort.id)]


@router.post("/cohorts/{cohort_code}/actual-dates")
def set_actual_dates(cohort_code: str, payload: ActualDatesIn, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    c = db.query(StudyCohort).filter_by(cohort_code=cohort_code).first()
    if c is None:
        raise fail(404, "cohort_not_found", "Cohort not found")
    if payload.actual_end < payload.actual_start:
        raise fail(400, "bad_dates", "actual_end precedes actual_start")
    c.actual_start, c.actual_end = payload.actual_start, payload.actual_end
    audit(db, admin, "cohort.actual_dates", "cohort", c.cohort_code, {"start": str(payload.actual_start), "end": str(payload.actual_end)})
    db.commit()
    return _cohort(db, c)


@router.post("/cohorts/{cohort_code}/enrollments")
def enroll(cohort_code: str, payload: EnrollIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    c = db.query(StudyCohort).filter_by(cohort_code=cohort_code).first()
    if c is None:
        raise fail(404, "cohort_not_found", "Cohort not found")
    if stored_allocation(db, KIND_FORM_ORDER, c.data_origin):
        raise fail(409, "allocation_frozen", "Enrollment is closed once form order has been frozen")
    ids = sorted(set(payload.student_ids))
    if any(db.get(Student, i) is None for i in ids):
        raise fail(404, "student_not_found", "Student not found")
    if db.query(StudyEnrollment).filter(StudyEnrollment.student_id.in_(ids)).first():
        raise fail(409, "already_enrolled", "A student can belong to only one cohort")
    if db.query(StudyEnrollment).filter_by(cohort_id=c.id).count() + len(ids) > c.expected_size:
        raise fail(409, "cohort_full", f"Cohort cannot exceed {c.expected_size} students")
    for i in ids:
        db.add(StudyEnrollment(cohort_id=c.id, student_id=i, enrolled_by_user_id=admin.id))
        ensure_research_code(db, i)
    audit(db, admin, "cohort.enroll", "cohort", c.cohort_code, {"count": len(ids)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise fail(409, "already_enrolled", "A student can belong to only one cohort") from None
    return _cohort(db, c)


def _cohorts_for_draw(db: Session, origin: str) -> list[StudyCohort]:
    cohorts = db.query(StudyCohort).filter_by(data_origin=origin).order_by(StudyCohort.cohort_code).all()
    if len(cohorts) != 7:
        raise fail(409, "need_seven_cohorts", f"Exactly 7 cohorts with data_origin={origin} are required, found {len(cohorts)}")
    for c in cohorts:
        n = db.query(StudyEnrollment).filter_by(cohort_id=c.id, status="enrolled").count()
        if n != c.expected_size:
            raise fail(409, "cohort_incomplete", f"Cohort {c.cohort_code} has {n} of {c.expected_size} students")
    return cohorts


def _store(db: Session, admin: User, kind: str, record: dict, origin: str, mode: str, protocol: str, version: str) -> StudyAllocation:
    row = StudyAllocation(kind=kind, allocation_version=version, mode=mode, protocol_version=protocol,
                          record_json=json.dumps(record, ensure_ascii=False, sort_keys=True),
                          record_sha256=record["content_hash"], data_origin=origin, executed_by_user_id=admin.id)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise fail(409, "already_drawn", "This allocation was already recorded; there is no redraw") from None
    return row


@router.post("/allocations/form-order")
def freeze_form_order(payload: FormOrderIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    origin = _origin(payload.data_origin)
    if stored_allocation(db, KIND_FORM_ORDER, origin):
        raise fail(409, "already_drawn", "Form order is already frozen; there is no redraw")
    cohorts = _cohorts_for_draw(db, origin)
    members = {}
    for c in cohorts:
        members[c.cohort_code] = [ensure_research_code(db, e.student_id) for e in
                                  db.query(StudyEnrollment).filter_by(cohort_id=c.id, status="enrolled")]
    seed = payload.seed or secrets.token_hex(16)
    try:
        rec = assign_form_orders(members, seed=seed, protocol_version=payload.protocol_version,
                                 executor=f"user:{admin.id}", frozen_at=utcnow().isoformat(timespec="microseconds"))
        verify_form_order_record(rec)
    except ResearchError as exc:
        raise fail(400, "research_error", str(exc)) from None
    row = _store(db, admin, KIND_FORM_ORDER, rec.to_dict(), origin, "frozen", payload.protocol_version,
                 f"FORM-ORDER-{origin}-{rec.content_hash[:12]}")
    audit(db, admin, "allocation.form_order", "allocation", row.allocation_version, {"hash": rec.content_hash})
    db.commit()
    return {"allocation_version": row.allocation_version, "content_hash": rec.content_hash, "executed_at": iso_z(row.executed_at)}


@router.post("/allocations/cluster")
def draw_cluster(payload: ClusterIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    origin = _origin(payload.data_origin)
    fo = stored_allocation(db, KIND_FORM_ORDER, origin)
    if fo is None:
        raise fail(409, "form_order_first", "Freeze the form order before the group draw")
    if stored_allocation(db, KIND_CLUSTER, origin):
        raise fail(409, "already_drawn", "Group allocation is already recorded; there is no redraw")
    cohorts = [c.cohort_code for c in _cohorts_for_draw(db, origin)]
    fo_rec = verify_form_order_record(json.loads(fo.record_json))
    drawn_at = max(utcnow(), _plus_us(fo.record_json)).isoformat(timespec="microseconds")
    try:
        if payload.mode == MODE_RANDOMIZED:
            rec = draw_cluster_allocation(fo_rec, cohort_ids=cohorts, seed=payload.seed or secrets.token_hex(16),
                                          protocol_version=payload.protocol_version, executor=f"user:{admin.id}",
                                          drawn_at=drawn_at)
        elif payload.mode == MODE_QUASI:
            rec = record_quasi_experimental_allocation(fo_rec, clinpath_cohorts=payload.clinpath_cohorts or [],
                                                       cohort_ids=cohorts, protocol_version=payload.protocol_version,
                                                       executor=f"user:{admin.id}", assigned_at=drawn_at)
        else:
            raise fail(400, "bad_mode", "mode must be randomized or quasi_experimental")
        verify_allocation_record(rec, fo_rec)
    except ResearchError as exc:
        raise fail(400, "research_error", str(exc)) from None
    row = _store(db, admin, KIND_CLUSTER, rec.to_dict(), origin, rec.mode, payload.protocol_version,
                 f"CLUSTER-{origin}-{rec.content_hash[:12]}")
    audit(db, admin, "allocation.cluster", "allocation", row.allocation_version, {"mode": rec.mode, "hash": rec.content_hash})
    db.commit()
    return {"allocation_version": row.allocation_version, "mode": rec.mode, "content_hash": rec.content_hash,
            "clinpath_cohorts": list(rec.clinpath_cohorts), "cbl_cohorts": list(rec.cbl_cohorts)}


def _plus_us(form_order_json: str):
    from datetime import datetime, timedelta
    return datetime.fromisoformat(json.loads(form_order_json)["frozen_at"]) + timedelta(microseconds=1)


@router.get("/allocations")
def list_allocations(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [{"allocation_version": a.allocation_version, "kind": a.kind, "mode": a.mode, "data_origin": a.data_origin,
             "protocol_version": a.protocol_version, "content_hash": a.record_sha256, "executed_at": iso_z(a.executed_at),
             "executed_by_user_id": a.executed_by_user_id,
             "record": json.loads(a.record_json) if a.kind == KIND_CLUSTER else {"cohorts": sorted({x[1] for x in json.loads(a.record_json)["assignments"]})}}
            for a in db.query(StudyAllocation).order_by(StudyAllocation.id)]
