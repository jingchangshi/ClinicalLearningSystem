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


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 1e-12 or syy <= 1e-12:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sxx * syy) ** 0.5


def batch_exposure_sensitivity(
    rows: Sequence[StudentScores],
    batch_index: Mapping[str, int],
    clinpath_cohorts: Iterable[str],
) -> dict:
    """Exploratory sensitivity: later batches may hear about the forms from earlier ones.

    ``batch_index`` is the chronological position (1..7) of each cohort. Batch b has
    ``7(b-1)`` nominal earlier students who sat both forms (``n_prior_informants``
    uses the actual enrolled counts). Also reported: same-form exposure inside a
    batch (classmates with the same form order, who sat the same form at the same
    time). Everything here is descriptive, for n = 7 clusters, and gives NO p-values;
    the single randomization p definition (exact_permutation) is unaffected.
    """
    assert_single_origin(rows)
    stats = per_cohort_stats(rows)
    if set(batch_index) != set(stats):
        raise ResearchError("batch_index must cover exactly the cohorts in the data")
    if sorted(batch_index.values()) != list(range(1, len(stats) + 1)):
        raise ResearchError("batch_index must be a permutation of 1..number of cohorts")
    cp = set(clinpath_cohorts)
    changes = cohort_changes(stats)
    by_batch = sorted(stats, key=lambda c: batch_index[c])
    per_cohort: dict[str, dict] = {}
    enrolled_before = 0
    for cid in by_batch:
        b = batch_index[cid]
        paired = [r for r in rows if r.cohort_id == cid and r.t0 is not None and r.t1 is not None]
        by_order = {o: [r for r in paired if r.form_order == o] for o in FORM_ORDERS}
        peers = [len(by_order[r.form_order]) - 1 for r in paired]
        major = max(FORM_ORDERS, key=lambda o: len(by_order[o]))
        minor = [o for o in FORM_ORDERS if o != major][0]
        mean_ch = lambda rs: (sum(r.t1 - r.t0 for r in rs) / len(rs)) if rs else None  # noqa: E731
        per_cohort[cid] = {
            "batch_index": b, "study_group": group_label(cid, cp), "mean_change": changes[cid],
            "n_prior_informants_nominal": 7 * (b - 1),
            "n_prior_informants_actual": enrolled_before,
            "mean_same_form_peers": (sum(peers) / len(peers)) if peers else None,
            "change_major_form_students": mean_ch(by_order[major]),
            "change_minor_form_students": mean_ch(by_order[minor]),
        }
        enrolled_before += stats[cid]["n_enrolled"]
    # arm-centred association between batch position (= informant count) and change
    arm_mean = {g: _mean([changes[c] for c in changes if (c in cp) == (g == STUDY_GROUP_CLINPATH)])
                for g in (STUDY_GROUP_CLINPATH, STUDY_GROUP_CBL)}
    xs = [float(batch_index[c]) for c in by_batch]
    resid = [changes[c] - arm_mean[group_label(c, cp)] for c in by_batch]
    mean_idx = {g: _mean([batch_index[c] for c in batch_index if (c in cp) == (g == STUDY_GROUP_CLINPATH)])
                for g in (STUDY_GROUP_CLINPATH, STUDY_GROUP_CBL)}
    trend = _trend_adjusted_difference(changes, batch_index, cp)
    return {
        "per_cohort": per_cohort,
        "mean_batch_index_by_arm": mean_idx,
        "r_batch_index_vs_change_within_arm": _pearson(xs, resid),
        "unadjusted_difference": between_arm_difference(changes, cp)["difference"],
        "batch_trend_adjusted_difference": trend,
        "note": "Exploratory, descriptive, 7 clusters; no p-values; the exact randomization p is unchanged.",
    }


def _trend_adjusted_difference(changes: Mapping[str, float], batch_index: Mapping[str, int],
                               clinpath: set[str]) -> dict:
    """OLS of cohort change on arm + batch_index (3 coefficients on 7 points)."""
    ids = sorted(changes)
    y = [changes[c] for c in ids]
    a = [1.0 if c in clinpath else 0.0 for c in ids]
    t = [float(batch_index[c]) for c in ids]
    n = len(ids)
    ma, mt, my = sum(a) / n, sum(t) / n, sum(y) / n
    saa = sum((v - ma) ** 2 for v in a); stt = sum((v - mt) ** 2 for v in t)
    sat = sum((u - ma) * (v - mt) for u, v in zip(a, t))
    say = sum((u - ma) * (v - my) for u, v in zip(a, y)); sty = sum((u - mt) * (v - my) for u, v in zip(t, y))
    det = saa * stt - sat * sat
    if n < 4 or det <= 1e-12:
        return {"status": "insufficient_data", "arm_effect": None, "batch_slope": None}
    return {"status": "ok", "arm_effect": (stt * say - sat * sty) / det,
            "batch_slope": (saa * sty - sat * say) / det}
