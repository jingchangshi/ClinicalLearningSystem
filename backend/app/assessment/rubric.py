"""Rubric weights and disagreement rules come from the (approved) form, not from code.

The six study dimensions and their *default* weights below are a proposal that is
still waiting for two real teachers to confirm it. They are used only to fill a
form whose author supplied none, and the form says so (``weights_source``). The
Training scorer's 20/20/20/15/15/10 weights are a different instrument and are
deliberately not referenced here.
"""
import math
from typing import Any

ABILITIES = ("medical_knowledge", "key_information", "differential_diagnosis",
             "evidence_integration", "clinical_decision", "evidence_based_medicine")
STUDY_DEFAULT_WEIGHTS = {"medical_knowledge": 10, "key_information": 20, "differential_diagnosis": 25,
                         "evidence_integration": 15, "clinical_decision": 20, "evidence_based_medicine": 10}
DEFAULT_RUBRIC_VERSION = "STUDY-RUBRIC-DEFAULT-PENDING-TEACHER-CONFIRMATION"
# Placeholder thresholds (points on the 0-100 scale); the real values must be set by teachers.
DEFAULT_DISAGREEMENT = {"total_threshold": 10.0, "dimension_threshold": 20.0}
PENDING_NOTE = "pending teacher confirmation"


class RubricError(ValueError):
    pass


def _num(value: Any, what: str) -> float:
    """A finite number; integral values stay ints so re-normalising a stored rubric is a no-op."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise RubricError(f"{what} must be a finite number")
    return int(value) if float(value).is_integer() else float(value)


def validate_weights(weights: Any) -> dict[str, float]:
    if not isinstance(weights, dict) or set(weights) != set(ABILITIES):
        raise RubricError("weights must contain exactly the six study dimensions")
    clean = {k: _num(weights[k], f"weight[{k}]") for k in ABILITIES}
    if any(v < 0 for v in clean.values()):
        raise RubricError("weights cannot be negative")
    if abs(sum(clean.values()) - 100.0) > 1e-6:
        raise RubricError("weights must sum to 100")
    return clean


def normalize_rubric(raw: dict | None) -> dict:
    """Return the rubric as stored: explicit weights, version, thresholds, provenance labels."""
    rubric = dict(raw or {})
    if "weights" in rubric:
        rubric["weights"] = validate_weights(rubric["weights"])
        rubric.setdefault("weights_source", "supplied")
    else:
        rubric["weights"] = dict(STUDY_DEFAULT_WEIGHTS)
        rubric["weights_source"] = "study_default"
    rubric["weights_note"] = PENDING_NOTE
    version = rubric.get("rubric_version")
    if version is None:
        rubric["rubric_version"] = DEFAULT_RUBRIC_VERSION
    elif not isinstance(version, str) or not 1 <= len(version) <= 80:
        raise RubricError("rubric_version must be a string of 1-80 characters")
    disagreement = dict(rubric.get("disagreement") or {})
    total = _num(disagreement.get("total_threshold", DEFAULT_DISAGREEMENT["total_threshold"]), "total_threshold")
    dim_raw = disagreement.get("dimension_threshold", DEFAULT_DISAGREEMENT["dimension_threshold"])
    dim = None if dim_raw is None else _num(dim_raw, "dimension_threshold")
    if total < 0 or (dim is not None and dim < 0):
        raise RubricError("thresholds cannot be negative")
    rubric["disagreement"] = {"total_threshold": total, "dimension_threshold": dim,
                              "note": PENDING_NOTE}
    return rubric


def validate_scores(scores: dict[str, Any]) -> dict[str, float]:
    if not isinstance(scores, dict) or set(scores) != set(ABILITIES):
        raise RubricError("Exactly six dimension scores required")
    clean = {k: _num(scores[k], f"score[{k}]") for k in ABILITIES}
    if any(not 0 <= v <= 100 for v in clean.values()):
        raise RubricError("Each dimension score must be within 0..100")
    return clean


def total_score(scores: dict[str, float], weights: dict[str, float]) -> float:
    return round(sum(scores[k] * weights[k] for k in ABILITIES) / sum(weights.values()), 2)


def disagreement(a: dict[str, float], b: dict[str, float], a_total: float, b_total: float,
                 rubric: dict) -> dict:
    cfg = rubric["disagreement"]
    total_diff = round(abs(a_total - b_total), 4)
    dim_diffs = {k: round(abs(a[k] - b[k]), 4) for k in ABILITIES}
    reasons = []
    if total_diff > cfg["total_threshold"]:
        reasons.append("total_diff")
    if cfg["dimension_threshold"] is not None:
        reasons += [f"dimension:{k}" for k in ABILITIES if dim_diffs[k] > cfg["dimension_threshold"]]
    return {"total_diff": total_diff, "dimension_diffs": dim_diffs, "flagged": bool(reasons),
            "reasons": reasons, "total_threshold": cfg["total_threshold"],
            "dimension_threshold": cfg["dimension_threshold"]}
