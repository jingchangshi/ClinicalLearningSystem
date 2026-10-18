"""Canonical JSON, hashing and the assessment audit trail."""
import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.assessment_models import AssessmentAuditLog, AssessmentEvent
from app.models import User


def canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audit(db: Session, actor: User, action: str, target_type: str, target_id: object,
          detail: dict | None = None) -> None:
    """Stage an audit row in the caller's transaction (commit together with the action).

    ``detail`` holds ids, counts and reasons — never answer or reference-answer bodies.
    """
    db.add(AssessmentAuditLog(actor_user_id=actor.id, actor_role=actor.role, action=action,
                              target_type=target_type, target_id=str(target_id),
                              detail_json=canon(detail or {})))


def event(db: Session, sitting_id: int, event_type: str, detail: dict | None = None) -> None:
    db.add(AssessmentEvent(sitting_id=sitting_id, event_type=event_type, detail_json=canon(detail or {})))
