"""Form authoring, two-teacher review and publication (versions freeze at publication)."""
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.assessment.access import fail, require_admin, require_author, require_teacher
from app.assessment.audit import audit, canon, sha256_text
from app.assessment.rubric import RubricError, normalize_rubric
from app.assessment.timeutil import iso_z, utcnow
from app.assessment_models import (
    AssessmentForm, AssessmentFormReview, AssessmentFormReviewer, AssessmentSitting,
)
from app.database import get_db
from app.models import User

router = APIRouter()
EDITABLE = ("PENDING_REAL_REVIEW", "CHANGES_REQUESTED")
STAGE_KEYS = ("title", "clinical_information", "question")


class FormIn(BaseModel):
    code: str = Field(min_length=2, max_length=60)
    title: str = Field(min_length=2, max_length=200)
    stages: list[dict]
    answer_key: dict
    rubric: dict


class FormVersionIn(BaseModel):
    """Only the fields that change; everything else is copied from the source version."""
    title: str | None = Field(default=None, min_length=2, max_length=200)
    stages: list[dict] | None = None
    answer_key: dict | None = None
    rubric: dict | None = None


class ReviewersIn(BaseModel):
    teacher_user_ids: list[int] = Field(min_length=2)


class FormReviewIn(BaseModel):
    decision: str
    comment: str = Field(min_length=2)


def load(value: str):
    return json.loads(value)


def form_rubric(form: AssessmentForm) -> dict:
    """The rubric as the raters must use it. Legacy rows without weights get the labelled study default."""
    return normalize_rubric(load(form.rubric_json))


def form_hash(title: str, stages: list, key: dict, rubric: dict) -> str:
    return sha256_text(canon({"title": title, "stages": stages, "answer_key": key, "rubric": rubric}))


def _check_stages(stages: list[dict]) -> None:
    if len(stages) != 5 or any(not all(isinstance(s.get(k), str) and s[k].strip() for k in STAGE_KEYS) for s in stages):
        raise fail(400, "bad_stages", "Exactly five complete stages are required")


def _rubric(raw: dict) -> dict:
    try:
        return normalize_rubric(raw)
    except RubricError as exc:
        raise fail(400, "bad_rubric", str(exc)) from None


def get_form(db: Session, form_id: int) -> AssessmentForm:
    form = db.get(AssessmentForm, form_id)
    if form is None:
        raise fail(404, "form_not_found", "Form not found")
    return form


def require_published(form: AssessmentForm) -> None:
    if form.review_status != "APPROVED_FOR_ASSESSMENT":
        raise fail(409, "form_not_approved", "Independent assessment form not approved")


def _content(form: AssessmentForm) -> dict:
    return {"stages": load(form.stages_json), "rubric": load(form.rubric_json), "answer_key": load(form.key_json)}


def _save_new(db: Session, user: User, *, code, version, title, stages, key, rubric, supersedes=None) -> AssessmentForm:
    form = AssessmentForm(code=code, version=version, title=title,
                          stages_json=json.dumps(stages, ensure_ascii=False),
                          key_json=json.dumps(key, ensure_ascii=False),
                          rubric_json=json.dumps(rubric, ensure_ascii=False),
                          author_user_id=user.id, supersedes_form_id=supersedes,
                          content_sha256=form_hash(title, stages, key, rubric))
    db.add(form)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise fail(409, "form_exists", "Form code/version already exists") from None
    return form


@router.post("/forms")
def create_form(payload: FormIn, db: Session = Depends(get_db), user: User = Depends(require_author)):
    _check_stages(payload.stages)
    rubric = _rubric(payload.rubric)
    if db.query(AssessmentForm).filter_by(code=payload.code).first():
        raise fail(409, "form_exists", "Form code already exists; create a new version instead")
    form = _save_new(db, user, code=payload.code, version=1, title=payload.title, stages=payload.stages,
                     key=payload.answer_key, rubric=rubric)
    audit(db, user, "form.create", "form", form.id, {"code": form.code, "version": 1})
    db.commit()
    return {"id": form.id, "code": form.code, "version": form.version, "review_status": form.review_status}


@router.post("/forms/{form_id}/versions")
def new_version(form_id: int, payload: FormVersionIn, db: Session = Depends(get_db),
                user: User = Depends(require_author)):
    """Any change to medical content becomes a new version; published versions never change."""
    src = get_form(db, form_id)
    latest = db.query(AssessmentForm).filter_by(code=src.code).order_by(AssessmentForm.version.desc()).first()
    stages = payload.stages if payload.stages is not None else load(src.stages_json)
    _check_stages(stages)
    rubric = _rubric(payload.rubric if payload.rubric is not None else load(src.rubric_json))
    key = payload.answer_key if payload.answer_key is not None else load(src.key_json)
    title = payload.title or src.title
    if form_hash(title, stages, key, rubric) == src.content_sha256:
        raise fail(409, "no_change", "New version must change the content")
    form = _save_new(db, user, code=src.code, version=latest.version + 1, title=title, stages=stages, key=key,
                     rubric=rubric, supersedes=src.id)
    if src.review_status in EDITABLE:
        src.review_status = "SUPERSEDED"
    audit(db, user, "form.new_version", "form", form.id, {"code": form.code, "version": form.version, "from": src.id})
    db.commit()
    return {"id": form.id, "code": form.code, "version": form.version, "review_status": form.review_status}


@router.get("/forms/admin/all")
def all_forms(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    forms = db.query(AssessmentForm).order_by(AssessmentForm.id).all()
    return [{"id": f.id, "code": f.code, "version": f.version, "title": f.title,
             "review_status": f.review_status, "published_at": iso_z(f.published_at)} for f in forms]


@router.get("/forms/reviewable")
def reviewable_forms(db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    """Only forms this teacher was invited to review: an exam is confidential before it runs."""
    ids = [r.form_id for r in db.query(AssessmentFormReviewer).filter_by(teacher_user_id=user.id).all()]
    forms = db.query(AssessmentForm).filter(AssessmentForm.id.in_(ids), AssessmentForm.review_status.in_(EDITABLE)) \
        .order_by(AssessmentForm.id).all() if ids else []
    out = []
    for f in forms:
        mine = db.query(AssessmentFormReview).filter_by(form_id=f.id, teacher_user_id=user.id).first()
        out.append({"id": f.id, "code": f.code, "version": f.version, "title": f.title, "review_status": f.review_status,
                    **_content(f), "reviewed_by_me": mine is not None,
                    "my_decision": mine.decision if mine else None})
    return out


@router.get("/forms/{form_id}/admin")
def form_review_status(form_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    form = get_form(db, form_id)
    reviews = db.query(AssessmentFormReview).filter_by(form_id=form_id).all()
    reviewers = db.query(AssessmentFormReviewer).filter_by(form_id=form_id).all()
    return {"id": form.id, "code": form.code, "version": form.version, "review_status": form.review_status,
            "content_sha256": form.content_sha256, "author_user_id": form.author_user_id,
            "published_at": iso_z(form.published_at),
            "sittings": db.query(AssessmentSitting).filter_by(form_id=form_id).count(),
            "assigned_reviewers": [r.teacher_user_id for r in reviewers],
            "reviews": [{"teacher_user_id": r.teacher_user_id, "decision": r.decision, "comment": r.comment,
                         "reviewed_at": iso_z(r.reviewed_at),
                         "matches_current_content": r.form_content_sha256 == form.content_sha256}
                        for r in reviews],
            **_content(form)}


@router.post("/forms/{form_id}/reviewers")
def assign_reviewers(form_id: int, payload: ReviewersIn, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    form = get_form(db, form_id)
    if form.review_status not in EDITABLE:
        raise fail(409, "form_frozen", "Only forms under review can get reviewers")
    users = [db.get(User, uid) for uid in set(payload.teacher_user_ids)]
    if any(u is None or u.role != "teacher" or u.teacher_id is None for u in users):
        raise fail(400, "not_teachers", "Reviewers must be real teacher accounts")
    if len({u.teacher_id for u in users}) < 2:
        raise fail(400, "distinct_reviewers", "At least two distinct teachers are required")
    if form.author_user_id in {u.id for u in users}:
        raise fail(400, "author_cannot_review", "The author of a form cannot be one of its reviewers")
    existing = {r.teacher_user_id for r in db.query(AssessmentFormReviewer).filter_by(form_id=form_id)}
    for u in users:
        if u.id not in existing:
            db.add(AssessmentFormReviewer(form_id=form_id, teacher_user_id=u.id, assigned_by_user_id=admin.id))
    audit(db, admin, "form.assign_reviewers", "form", form_id, {"teacher_user_ids": sorted(u.id for u in users)})
    db.commit()
    return {"form_id": form_id, "assigned_reviewers": sorted(existing | {u.id for u in users})}


@router.post("/forms/{form_id}/review")
def review_form(form_id: int, payload: FormReviewIn, db: Session = Depends(get_db),
                user: User = Depends(require_teacher)):
    form = get_form(db, form_id)
    if db.query(AssessmentFormReviewer).filter_by(form_id=form_id, teacher_user_id=user.id).first() is None:
        raise fail(404, "form_not_found", "Form not found")  # unassigned teachers do not learn it exists
    if payload.decision not in ("approve", "reject"):
        raise fail(400, "bad_decision", "Invalid decision")
    if form.review_status not in EDITABLE:
        raise fail(409, "form_frozen", "Form is frozen or superseded")
    db.add(AssessmentFormReview(form_id=form_id, teacher_user_id=user.id, decision=payload.decision,
                                comment=payload.comment, form_content_sha256=form.content_sha256))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise fail(409, "already_reviewed", "Teacher already reviewed") from None
    if payload.decision == "reject":
        form.review_status = "CHANGES_REQUESTED"
    db.commit()
    return {"status": "recorded"}


@router.post("/forms/{form_id}/approve")
def approve_form(form_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Publication needs two distinct real teachers' approvals of *this exact content*.

    The admin verifies and publishes; the endpoint takes no reviewer input, so an admin
    cannot supply or forge a teacher's decision.
    """
    form = get_form(db, form_id)
    if form.review_status == "APPROVED_FOR_ASSESSMENT":
        raise fail(409, "form_frozen", "Approved form is frozen")
    if form.review_status not in EDITABLE:
        raise fail(409, "form_superseded", "Form is superseded")
    assigned = {r.teacher_user_id for r in db.query(AssessmentFormReviewer).filter_by(form_id=form_id)}
    reviews = [r for r in db.query(AssessmentFormReview).filter_by(form_id=form_id)
               if r.teacher_user_id in assigned]
    users = {r.teacher_user_id: db.get(User, r.teacher_user_id) for r in reviews}
    good = [r for r in reviews if r.decision == "approve" and r.form_content_sha256 == form.content_sha256
            and users[r.teacher_user_id].role == "teacher" and users[r.teacher_user_id].teacher_id is not None
            and r.teacher_user_id != form.author_user_id]
    if any(r.decision != "approve" for r in reviews) or len({users[r.teacher_user_id].teacher_id for r in good}) < 2:
        raise fail(409, "two_approvals_required", "Two distinct teacher approvals of the current content required")
    form.review_status = "APPROVED_FOR_ASSESSMENT"
    form.published_at = utcnow()
    form.published_by_user_id = admin.id
    audit(db, admin, "form.publish", "form", form.id,
          {"code": form.code, "version": form.version, "content_sha256": form.content_sha256,
           "approving_teacher_user_ids": sorted(r.teacher_user_id for r in good)})
    db.commit()
    return {"id": form.id, "review_status": form.review_status}


@router.get("/forms/mine")
def my_forms(db: Session = Depends(get_db), user: User = Depends(require_author)):
    """Forms this author created, newest version per code, metadata only.

    A teacher needs this to reopen their own draft and to start a new version; the
    admin listing is admin-only and the reviewable list only shows forms they were
    invited to review. Bodies are omitted on purpose — a new version is built from
    the version's own admin detail, not from a list response.
    """
    rows = db.query(AssessmentForm).filter(AssessmentForm.author_user_id == user.id).all()
    newest: dict[str, AssessmentForm] = {}
    for form in rows:
        seen = newest.get(form.code)
        if seen is None or form.version > seen.version:
            newest[form.code] = form
    out = [{"id": f.id, "code": f.code, "version": f.version, "title": f.title,
            "review_status": f.review_status, "published_at": iso_z(f.published_at)}
           for f in newest.values()]
    out.sort(key=lambda r: (r["code"], r["version"]))
    return out
