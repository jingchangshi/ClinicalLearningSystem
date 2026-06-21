from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Case
from app.services.serializers import dumps_json, serialize_case, serialize_case_summary

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("")
def list_cases(db: Session = Depends(get_db), _user=Depends(get_current_user)) -> list[dict]:
    return [serialize_case_summary(case) for case in db.query(Case).all()]


@router.get("/{case_id}")
def get_case(case_id: int, db: Session = Depends(get_db), _user=Depends(get_current_user)) -> dict:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return serialize_case(case)


def create_case_from_payload(payload: dict, db: Session) -> Case:
    case = Case(
        title=payload["title"],
        disease_category=payload["disease_category"],
        difficulty=payload["difficulty"],
        learning_objectives=dumps_json(payload.get("learning_objectives", [])),
        chief_complaint=payload["chief_complaint"],
        history=payload["history"],
        physical_exam=payload["physical_exam"],
        lab_results=payload["lab_results"],
        imaging=payload["imaging"],
        standard_diagnosis=payload["standard_diagnosis"],
        differential_diagnosis=dumps_json(payload.get("differential_diagnosis", [])),
        treatment_plan=payload["treatment_plan"],
        rubric=dumps_json(payload.get("rubric", {})),
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def update_case_from_payload(case: Case, payload: dict, db: Session) -> Case:
    case.title = payload["title"]
    case.disease_category = payload["disease_category"]
    case.difficulty = payload["difficulty"]
    case.learning_objectives = dumps_json(payload.get("learning_objectives", []))
    case.chief_complaint = payload["chief_complaint"]
    case.history = payload["history"]
    case.physical_exam = payload["physical_exam"]
    case.lab_results = payload["lab_results"]
    case.imaging = payload["imaging"]
    case.standard_diagnosis = payload["standard_diagnosis"]
    case.differential_diagnosis = dumps_json(payload.get("differential_diagnosis", []))
    case.treatment_plan = payload["treatment_plan"]
    case.rubric = dumps_json(payload.get("rubric", {}))
    db.commit()
    db.refresh(case)
    return case
