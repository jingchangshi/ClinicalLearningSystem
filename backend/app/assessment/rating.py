"""Blinded double rating and adjudication.

A rater is addressed only by an opaque blind code and is shown the form, the
student's answers (best-effort de-identified) and the rubric anchors. Student,
group, cohort, timepoint, attempt, form identity and the other rater's scores are
never part of a rater response.
"""
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.assessment.access import fail, require_teacher
from app.assessment.audit import audit, canon
from app.assessment.blinding import blind_order_key, redact_answer
from app.assessment.forms import form_rubric, load
from app.assessment.rubric import RubricError, disagreement, total_score, validate_scores
from app.assessment_models import (
    AssessmentAdjudication, AssessmentAnswer, AssessmentFinalScore, AssessmentForm, AssessmentReview, AssessmentSitting,
)
from app.database import get_db
from app.models import Student, User

router = APIRouter()


class ReviewIn(BaseModel):
    scores: dict[str, float]
    rationale: str | None = Field(default=None, max_length=4000)


class AdjudicationIn(BaseModel):
    scores: dict[str, float]
    rationale: str = Field(min_length=5, max_length=4000)


def live_reviews(db: Session, sitting_id: int) -> list[AssessmentReview]:
    return db.query(AssessmentReview).filter(AssessmentReview.sitting_id == sitting_id,
                                             AssessmentReview.voided_at.is_(None)).order_by(AssessmentReview.id).all()


def sitting_disagreement(db: Session, s: AssessmentSitting) -> dict | None:
    """Disagreement between the two live reviews under the rubric the raters used."""
    reviews = live_reviews(db, s.id)
    if len(reviews) != 2:
        return None
    rubric = form_rubric(db.get(AssessmentForm, s.form_id))
    a, b = reviews
    return disagreement(json.loads(a.scores_json), json.loads(b.scores_json), a.total_score, b.total_score, rubric)


def _assigned(db: Session, blind_code: str, user: User, *, adjudicator: bool = False) -> AssessmentSitting:
    s = db.query(AssessmentSitting).filter_by(blind_code=blind_code, status="submitted").first()
    ok = s is not None and ((user.id == s.adjudicator_user_id) if adjudicator else user.id in (s.rater_a_id, s.rater_b_id))
    if not ok:  # same answer for "does not exist" and "not yours"
        raise fail(404, "not_found", "Submitted assessment not found")
    return s


def _blind_view(db: Session, s: AssessmentSitting) -> dict:
    form = db.get(AssessmentForm, s.form_id)
    student = db.get(Student, s.student_id)
    answers = db.query(AssessmentAnswer).filter_by(sitting_id=s.id).order_by(AssessmentAnswer.stage_index).all()
    redacted = [redact_answer(a.answer_text, student) for a in answers]
    rubric = form_rubric(form)
    return {"blind_code": s.blind_code, "stages": load(form.stages_json),
            "answers": [{"index": a.stage_index, "answer_text": r[0]} for a, r in zip(answers, redacted)],
            "identifier_redactions": sum(r[1] for r in redacted),
            "rubric": rubric,
            "answer_key": load(form.key_json)}


@router.get("/blind/queue")
def blind_queue(db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    mine = [s for s in db.query(AssessmentSitting).filter_by(status="submitted").all()
            if user.id in (s.rater_a_id, s.rater_b_id)]
    mine.sort(key=lambda s: blind_order_key(user.id, s.blind_code))
    done = {r.sitting_id for r in db.query(AssessmentReview).filter(AssessmentReview.rater_user_id == user.id,
                                                                    AssessmentReview.voided_at.is_(None))}
    return [{"blind_code": s.blind_code, "reviewed": s.id in done} for s in mine]


@router.get("/blind/{blind_code}")
def blind_detail(blind_code: str, db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    s = _assigned(db, blind_code, user)
    mine = db.query(AssessmentReview).filter(AssessmentReview.sitting_id == s.id,
                                             AssessmentReview.rater_user_id == user.id,
                                             AssessmentReview.voided_at.is_(None)).first()
    return {**_blind_view(db, s), "already_reviewed": mine is not None}


@router.post("/blind/{blind_code}/review")
def review(blind_code: str, payload: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    s = _assigned(db, blind_code, user)
    rubric = form_rubric(db.get(AssessmentForm, s.form_id))
    try:
        scores = validate_scores(payload.scores)
    except RubricError as exc:
        raise fail(400, "bad_scores", str(exc)) from None
    total = total_score(scores, rubric["weights"])
    prior = db.query(AssessmentReview).filter(AssessmentReview.sitting_id == s.id,
                                              AssessmentReview.rater_user_id == user.id,
                                              AssessmentReview.voided_at.is_(None)).first()
    if prior is not None:
        # Locked. Re-sending the identical scores (double click) is harmless; anything else is refused.
        if json.loads(prior.scores_json) == scores:
            return {"status": "locked", "total_score": prior.total_score, "already_locked": True}
        raise fail(409, "review_locked", "Review already locked")
    row = AssessmentReview(sitting_id=s.id, rater_user_id=user.id, scores_json=json.dumps(scores), total_score=total,
                           rater_slot="A" if user.id == s.rater_a_id else "B", rationale=payload.rationale,
                           rubric_version=rubric["rubric_version"], weights_json=json.dumps(rubric["weights"]))
    db.add(row)
    audit(db, user, "review.submit", "sitting", s.id, {"rater_slot": row.rater_slot})
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise fail(409, "review_locked", "Review already locked") from None
    return {"status": "locked", "total_score": total, "already_locked": False}


# --- adjudication -----------------------------------------------------------

@router.get("/adjudication/queue")
def adjudication_queue(db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    out = []
    for s in db.query(AssessmentSitting).filter_by(status="submitted", adjudicator_user_id=user.id).all():
        d = sitting_disagreement(db, s)
        if d and d["flagged"]:
            decided = db.query(AssessmentAdjudication).filter_by(sitting_id=s.id).first() is not None
            out.append({"blind_code": s.blind_code, "adjudicated": decided})
    out.sort(key=lambda r: blind_order_key(user.id, r["blind_code"]))
    return out


@router.get("/adjudication/{blind_code}")
def adjudication_detail(blind_code: str, db: Session = Depends(get_db), user: User = Depends(require_teacher)):
    s = _assigned(db, blind_code, user, adjudicator=True)
    d = sitting_disagreement(db, s)
    if not d or not d["flagged"]:
        raise fail(404, "not_found", "Submitted assessment not found")
    reviews = live_reviews(db, s.id)
    # Both raw reviews are shown, anonymised as rater 1/2 in a stable (blind-code based) order.
    ordered = sorted(reviews, key=lambda r: blind_order_key(0, f"{s.blind_code}:{r.id}"))
    return {**_blind_view(db, s), "disagreement": d,
            "reviews": [{"label": f"rater_{i + 1}", "scores": json.loads(r.scores_json), "total_score": r.total_score,
                         "rationale": r.rationale} for i, r in enumerate(ordered)],
            "already_adjudicated": db.query(AssessmentAdjudication).filter_by(sitting_id=s.id).first() is not None}


@router.post("/adjudication/{blind_code}")
def adjudicate(blind_code: str, payload: AdjudicationIn, db: Session = Depends(get_db),
               user: User = Depends(require_teacher)):
    s = _assigned(db, blind_code, user, adjudicator=True)
    d = sitting_disagreement(db, s)
    if not d or not d["flagged"]:
        raise fail(409, "no_disagreement", "Only a flagged disagreement can be adjudicated")
    if db.query(AssessmentFinalScore).filter_by(sitting_id=s.id).first():
        raise fail(409, "final_locked", "Final score already locked")
    if db.query(AssessmentAdjudication).filter_by(sitting_id=s.id).first():
        raise fail(409, "already_adjudicated", "Adjudication already recorded")
    try:
        scores = validate_scores(payload.scores)
    except RubricError as exc:
        raise fail(400, "bad_scores", str(exc)) from None
    rubric = form_rubric(db.get(AssessmentForm, s.form_id))
    a, b = live_reviews(db, s.id)
    row = AssessmentAdjudication(sitting_id=s.id, adjudicator_user_id=user.id, review_a_id=a.id, review_b_id=b.id,
                                 trigger_json=canon(d), scores_json=json.dumps(scores),
                                 total_score=total_score(scores, rubric["weights"]), rationale=payload.rationale)
    db.add(row)
    audit(db, user, "adjudication.submit", "sitting", s.id, {"total_diff": d["total_diff"], "reasons": d["reasons"]})
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise fail(409, "already_adjudicated", "Adjudication already recorded") from None
    return {"status": "recorded", "total_score": row.total_score}
