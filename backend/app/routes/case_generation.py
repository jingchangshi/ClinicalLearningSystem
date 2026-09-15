from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import require_role
from app.core.ai_audit import ai_invocation
from app.core.deidentify import scan_case_payload
from app.core.rate_limit import client_identity, enforce
from app.database import get_db
from app.models import Case, GeneratedCaseDraft
from app.services.case_generator import generate_case_payload, validate_case_payload
from app.services.serializers import dumps_json, loads_json, serialize_case

router = APIRouter(
    prefix="/api/teacher/case-generator",
    tags=["case-generator"],
    dependencies=[Depends(require_role(["teacher"]))],
)


class CaseGenerateRequest(BaseModel):
    disease_category: str
    difficulty: str
    teaching_goal: str
    required_elements: list[str]
    target_abilities: list[str]


class CaseApproveRequest(BaseModel):
    generated_payload: dict | None = None


@router.post("/generate")
def generate_case(payload: CaseGenerateRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    enforce("case_generate", client_identity(request))
    prompt_report = scan_case_payload(
        {"teaching_goal": payload.teaching_goal, "disease_category": payload.disease_category,
         "required_elements": payload.required_elements},
        fields=("teaching_goal", "disease_category"),
    )
    with ai_invocation("case_generation", evidence_ref=f"disease:{payload.disease_category}"):
        generated_payload = generate_case_payload(payload.model_dump())
    draft = GeneratedCaseDraft(
        teacher_prompt=dumps_json(payload.model_dump()),
        generated_payload=dumps_json(generated_payload),
        status="draft",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return {
        "draft_id": draft.id,
        "generated_payload": generated_payload,
        "deidentification": prompt_report,
    }


@router.post("/{draft_id}/approve")
def approve_case_draft(
    draft_id: int,
    payload: CaseApproveRequest | None = None,
    db: Session = Depends(get_db),
) -> dict:
    draft = db.get(GeneratedCaseDraft, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Case draft not found")
    if draft.status == "approved":
        raise HTTPException(status_code=400, detail="Case draft already approved")

    candidate = payload.generated_payload if payload and payload.generated_payload else loads_json(draft.generated_payload, {})
    try:
        validated = validate_case_payload(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    case = Case(
        title=validated["title"],
        disease_category=validated["disease_category"],
        difficulty=validated["difficulty"],
        learning_objectives=dumps_json(validated["learning_objectives"]),
        chief_complaint=validated["chief_complaint"],
        history=validated["history"],
        physical_exam=validated["physical_exam"],
        lab_results=validated["lab_results"],
        imaging=validated["imaging"],
        standard_diagnosis=validated["standard_diagnosis"],
        differential_diagnosis=dumps_json(validated["differential_diagnosis"]),
        treatment_plan=validated["treatment_plan"],
        rubric=dumps_json(validated["rubric"]),
    )
    db.add(case)
    draft.generated_payload = dumps_json(validated)
    draft.status = "approved"
    db.commit()
    db.refresh(case)
    return {
        "draft_id": draft.id,
        "status": draft.status,
        "case": serialize_case(case),
    }
