"""Inter-rater agreement: ICC(2,1) and ICC(2,k) with 95% CI (two-way random, absolute).

Mean squares from a two-way ANOVA on complete subject x rater cases; CI for ICC(2,1)
by McGraw & Wong (1996) with Satterthwaite df; the ICC(2,k) CI is the Spearman-Brown
transform of the ICC(2,1) limits. When the sample is too small or degenerate the
result says so and carries NO numbers: an unreliable index is worse than none.
"""
from __future__ import annotations

import math
from typing import Sequence

MIN_SUBJECTS = 10
METHOD = "ICC(2,1)/ICC(2,k) two-way random effects, absolute agreement; McGraw & Wong 1996 CI"


def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d; d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c; c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    front = math.exp(ln_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def f_cdf(f: float, d1: float, d2: float) -> float:
    return _betainc(d1 / 2.0, d2 / 2.0, d1 * f / (d1 * f + d2)) if f > 0 else 0.0


def f_ppf(q: float, d1: float, d2: float) -> float:
    lo, hi = 0.0, 1.0
    while f_cdf(hi, d1, d2) < q:
        hi *= 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if f_cdf(mid, d1, d2) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def icc_two_way_random(ratings: Sequence[Sequence[float | None]], *, min_subjects: int = MIN_SUBJECTS,
                       alpha: float = 0.05) -> dict:
    """``ratings``: one row per subject, one column per rater. Rows with a missing
    value are dropped (complete cases); the count used is reported."""
    rows = [list(r) for r in ratings]
    k = len(rows[0]) if rows else 0
    if any(len(r) != k for r in rows):
        raise ValueError("ragged ratings matrix")
    complete = [r for r in rows if all(v is not None for v in r)]
    n = len(complete)
    base = {"method": METHOD, "n_subjects": n, "n_raters": k, "n_dropped_incomplete": len(rows) - n}

    def unavailable(status: str, reason: str) -> dict:
        return {**base, "status": status, "reason": reason, "icc_2_1": None, "icc_2_k": None,
                "ci_2_1": None, "ci_2_k": None}

    if k < 2:
        return unavailable("insufficient_data", "at least 2 raters are required")
    if n < min_subjects:
        return unavailable("insufficient_data",
                           f"{n} complete subjects < {min_subjects}; no reliability index is reported")
    grand = sum(sum(r) for r in complete) / (n * k)
    row_m = [sum(r) / k for r in complete]
    col_m = [sum(r[j] for r in complete) / n for j in range(k)]
    ssr = k * sum((m - grand) ** 2 for m in row_m)
    ssc = n * sum((m - grand) ** 2 for m in col_m)
    sst = sum((v - grand) ** 2 for r in complete for v in r)
    sse = max(sst - ssr - ssc, 0.0)
    msr, msc, mse = ssr / (n - 1), ssc / (k - 1), sse / ((n - 1) * (k - 1))
    if sst <= 1e-12:
        return unavailable("degenerate", "no variance in the ratings")
    denom1 = msr + (k - 1) * mse + k * (msc - mse) / n
    icc1 = (msr - mse) / denom1
    icck = (msr - mse) / (msr + (msc - mse) / n)
    ci1 = ci_k = None
    note = None
    if mse > 1e-12:
        f_r, f_c = msr / mse, msc / mse
        a_ = k * icc1 / (n * (1 - icc1)) if icc1 < 1 else None
        b_ = 1 + k * icc1 * (n - 1) / (n * (1 - icc1)) if icc1 < 1 else None
        if a_ is not None:
            v = (a_ * msc + b_ * mse) ** 2 / ((a_ * msc) ** 2 / (k - 1) + (b_ * mse) ** 2 / ((n - 1) * (k - 1)))
            def limit(f: float) -> float:
                return n * (msr - f * mse) / (f * (k * msc + (k * n - k - n) * mse) + n * msr)

            lo = limit(f_ppf(1 - alpha / 2, n - 1, v))
            hi = limit(f_ppf(alpha / 2, n - 1, v))
            ci1 = (max(lo, -1.0), min(hi, 1.0))
            sb = lambda r: k * r / (1 + (k - 1) * r)  # noqa: E731
            ci_k = (sb(ci1[0]), sb(ci1[1]))
    if ci1 is None:
        note = "CI not available (zero residual variance)"
    return {**base, "status": "ok", "icc_2_1": icc1, "icc_2_k": icck, "ci_2_1": ci1, "ci_2_k": ci_k,
            "ci_level": 1 - alpha, "note": note,
            "mean_abs_difference": (sum(abs(r[0] - r[1]) for r in complete) / n) if k == 2 else None}
