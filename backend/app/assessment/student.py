"""Student-facing sitting API: server-driven stage release, drafts, idempotent submission.

Every rule is enforced here on the server; hiding buttons in the UI is not relied on.
This module never calls AI, Training scoring, competency or recommendation code.
"""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.assessment.access import fail, require_student
from app.assessment.audit import event, sha256_text
from app.assessment.forms import load, require_published
from app.assessment.timeutil import iso_z, utcnow
from app.assessment_models import AssessmentAnswer, AssessmentAnswerRevision, AssessmentForm, AssessmentSitting
from app.database import get_db
from app.models import User

router = APIRouter()
N_STAGES = 5
INSTRUCTIONS = (
    "这是一次独立在线考核，不是训练：系统不会给出提示、AI追问、正确答案或自动评分。"
    "请独立作答，不要查阅他人或使用AI工具。"
    "请不要在答案中写入你的姓名、学号、床号等可识别信息，以保证评阅的匿名性。"
    "每个阶段提交后不能修改，下一阶段才会显示新增的临床资料。"
    "草稿会自动保存在服务器上，断网或刷新后可继续作答；超出开放时间将无法提交。"
)
LIVE = ("assigned", "in_progress")


class DraftIn(BaseModel):
    stage_index: int = Field(ge=0, le=N_STAGES - 1)
    answer_text: str = Field(max_length=16000)


class AnswerIn(BaseModel):
    # Required: the server compares it with its own progress so a double click or a
    # tampered request can neither skip a stage nor answer the next stage twice.
    stage_index: int = Field(ge=0, le=N_STAGES - 1)
    answer_text: str = Field(min_length=1, max_length=16000)


class InterruptionIn(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


def effective_end(s: AssessmentSitting) -> datetime:
    return max(s.window_end, s.extended_until) if s.extended_until else s.window_end


def own_sitting(db: Session, sitting_id: int, user: User) -> AssessmentSitting:
    s = db.get(AssessmentSitting, sitting_id)
    # Another student's id and a non-existent id look the same.
    if s is None or s.student_id != user.student_id or s.status == "voided":
        raise fail(404, "sitting_not_found", "Sitting not found")
    return s


def expire_if_needed(db: Session, s: AssessmentSitting, now: datetime | None = None) -> bool:
    """Materialise 'the window closed before submission' exactly once. Returns True if expired."""
    now = now or utcnow()
    if s.status in LIVE and now >= effective_end(s):
        done = db.query(AssessmentAnswer).filter_by(sitting_id=s.id).count()
        drafts = db.query(AssessmentAnswerRevision).filter_by(sitting_id=s.id, kind="draft").count()
        s.status, s.closed_reason = "expired", "window_closed_unsubmitted"
        event(db, s.id, "window_expired", {"stages_completed": done, "draft_saves": drafts,
                                           "was_started": s.started_at is not None})
        db.commit()
    return s.status == "expired"


def _open(db: Session, s: AssessmentSitting, *, write: bool) -> None:
    """Gate every read/write of exam content."""
    now = utcnow()
    if now < s.window_start:
        raise fail(403, "window_not_open", "Assessment window has not opened")
    if s.status == "submitted" or (s.status == "expired" and not write):
        return
    if expire_if_needed(db, s, now):
        if write:
            event(db, s.id, "late_write_refused", {})
            db.commit()
        raise fail(403, "window_closed", "Assessment window is closed")
    form = db.get(AssessmentForm, s.form_id)
    require_published(form)


def _answers(db: Session, s: AssessmentSitting) -> dict[int, AssessmentAnswer]:
    return {a.stage_index: a for a in db.query(AssessmentAnswer).filter_by(sitting_id=s.id)}


def _stage(form: AssessmentForm, index: int) -> dict:
    st = load(form.stages_json)[index]
    return {"index": index, "title": st["title"], "clinical_information": st["clinical_information"],
            "question": st["question"]}


def _latest_draft(db: Session, s: AssessmentSitting, stage: int) -> AssessmentAnswerRevision | None:
    return db.query(AssessmentAnswerRevision).filter_by(sitting_id=s.id, stage_index=stage, kind="draft") \
        .order_by(AssessmentAnswerRevision.revision_no.desc()).first()


def _view(db: Session, s: AssessmentSitting) -> dict:
    base = {"sitting_id": s.id, "status": s.status, "timepoint": s.timepoint, "total_stages": N_STAGES,
            "server_time": iso_z(utcnow()), "window_start": iso_z(s.window_start),
            "window_end": iso_z(effective_end(s)), "instructions": INSTRUCTIONS}
    if s.status in ("submitted", "expired"):
        return {**base, "completed": s.stage_index, "submitted_at": iso_z(s.submitted_at)}
    if s.started_at is None:
        return {**base, "completed": 0, "can_start": True}
    form = db.get(AssessmentForm, s.form_id)
    answers = _answers(db, s)
    # Only information the student has already unlocked, with their own final answers.
    history = [{**_stage(form, i), "answer_text": answers[i].answer_text} for i in range(s.stage_index) if i in answers]
    base.update({"completed": s.stage_index, "history": history, "last_saved_at": iso_z(s.last_saved_at)})
    if s.stage_index >= N_STAGES:
        return {**base, "status": "ready_to_submit"}
    draft = _latest_draft(db, s, s.stage_index)
    return {**base, "stage": _stage(form, s.stage_index),
            "draft": {"answer_text": draft.answer_text, "saved_at": iso_z(draft.saved_at)} if draft else None}


@router.get("/my")
def my_sittings(db: Session = Depends(get_db), user: User = Depends(require_student)):
    now = utcnow()
    rows = db.query(AssessmentSitting).filter_by(student_id=user.student_id).order_by(AssessmentSitting.id).all()
    out = []
    for s in rows:
        if s.status == "voided" or now < s.window_start:
            continue  # unreleased schedules stay hidden
        expire_if_needed(db, s, now)
        # Neutral on purpose: no form title, study group or cohort.
        out.append({"id": s.id, "status": s.status, "timepoint": s.timepoint,
                    "window_start": iso_z(s.window_start), "window_end": iso_z(effective_end(s)),
                    "server_time": iso_z(now)})
    return out


@router.get("/my/{sitting_id}")
def get_my_sitting(sitting_id: int, db: Session = Depends(get_db), user: User = Depends(require_student)):
    s = own_sitting(db, sitting_id, user)
    _open(db, s, write=False)
    return _view(db, s)


@router.post("/my/{sitting_id}/start")
def start(sitting_id: int, db: Session = Depends(get_db), user: User = Depends(require_student)):
    s = own_sitting(db, sitting_id, user)
    _open(db, s, write=True)
    if s.status == "assigned":
        s.status, s.started_at = "in_progress", utcnow()
        event(db, s.id, "started", {})
        db.commit()
    elif s.status == "in_progress":
        event(db, s.id, "resumed", {"stage_index": s.stage_index})
        db.commit()
    return _view(db, s)


def _require_started(s: AssessmentSitting) -> None:
    if s.status == "submitted":
        raise fail(409, "already_submitted", "Assessment already submitted")
    if s.status != "in_progress":
        raise fail(409, "not_started", "Start the assessment first")


@router.put("/my/{sitting_id}/draft")
def save_draft(sitting_id: int, payload: DraftIn, db: Session = Depends(get_db),
               user: User = Depends(require_student)):
    s = own_sitting(db, sitting_id, user)
    _open(db, s, write=True)
    _require_started(s)
    if payload.stage_index != s.stage_index:
        raise fail(409, "wrong_stage", "Drafts can only be saved for the current stage")
    last = _latest_draft(db, s, s.stage_index)
    digest = sha256_text(payload.answer_text)
    if last is not None and last.answer_sha256 == digest:
        return {"saved_at": iso_z(last.saved_at), "unchanged": True}
    now = utcnow()
    nxt = db.query(AssessmentAnswerRevision).filter_by(sitting_id=s.id, stage_index=s.stage_index).count() + 1
    db.add(AssessmentAnswerRevision(sitting_id=s.id, stage_index=s.stage_index, revision_no=nxt, kind="draft",
                                    answer_text=payload.answer_text, answer_sha256=digest, saved_at=now))
    s.last_saved_at = now
    try:
        db.commit()
    except (IntegrityError, OperationalError):  # two tabs saving at once: the other save wins, ours is just a draft
        db.rollback()
        raise fail(409, "draft_conflict", "Draft changed elsewhere; retry") from None
    return {"saved_at": iso_z(now), "unchanged": False}


@router.post("/my/{sitting_id}/answer")
def answer(sitting_id: int, payload: AnswerIn, db: Session = Depends(get_db),
           user: User = Depends(require_student)):
    s = own_sitting(db, sitting_id, user)
    _open(db, s, write=True)
    _require_started(s)
    text = payload.answer_text.strip()
    if not text:
        raise fail(400, "empty_answer", "Answer cannot be empty")
    digest = sha256_text(text)
    if payload.stage_index > s.stage_index:
        event(db, s.id, "stage_skip_refused", {"requested": payload.stage_index, "current": s.stage_index})
        db.commit()
        raise fail(409, "stage_skip", "Earlier stages must be answered first")
    if payload.stage_index < s.stage_index:
        # Replay of a stage that is already final: identical text is a harmless retry,
        # anything else is an attempt to rewrite history.
        prior = db.query(AssessmentAnswer).filter_by(sitting_id=s.id, stage_index=payload.stage_index).one()
        if prior.answer_sha256 == digest:
            return {"completed": s.stage_index, "status": _progress(s), "idempotent": True}
        raise fail(409, "answer_immutable", "A submitted stage answer cannot be changed")
    now = utcnow()
    revisions = db.query(AssessmentAnswerRevision).filter_by(sitting_id=s.id, stage_index=s.stage_index).count()
    try:
        db.add(AssessmentAnswer(sitting_id=s.id, stage_index=s.stage_index, answer_text=text, answer_sha256=digest,
                                submitted_at=now))
        db.add(AssessmentAnswerRevision(sitting_id=s.id, stage_index=s.stage_index, revision_no=revisions + 1,
                                        kind="final", answer_text=text, answer_sha256=digest, saved_at=now))
        # Compare-and-set the progress counter: a concurrent duplicate loses here.
        moved = db.execute(update(AssessmentSitting).where(AssessmentSitting.id == s.id,
                           AssessmentSitting.stage_index == payload.stage_index, AssessmentSitting.status == "in_progress")
                           .values(stage_index=payload.stage_index + 1, last_saved_at=now)).rowcount
        if moved != 1:
            raise IntegrityError("stale stage", None, Exception("stale"))
        event(db, s.id, "stage_submitted", {"stage_index": payload.stage_index})
        db.commit()
    except (IntegrityError, OperationalError):  # lost a race (unique key or stale snapshot)
        db.rollback()
        db.refresh(s)
        prior = db.query(AssessmentAnswer).filter_by(sitting_id=s.id, stage_index=payload.stage_index).first()
        if prior is not None and prior.answer_sha256 == digest:
            return {"completed": s.stage_index, "status": _progress(s), "idempotent": True}
        raise fail(409, "answer_conflict", "Stage was already answered") from None
    db.refresh(s)
    return {"completed": s.stage_index, "status": _progress(s), "idempotent": False}


def _progress(s: AssessmentSitting) -> str:
    return "ready_to_submit" if s.stage_index >= N_STAGES else "in_progress"


@router.post("/my/{sitting_id}/submit")
def submit(sitting_id: int, db: Session = Depends(get_db), user: User = Depends(require_student)):
    s = own_sitting(db, sitting_id, user)
    if s.status == "submitted":  # repeated clicks / retries after a lost response
        return {"status": "submitted", "submitted_at": iso_z(s.submitted_at), "already_submitted": True}
    _open(db, s, write=True)
    _require_started(s)
    if s.stage_index != N_STAGES or db.query(AssessmentAnswer).filter_by(sitting_id=s.id).count() != N_STAGES:
        raise fail(409, "incomplete", "All five stages required")
    now = utcnow()
    moved = db.execute(update(AssessmentSitting).where(AssessmentSitting.id == s.id,
                       AssessmentSitting.status == "in_progress")
                       .values(status="submitted", submitted_at=now, closed_reason="submitted")).rowcount
    if moved == 1:
        event(db, s.id, "submitted", {})
    try:
        db.commit()
    except (IntegrityError, OperationalError):  # a concurrent submit won
        db.rollback()
        moved = 0
    db.refresh(s)
    if s.status != "submitted":
        raise fail(409, "submit_failed", "Submission could not be recorded; retry")
    return {"status": "submitted", "submitted_at": iso_z(s.submitted_at), "already_submitted": moved != 1}


@router.post("/my/{sitting_id}/interruption")
def report_interruption(sitting_id: int, payload: InterruptionIn, db: Session = Depends(get_db),
                        user: User = Depends(require_student)):
    """Student self-report (e.g. network loss). Recorded for the study admin; changes no state."""
    s = own_sitting(db, sitting_id, user)
    if utcnow() < s.window_start:
        raise fail(403, "window_not_open", "Assessment window has not opened")
    event(db, s.id, "interruption_reported", {"reason": payload.reason, "stage_index": s.stage_index})
    db.commit()
    return {"status": "recorded"}
