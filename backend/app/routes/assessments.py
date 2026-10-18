"""Controlled independent testing, double-blind review, and admin-only research export.

This router NEVER calls the training scoring, competency, or recommendation services.
"""
import json
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import Student, User
from app.assessment_models import AssessmentForm, AssessmentSitting, AssessmentAnswer, AssessmentReview, AssessmentFormReview

router = APIRouter(prefix="/api/assessments", tags=["independent-assessments"])
ABILITIES = ("medical_knowledge", "key_information", "differential_diagnosis",
             "evidence_integration", "clinical_decision", "evidence_based_medicine")
WEIGHTS = (10, 20, 25, 15, 20, 10)

class FormIn(BaseModel):
    code: str = Field(min_length=2, max_length=60)
    title: str = Field(min_length=2, max_length=200)
    stages: list[dict]
    answer_key: dict
    rubric: dict

class SittingIn(BaseModel):
    student_id: int
    form_id: int
    cohort_code: str = Field(min_length=1)
    study_group: str
    timepoint: str
    window_start: datetime
    window_end: datetime
    rater_a_id: int
    rater_b_id: int

class AnswerIn(BaseModel):
    answer_text: str = Field(min_length=1, max_length=16000)

class FormReviewIn(BaseModel):
    decision: str
    comment: str = Field(min_length=2)

class ReviewIn(BaseModel):
    scores: dict[str, float]

def _load(value: str):
    return json.loads(value)

def _visible_stage(form: AssessmentForm, index: int) -> dict:
    stage = _load(form.stages_json)[index]
    return {"index": index, "title": stage["title"], "clinical_information": stage["clinical_information"],
            "question": stage["question"]}

def _valid_form(form: AssessmentForm):
    if form.review_status != "APPROVED_FOR_ASSESSMENT":
        raise HTTPException(409, "Independent assessment form not approved")

def _student_sitting(db: Session, sitting_id: int, user: User) -> AssessmentSitting:
    sitting = db.get(AssessmentSitting, sitting_id)
    if sitting is None:
        raise HTTPException(404, "Sitting not found")
    if user.role != "student" or user.student_id != sitting.student_id:
        raise HTTPException(403, "Not your assessment")
    return sitting

def _in_window(sitting: AssessmentSitting):
    now = datetime.utcnow()
    if now < sitting.window_start or now >= sitting.window_end:
        raise HTTPException(403, "Assessment window is closed")
    if sitting.status == "submitted":
        raise HTTPException(409, "Assessment already submitted")

@router.post("/forms", dependencies=[Depends(require_role(["admin"]))])
def create_form(payload: FormIn, db: Session = Depends(get_db)):
    if len(payload.stages) != 5 or any(not all(k in s and s[k] for k in ("title", "clinical_information", "question")) for s in payload.stages):
        raise HTTPException(400, "Exactly five complete stages are required")
    if db.query(AssessmentForm).filter_by(code=payload.code).first():
        raise HTTPException(409, "Form code already exists")
    form = AssessmentForm(code=payload.code, title=payload.title, stages_json=json.dumps(payload.stages, ensure_ascii=False),
                          key_json=json.dumps(payload.answer_key, ensure_ascii=False),
                          rubric_json=json.dumps(payload.rubric, ensure_ascii=False))
    db.add(form); db.commit(); db.refresh(form)
    return {"id": form.id, "code": form.code, "review_status": form.review_status}

@router.post("/forms/{form_id}/review", dependencies=[Depends(require_role(["teacher"]))])
def review_form(form_id: int, payload: FormReviewIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    form = db.get(AssessmentForm, form_id)
    if form is None: raise HTTPException(404, "Form not found")
    if user.role != "teacher": raise HTTPException(403, "Independent teacher account required")
    if payload.decision not in ("approve", "reject"): raise HTTPException(400, "Invalid decision")
    if form.review_status == "APPROVED_FOR_ASSESSMENT":raise HTTPException(409,"Approved form is frozen")
    if db.query(AssessmentFormReview).filter_by(form_id=form_id,teacher_user_id=user.id).first():
        raise HTTPException(409, "Teacher already reviewed")
    db.add(AssessmentFormReview(form_id=form_id,teacher_user_id=user.id,decision=payload.decision,comment=payload.comment))
    db.commit()
    return {"status":"recorded"}

@router.get("/forms/{form_id}/admin", dependencies=[Depends(require_role(["admin"]))])
def form_review_status(form_id:int,db:Session=Depends(get_db)):
    form=db.get(AssessmentForm,form_id)
    if not form:raise HTTPException(404,"Form not found")
    reviews=db.query(AssessmentFormReview).filter_by(form_id=form_id).all()
    return {"review_status":form.review_status,"reviews":[{"teacher_user_id":r.teacher_user_id,"decision":r.decision,"comment":r.comment} for r in reviews]}

@router.post("/forms/{form_id}/approve", dependencies=[Depends(require_role(["admin"]))])
def approve_form(form_id: int, db: Session = Depends(get_db)):
    form = db.get(AssessmentForm, form_id)
    if form is None: raise HTTPException(404, "Form not found")
    reviews=db.query(AssessmentFormReview).filter_by(form_id=form_id).all()
    if len(reviews)<2 or any(r.decision!="approve" for r in reviews):
        raise HTTPException(409, "Two distinct teacher approvals required")
    form.review_status = "APPROVED_FOR_ASSESSMENT"
    db.commit()
    return {"id": form.id, "review_status": form.review_status}

@router.post("/sittings", dependencies=[Depends(require_role(["admin"]))])
def assign(payload: SittingIn, db: Session = Depends(get_db)):
    if payload.rater_a_id==payload.rater_b_id:
        raise HTTPException(400,"Two different raters required")
    raters=[db.get(User,payload.rater_a_id),db.get(User,payload.rater_b_id)]
    if any(r is None or r.role!="teacher" for r in raters):
        raise HTTPException(400,"Both raters must be teacher users")
    if payload.study_group not in ("CLINPATH", "CBL") or payload.timepoint not in ("T0", "T1"):
        raise HTTPException(400, "Invalid study group or timepoint")
    if payload.window_start >= payload.window_end:
        raise HTTPException(400, "Invalid window")
    form = db.get(AssessmentForm, payload.form_id)
    if form is None: raise HTTPException(404, "Form not found")
    _valid_form(form)
    if db.get(Student, payload.student_id) is None: raise HTTPException(404, "Student not found")
    if db.query(AssessmentSitting).filter_by(student_id=payload.student_id,timepoint=payload.timepoint).first():
        raise HTTPException(409, "Student timepoint already assigned")
    sitting = AssessmentSitting(student_id=payload.student_id,form_id=form.id,cohort_code=payload.cohort_code,
                                study_group=payload.study_group,timepoint=payload.timepoint,
                                blind_code=secrets.token_urlsafe(24),rater_a_id=payload.rater_a_id,rater_b_id=payload.rater_b_id,window_start=payload.window_start,
                                window_end=payload.window_end)
    db.add(sitting);db.commit();db.refresh(sitting)
    return {"id": sitting.id, "status": sitting.status}

@router.get("/my", dependencies=[Depends(require_role(["student"]))])
def my_sittings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = datetime.utcnow()
    sittings = db.query(AssessmentSitting).filter_by(student_id=user.student_id).all()
    # Never reveal hidden forms, group assignments, answer keys or unreleased schedules.
    return [{"id": s.id, "status": s.status} for s in sittings
            if s.window_start <= now < s.window_end or s.status == "submitted"]

@router.get("/my/{sitting_id}", dependencies=[Depends(require_role(["student"]))])
def get_my_sitting(sitting_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _student_sitting(db,sitting_id,user);_in_window(s)
    form = db.get(AssessmentForm,s.form_id);_valid_form(form)
    stages = _load(form.stages_json)
    if s.stage_index >= len(stages):
        return {"sitting_id": s.id, "status": "ready_to_submit", "completed": len(stages)}
    return {"sitting_id":s.id,"status":s.status,"completed":s.stage_index,
            "stage":_visible_stage(form,s.stage_index)}

@router.post("/my/{sitting_id}/answer", dependencies=[Depends(require_role(["student"]))])
def answer(sitting_id: int,payload: AnswerIn,db: Session=Depends(get_db),user:User=Depends(get_current_user)):
    s=_student_sitting(db,sitting_id,user);_in_window(s)
    form=db.get(AssessmentForm,s.form_id);_valid_form(form)
    if s.stage_index >= 5:raise HTTPException(409,"All stages answered")
    db.add(AssessmentAnswer(sitting_id=s.id,stage_index=s.stage_index,answer_text=payload.answer_text.strip()))
    s.stage_index+=1;s.status="in_progress";db.commit()
    return {"completed":s.stage_index,"status":"ready_to_submit" if s.stage_index==5 else "in_progress"}

@router.post("/my/{sitting_id}/submit", dependencies=[Depends(require_role(["student"]))])
def submit(sitting_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    s=_student_sitting(db,sitting_id,user);_in_window(s)
    if s.stage_index!=5 or db.query(AssessmentAnswer).filter_by(sitting_id=s.id).count()!=5:
        raise HTTPException(409,"All five stages required")
    s.status="submitted";s.submitted_at=datetime.utcnow();db.commit()
    return {"status":"submitted"}

@router.get("/blind/queue", dependencies=[Depends(require_role(["teacher"]))])
def blind_queue(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    qs=[s for s in db.query(AssessmentSitting).filter_by(status="submitted").all() if user.id in (s.rater_a_id,s.rater_b_id)]
    return [{"blind_code":s.blind_code,"reviewed":db.query(AssessmentReview).filter_by(sitting_id=s.id,rater_user_id=user.id).first() is not None}
            for s in qs]

@router.get("/blind/{blind_code}", dependencies=[Depends(require_role(["teacher"]))])
def blind_detail(blind_code:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    s=db.query(AssessmentSitting).filter_by(blind_code=blind_code,status="submitted").first()
    if s is None:raise HTTPException(404,"Submitted assessment not found")
    if user.id not in (s.rater_a_id,s.rater_b_id):raise HTTPException(403,"Not assigned as blind rater")
    form=db.get(AssessmentForm,s.form_id)
    answers=db.query(AssessmentAnswer).filter_by(sitting_id=s.id).order_by(AssessmentAnswer.stage_index).all()
    # No student identity, group, cohort or T0/T1 in this response. No other rater's scores.
    return {"blind_code":blind_code,"stages":_load(form.stages_json),
            "answers":[{"index":a.stage_index,"answer_text":a.answer_text} for a in answers],
            "rubric":_load(form.rubric_json),"answer_key":_load(form.key_json),
            "already_reviewed":db.query(AssessmentReview).filter_by(sitting_id=s.id,rater_user_id=user.id).first() is not None}

@router.post("/blind/{blind_code}/review", dependencies=[Depends(require_role(["teacher"]))])
def review(blind_code:str,payload:ReviewIn,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    s=db.query(AssessmentSitting).filter_by(blind_code=blind_code,status="submitted").first()
    if s is None:raise HTTPException(404,"Submitted assessment not found")
    if user.id not in (s.rater_a_id,s.rater_b_id):raise HTTPException(403,"Not assigned as blind rater")
    if db.query(AssessmentReview).filter_by(sitting_id=s.id,rater_user_id=user.id).first():
        raise HTTPException(409,"Review already locked")
    if set(payload.scores)!=set(ABILITIES) or any(not 0<=v<=100 for v in payload.scores.values()):
        raise HTTPException(400,"Exactly six 0..100 dimension scores required")
    total=round(sum(payload.scores[k]*w for k,w in zip(ABILITIES,WEIGHTS))/100,2)
    row=AssessmentReview(sitting_id=s.id,rater_user_id=user.id,scores_json=json.dumps(payload.scores),
                         total_score=total)
    db.add(row);db.commit()
    return {"status":"locked","total_score":total}

@router.get("/admin/export", dependencies=[Depends(require_role(["admin"]))])
def research_export(db:Session=Depends(get_db)):
    sittings=db.query(AssessmentSitting).order_by(AssessmentSitting.id).all()
    out=[]
    for s in sittings:
        reviews=db.query(AssessmentReview).filter_by(sitting_id=s.id).order_by(AssessmentReview.id).all()
        out.append({"sitting_id":s.id,"student_id":s.student_id,"cohort_code":s.cohort_code,
                    "study_group":s.study_group,"timepoint":s.timepoint,"form_id":s.form_id,
                    "blind_code":s.blind_code,"status":s.status,
                    "scores":[{"review_id":r.id,"rater_user_id":r.rater_user_id,"total_score":r.total_score,
                               "dimensions":_load(r.scores_json)} for r in reviews]})
    return {"data_origin":"REAL_ASSESSMENT_IF_CONSENTED","records":out}
