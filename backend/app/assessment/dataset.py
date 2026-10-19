"""Coded research export, rater-agreement table and frozen dataset versions.

Rows carry the pseudonymous study code only; the identity map is a separate,
audited admin call. A dataset lock stores the exported snapshot verbatim with its
SHA-256, so a version can be re-read byte-for-byte later.
"""
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assessment.access import fail, require_admin
from app.assessment.audit import audit, canon, sha256_text
from app.assessment.rating import live_reviews
from app.assessment.timeutil import iso_z, utcnow
from app.assessment_models import (
    AssessmentAdjudication, AssessmentDatasetLock, AssessmentFinalScore, AssessmentForm, AssessmentSitting,
    ResearchCode, StudyAllocation,
)
from app.database import get_db
from app.models import User
from app.research import DATA_ORIGINS, FORM_BY_ORDER
from app.research import teaching_log as teaching_log_module
from app.research.agreement import icc_two_way_random
from app.research.linkage import LINKAGE_VERSION, SOURCES, batch_indices, export_fields, training_linkage

router = APIRouter(prefix="/admin")


class LockIn(BaseModel):
    dataset_version: str = Field(min_length=3, max_length=60, pattern=r"^[A-Za-z0-9._-]+$")
    data_origin: str
    note: str | None = Field(default=None, max_length=1000)
    allow_incomplete: bool = False


def _origin(value: str) -> str:
    if value not in DATA_ORIGINS:
        raise fail(400, "bad_data_origin", f"data_origin must be one of {DATA_ORIGINS}")
    return value


def _missingness(s: AssessmentSitting, n_reviews: int, fin: AssessmentFinalScore | None) -> str | None:
    if fin is not None:
        return None
    if s.status == "expired":
        return "expired_unsubmitted"
    if s.status != "submitted":
        return "not_submitted"
    return "not_scored" if n_reviews < 2 else "not_finalized"


def records(db: Session, origin: str, dataset_version: str | None) -> list[dict]:
    out = []
    codes = {c.student_id: c.study_student_code for c in db.query(ResearchCode)}
    allocs = {a.id: a for a in db.query(StudyAllocation)}
    forms = {f.id: f for f in db.query(AssessmentForm)}
    # The CBL teaching register is one file: read it once per export, not per row.
    log, log_status = teaching_log_module.load()
    batches = batch_indices(db, origin)
    links: dict[tuple[int, str], dict] = {}
    q = db.query(AssessmentSitting).filter(AssessmentSitting.data_origin == origin, AssessmentSitting.status != "voided")
    for s in q.order_by(AssessmentSitting.id):
        reviews = {r.rater_slot: r for r in live_reviews(db, s.id)}
        fin = db.query(AssessmentFinalScore).filter_by(sitting_id=s.id).first()
        adj = db.query(AssessmentAdjudication).filter_by(sitting_id=s.id).first()
        a, b = reviews.get("A"), reviews.get("B")
        alloc = allocs.get(s.allocation_id)
        form = forms[s.form_id]
        # Read-only join: the Training domain (and the CBL teaching register) are
        # read here, never invoked. Both timepoints of one student share a linkage.
        key = (s.student_id, s.cohort_code)
        if key not in links:
            links[key] = training_linkage(db, student_id=s.student_id, cohort_code=s.cohort_code,
                                          data_origin=origin, log=log, log_status=log_status)
        link = links[key]
        training_exposure, intervention_count, cbl_topics = export_fields(link)
        out.append({
            "study_student_code": codes.get(s.student_id), "cohort_id": s.cohort_code,
            "batch_index": batches.get(s.cohort_code),
            "study_group": s.study_group.lower(),
            "randomization_version": alloc.allocation_version if alloc else None,
            "randomization_mode": alloc.mode if alloc else None,
            "timepoint": s.timepoint, "assessment_form_id": form.id, "assessment_form_code": form.code,
            # The slot the sitting was scheduled under, from the frozen form order. The
            # frozen CSV validates *this* against form_order and timepoint; the id above
            # is a local database key and cannot be compared with a slot code.
            "assessment_form_slot": FORM_BY_ORDER.get(s.form_order, {}).get(s.timepoint),
            "assessment_form_version": form.version, "form_order": s.form_order, "attempt_no": s.attempt_no,
            "blinded_rater_1_score": a.total_score if a else None,
            "blinded_rater_2_score": b.total_score if b else None,
            "rater_1_dimensions": json.loads(a.scores_json) if a else None,
            "rater_2_dimensions": json.loads(b.scores_json) if b else None,
            "absolute_total_diff": round(abs(a.total_score - b.total_score), 4) if a and b else None,
            "adjudicated_score": adj.total_score if adj else None,
            "final_score": fin.final_score if fin else None,
            "scoring_provenance": fin.provenance if fin else None,
            "rubric_version": fin.rubric_version if fin else (a.rubric_version if a else None),
            "assessment_completed_at": iso_z(s.submitted_at), "sitting_status": s.status,
            "missingness": _missingness(s, len(reviews), fin), "blinding_risk": s.blinding_risk,
            # Joined from the Training domain by the Research layer, never by this module.
            "training_exposure": training_exposure, "intervention_count": intervention_count,
            "cbl_case_topics": cbl_topics, "linkage": link,
            "dataset_version": dataset_version, "data_origin": s.data_origin,
        })
    return out


def _provenance(recs: list[dict]) -> dict:
    """Where each part of the export comes from. Derived from the rows themselves, so a
    frozen snapshot can never claim a register it did not actually read."""
    register = recs[0]["linkage"]["cbl_teaching"]["register"] if recs else {}
    return {
        "independent_assessment": SOURCES["independent_assessment"],
        "training": SOURCES["training"],
        "teaching_log": register,
        "study_allocation": SOURCES["study_allocation"],
        "research_metadata": {"linkage_version": LINKAGE_VERSION, "sources": SOURCES["research_metadata"]},
    }


@router.get("/export")
def research_export(data_origin: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Working (not frozen) coded dataset for one data origin. Origins are never mixed."""
    _origin(data_origin)
    recs = records(db, data_origin, None)
    audit(db, admin, "export.read", "dataset", data_origin, {"records": len(recs)})
    db.commit()
    return {"data_origin": data_origin, "dataset_status": "WORKING_NOT_FROZEN",
            "provenance": _provenance(recs), "records": recs}


@router.get("/agreement")
def agreement(data_origin: str, timepoint: str | None = None, db: Session = Depends(get_db),
              admin: User = Depends(require_admin)):
    """Raw dual ratings plus ICC(2,1)/ICC(2,k); says so honestly when the sample is too small."""
    _origin(data_origin)
    rows = [r for r in records(db, data_origin, None) if r["blinded_rater_1_score"] is not None
            and r["blinded_rater_2_score"] is not None and (timepoint is None or r["timepoint"] == timepoint)]
    icc = icc_two_way_random([[r["blinded_rater_1_score"], r["blinded_rater_2_score"]] for r in rows])
    audit(db, admin, "agreement.read", "dataset", data_origin, {"pairs": len(rows)})
    db.commit()
    return {"data_origin": data_origin, "timepoint": timepoint, "pairs": [
        {k: r[k] for k in ("study_student_code", "timepoint", "blinded_rater_1_score", "blinded_rater_2_score",
                           "absolute_total_diff", "adjudicated_score", "final_score", "scoring_provenance",
                           "rater_1_dimensions", "rater_2_dimensions")} for r in rows], "icc": icc}


@router.post("/dataset-locks")
def lock_dataset(payload: LockIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    origin = _origin(payload.data_origin)
    recs = records(db, origin, payload.dataset_version)
    if not recs:
        raise fail(409, "empty_dataset", "Nothing to freeze for this data origin")
    missing = [r for r in recs if r["final_score"] is None]
    if missing and not payload.allow_incomplete:
        raise fail(409, "not_final", f"{len(missing)} of {len(recs)} sittings have no locked final score; "
                                     "finalize them or set allow_incomplete")
    locked_at = utcnow()
    snapshot = {"dataset_version": payload.dataset_version, "data_origin": origin, "locked_at": iso_z(locked_at),
                "locked_by_user_id": admin.id, "records": recs, "provenance": _provenance(recs),
                "summary": {"records": len(recs), "incomplete": len(missing),
                            "blinding_risk_records": sum(r["blinding_risk"] == "TEACHES_COHORT" for r in recs)}}
    text = canon(snapshot)
    lock = AssessmentDatasetLock(dataset_version=payload.dataset_version, data_origin=origin, locked_at=locked_at,
                                 locked_by_user_id=admin.id, note=payload.note, record_count=len(recs),
                                 snapshot_json=text, snapshot_sha256=sha256_text(text))
    db.add(lock)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise fail(409, "version_exists", "Dataset version already exists") from None
    for f in db.query(AssessmentFinalScore).join(AssessmentSitting, AssessmentSitting.id == AssessmentFinalScore.sitting_id) \
            .filter(AssessmentSitting.data_origin == origin, AssessmentFinalScore.dataset_lock_id.is_(None)):
        f.dataset_lock_id = lock.id
    audit(db, admin, "dataset.lock", "dataset", payload.dataset_version,
          {"records": len(recs), "incomplete": len(missing), "sha256": lock.snapshot_sha256})
    db.commit()
    return {"dataset_version": lock.dataset_version, "records": lock.record_count, "sha256": lock.snapshot_sha256,
            "locked_at": iso_z(lock.locked_at)}


@router.get("/dataset-locks")
def list_locks(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [{"dataset_version": l.dataset_version, "data_origin": l.data_origin, "records": l.record_count,
             "sha256": l.snapshot_sha256, "locked_at": iso_z(l.locked_at), "note": l.note}
            for l in db.query(AssessmentDatasetLock).order_by(AssessmentDatasetLock.id)]


@router.get("/dataset-locks/{dataset_version}")
def get_lock(dataset_version: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    lock = db.query(AssessmentDatasetLock).filter_by(dataset_version=dataset_version).first()
    if lock is None:
        raise fail(404, "lock_not_found", "Dataset version not found")
    audit(db, admin, "export.read", "dataset", dataset_version, {"frozen": True})
    db.commit()
    return {"sha256": lock.snapshot_sha256, "integrity_ok": sha256_text(lock.snapshot_json) == lock.snapshot_sha256,
            "snapshot": json.loads(lock.snapshot_json)}
