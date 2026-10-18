"""Exact cluster-level randomization test over the 35 whole-cohort allocations.

Pre-fixed definitions (the SAP states the same, and only, ones):

* unit: the cohort. ``cohort_change`` = mean over the cohort's paired students of
  (T1 - T0) on the common scale; 7 values in total.
* statistic: T(a) = mean(change of the 3 ClinPath cohorts in allocation a)
              - mean(change of the 4 CBL cohorts in a).
* reference set: all C(7,3) = 35 allocations, equiprobable.
* two-sided p = #{ allocations a : |T(a)| >= |T_obs| } / 35.   (>= includes the
  observed allocation itself, so p >= 1/35.)

Because the arms are unequal (3 vs 4), T(complement of a) != -T(a), so the null
distribution is generally NOT symmetric and the minimum attainable p is NOT
unconditionally 2/35: it is 1/35 when the observed allocation is the unique extreme
one. p can be < 0.05 only in that case. The test is exploratory; 7 clusters never
support a confirmatory superiority claim.

Arithmetic is exact (``fractions.Fraction`` built from the decimal repr of inputs).
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from . import MODE_RANDOMIZED, QuasiExperimentalError, ResearchError
from .randomization import N_ALLOCATIONS, N_CLINPATH, N_COHORTS, AllocationRecord, verify_allocation_record

P_VALUE_DEFINITION = "two_sided_ge_abs_count_over_35"


def _frac(x) -> Fraction:
    return x if isinstance(x, Fraction) else Fraction(str(x))


def statistic(changes: Mapping[str, Fraction], clinpath: frozenset[str] | set[str]) -> Fraction:
    treated = [v for k, v in changes.items() if k in clinpath]
    control = [v for k, v in changes.items() if k not in clinpath]
    return sum(treated) / len(treated) - sum(control) / len(control)


@dataclass(frozen=True)
class ExactTestResult:
    p_definition: str
    n_allocations: int
    t_obs: float
    p_two_sided: float
    count_ge: int
    min_attainable_p: float       # for THIS data set under the stated definition
    null_distribution: tuple[float, ...]  # 35 values, allocation order
    null_summary: dict
    exploratory_note: str

    def to_dict(self) -> dict:
        return {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.__dict__.items()}


def null_distribution(changes: Mapping[str, object]) -> list[Fraction]:
    ids = sorted(changes)
    if len(ids) != N_COHORTS:
        raise ResearchError(f"exactly {N_COHORTS} cohort-level changes required, got {len(ids)}")
    fr = {k: _frac(changes[k]) for k in ids}
    return [statistic(fr, frozenset(a)) for a in itertools.combinations(ids, N_CLINPATH)]


def exact_randomization_test(changes: Mapping[str, object], allocation: AllocationRecord) -> ExactTestResult:
    """Run the test for a randomized allocation. Refuses anything else."""
    allocation = verify_allocation_record(allocation)
    if allocation.mode != MODE_RANDOMIZED:
        raise QuasiExperimentalError(
            "quasi_experimental allocation: randomization-test conclusions are not produced")
    if set(changes) != set(allocation.cohort_ids):
        raise ResearchError("cohort-level changes must cover exactly the allocation's 7 cohorts")
    fr = {k: _frac(v) for k, v in changes.items()}
    dist = null_distribution(fr)
    t_obs = statistic(fr, frozenset(allocation.clinpath_cohorts))
    count = sum(1 for t in dist if abs(t) >= abs(t_obs))
    # minimum p reachable on this data: the smallest count over any possible observed allocation
    min_count = min(sum(1 for u in dist if abs(u) >= abs(t)) for t in dist)
    ordered = sorted(float(t) for t in dist)
    return ExactTestResult(
        p_definition=P_VALUE_DEFINITION,
        n_allocations=N_ALLOCATIONS,
        t_obs=float(t_obs),
        p_two_sided=count / N_ALLOCATIONS,
        count_ge=count,
        min_attainable_p=min_count / N_ALLOCATIONS,
        null_distribution=tuple(float(t) for t in dist),
        null_summary={"min": ordered[0], "median": ordered[len(ordered) // 2], "max": ordered[-1]},
        exploratory_note="Exploratory: 7 clusters; not a confirmatory superiority test.",
    )
