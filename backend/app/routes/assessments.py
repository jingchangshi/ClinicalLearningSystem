"""Independent online assessment API (``/api/assessments``).

Assembles the sub-routers in ``app.assessment``. This router NEVER calls the
Training scoring, tutor, LLM, competency or recommendation services.
"""
from fastapi import APIRouter

from app.assessment import admin, dataset, design, forms, rating, student

router = APIRouter(prefix="/api/assessments", tags=["independent-assessments"])
# Static admin paths first so "/forms/admin/all" is not captured by "/forms/{form_id}".
router.include_router(forms.router)
router.include_router(student.router)
router.include_router(rating.router)
router.include_router(admin.router)
router.include_router(design.router)
router.include_router(dataset.router)
# Compatibility alias for the first-generation scheduling path.
router.add_api_route("/sittings", admin.assign, methods=["POST"], include_in_schema=False)
