"""Cohort-level descriptive statistics for the exploratory 7-cohort study.

The analysis unit is the cohort. All functions take ``StudentScores`` records, refuse
mixed ``data_origin``, and never invent numbers when data are missing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from . import (
    DATA_ORIGIN_REAL,
    DATA_ORIGINS,
    FORM_ORDERS,
    MixedDataOriginError,
    ResearchError,
    STUDY_GROUP_CBL,
    STUDY_GROUP_CLINPATH,
)
from .order_balance import adjust_change, form_effect


@dataclass(frozen=True)
class StudentScores:
    study_student_code: str
    cohort_id: str
    form_order: str
    t0: float | None
    t1: float | None
    data_origin: str
    missing_reason: str | None = None


def assert_single_origin(rows: Iterable, *, require: str | None = None) -> str:
    """Return the one data_origin present, or refuse. ``require`` pins the expected one."""
    origins = {r.data_origin for r in rows}
    if not origins:
        raise ResearchError("no data")
    if len(origins) > 1:
        raise MixedDataOriginError(f"mixed data_origin values: {sorted(origins)}")
    (origin,) = origins
    if origin not in DATA_ORIGINS:
        raise MixedDataOriginError(f"unknown data_origin {origin!r}")
    if require and origin != require:
        raise MixedDataOriginError(f"data_origin {origin!r} not allowed; {require!r} required")
    return origin


def real_study_expected_effect(rows: Sequence[StudentScores]) -> dict:
    """Pooled mean change used to inform expectations. Real-study data only: synthetic
    demo or pilot rows are refused so a preset demo effect can never leak in."""
    assert_single_origin(rows, require=DATA_ORIGIN_REAL)
    ch = [r.t1 - r.t0 for r in rows if r.t0 is not None and r.t1 is not None]
    return {"n_paired": len(ch), "mean_change": sum(ch) / len(ch) if ch else None}


def _mean(xs: Sequence[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def per_cohort_stats(rows: Sequence[StudentScores]) -> dict[str, dict]:
    """T0/T1 means and mean change per cohort (paired students only for change)."""
    assert_single_origin(rows)
    out: dict[str, dict] = {}
    for cid in sorted({r.cohort_id for r in rows}):
        rs = [r for r in rows if r.cohort_id == cid]
        t0 = [r.t0 for r in rs if r.t0 is not None]
        t1 = [r.t1 for r in rs if r.t1 is not None]
        paired = [r for r in rs if r.t0 is not None and r.t1 is not None]
        out[cid] = {
            "n_enrolled": len(rs), "n_t0": len(t0), "n_t1": len(t1), "n_paired": len(paired),
            "mean_t0": _mean(t0), "mean_t1": _mean(t1),
            "mean_change": _mean([r.t1 - r.t0 for r in paired]),
        }
    return out


def cohort_changes(stats: Mapping[str, dict]) -> dict[str, float]:
    """Cohort-level changes; a cohort with no paired student blocks the analysis."""
    missing = [c for c, s in stats.items() if s["mean_change"] is None]
    if missing:
        raise ResearchError(f"cohorts without any paired T0/T1 student: {missing}")
    return {c: s["mean_change"] for c, s in stats.items()}


def between_arm_difference(changes: Mapping[str, float], clinpath_cohorts: Iterable[str]) -> dict:
    cp = set(clinpath_cohorts)
    a = [v for c, v in changes.items() if c in cp]
    b = [v for c, v in changes.items() if c not in cp]
    return {"n_cohorts_clinpath": len(a), "n_cohorts_cbl": len(b),
            "mean_change_clinpath": _mean(a), "mean_change_cbl": _mean(b),
            "difference": (_mean(a) - _mean(b)) if a and b else None}


def missingness(rows: Sequence[StudentScores]) -> dict:
    assert_single_origin(rows)
    n = len(rows)
    by_reason: dict[str, int] = {}
    for r in rows:
        if r.t0 is None or r.t1 is None:
            key = r.missing_reason or "unspecified"
            by_reason[key] = by_reason.get(key, 0) + 1
    return {
        "n": n, "missing_t0": sum(r.t0 is None for r in rows), "missing_t1": sum(r.t1 is None for r in rows),
        "incomplete_pairs": sum(r.t0 is None or r.t1 is None for r in rows),
        "proportion_incomplete": (sum(r.t0 is None or r.t1 is None for r in rows) / n) if n else None,
        "by_reason": by_reason,
        "per_cohort": {c: s["n_enrolled"] - s["n_paired"] for c, s in per_cohort_stats(rows).items()},
    }


def order_sensitivity(rows: Sequence[StudentScores], clinpath_cohorts: Iterable[str]) -> dict:
    """Unadjusted vs form-order-adjusted cohort-level between-arm difference."""
    assert_single_origin(rows)
    paired = [r for r in rows if r.t0 is not None and r.t1 is not None]
    by_order = {o: [r.t1 - r.t0 for r in paired if r.form_order == o] for o in FORM_ORDERS}
    effect = form_effect(by_order)
    stats = per_cohort_stats(rows)
    unadjusted = between_arm_difference(cohort_changes(stats), clinpath_cohorts)
    if effect["status"] != "ok":
        return {"form_effect": effect, "unadjusted": unadjusted, "adjusted": None}
    delta = effect["delta_hat"]
    adj: dict[str, float] = {}
    for cid in stats:
        ch = [adjust_change(r.t1 - r.t0, r.form_order, delta) for r in paired if r.cohort_id == cid]
        adj[cid] = sum(ch) / len(ch)
    return {"form_effect": effect, "unadjusted": unadjusted,
            "adjusted": between_arm_difference(adj, clinpath_cohorts), "adjusted_cohort_changes": adj}


def rate(numerator: int, denominator: int) -> dict:
    """Completion / degraded / intervention rates always carry their denominator."""
    return {"numerator": numerator, "denominator": denominator,
            "rate": (numerator / denominator) if denominator else None}


def group_label(cohort_id: str, clinpath_cohorts: Iterable[str]) -> str:
    return STUDY_GROUP_CLINPATH if cohort_id in set(clinpath_cohorts) else STUDY_GROUP_CBL
