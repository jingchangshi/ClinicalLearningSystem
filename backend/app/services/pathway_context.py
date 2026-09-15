"""The one catalog loader the deterministic pathway pipeline runs on.

The student pathway page and the teacher learning profile must rank the same
learner gap against the same material. Both used to assemble the five module
catalogs inline — and the teacher view used a thinner guideline shape — so the
same student could be recommended different guideline work depending on who was
looking. ``load_pathway_catalog`` is now the single source for that input.
"""

from sqlalchemy.orm import Session

from app.models import Case, ClinicalSkill, GuidelineDocument, KnowledgeUnit, SPCase
from app.services.serializers import (
    serialize_case_summary,
    serialize_guideline_summary,
    serialize_knowledge_summary,
    serialize_skill_summary,
    serialize_sp_case_summary,
)


def load_pathway_catalog(db: Session) -> dict:
    return {
        "cases": [serialize_case_summary(case) for case in db.query(Case).all()],
        "knowledge_units": [serialize_knowledge_summary(unit) for unit in db.query(KnowledgeUnit).all()],
        "clinical_skills": [serialize_skill_summary(skill) for skill in db.query(ClinicalSkill).all()],
        "guidelines": [serialize_guideline_summary(row) for row in db.query(GuidelineDocument).all()],
        "sp_cases": [serialize_sp_case_summary(row) for row in db.query(SPCase).all()],
    }
