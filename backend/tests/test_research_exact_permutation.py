"""The p-value definition test is deliberately independent of app.research: it
enumerates the 35 allocations itself with plain itertools and Fractions."""
import itertools
from fractions import Fraction

from app.research import exact_permutation as ep
from app.research import randomization as rz

COHORTS = [f"C{i}" for i in range(1, 8)]
STUDENTS = {c: [f"{c}-S{j}" for j in range(1, 8)] for c in COHORTS}
KW = dict(protocol_version="v4", executor="tester")


def brute_force_p(values, treated_idx):
    """Independent reference: p = #{|T_perm| >= |T_obs|} / 35 over all C(7,3) splits."""
    def T(tr):
        a = [values[i] for i in tr]
        b = [values[i] for i in range(7) if i not in tr]
        return Fraction(sum(a), 3) - Fraction(sum(b), 4)
    allocs = list(itertools.combinations(range(7), 3))
    assert len(allocs) == 35
    t_obs = T(treated_idx)
    return Fraction(sum(1 for a in allocs if abs(T(a)) >= abs(t_obs)), 35)


def test_one_over_35_is_attainable_with_the_goal_data():
    values = [10, 9, 8, 0, 0, 0, 0]
    assert brute_force_p(values, (0, 1, 2)) == Fraction(1, 35)
    # and the minimum over every possible observed allocation is 1/35, not 2/35
    ps = {brute_force_p(values, a) for a in itertools.combinations(range(7), 3)}
    assert min(ps) == Fraction(1, 35)


def test_p_is_never_below_one_over_35_and_min_is_data_dependent():
    # all-distinct data: each |T| is unique to its allocation up to ties; the
    # minimum is whatever the data give, never asserted a priori
    for values in ([10, 9, 8, 0, 0, 0, 0], [1, 2, 3, 4, 5, 6, 7], [0, 0, 0, 0, 0, 0, 0]):
        ps = {brute_force_p(values, a) for a in itertools.combinations(range(7), 3)}
        assert min(ps) >= Fraction(1, 35)
    assert min(brute_force_p([0] * 7, a) for a in itertools.combinations(range(7), 3)) == 1  # no information


def test_module_matches_independent_brute_force_for_every_observed_allocation():
    values = [10, 9, 8, 0, 0, 0, 0]
    changes = dict(zip(COHORTS, values))
    fo = rz.assign_form_orders(STUDENTS, seed="fo", frozen_at="2026-10-01T00:00:00", **KW)
    for i in range(60):
        rec = rz.draw_cluster_allocation(fo, cohort_ids=COHORTS, seed=f"g{i}", drawn_at="2026-10-02T00:00:00", **KW)
        res = ep.exact_randomization_test(changes, rec)
        treated = tuple(COHORTS.index(c) for c in rec.clinpath_cohorts)
        assert Fraction(res.count_ge, 35) == brute_force_p(values, treated)
        assert res.p_two_sided == res.count_ge / 35
        assert res.n_allocations == 35 and len(res.null_distribution) == 35
    # data-specific minimum reported by the module
    assert res.min_attainable_p == 1 / 35


def test_observed_allocation_is_always_counted():
    changes = {c: float(i) for i, c in enumerate(COHORTS)}
    fo = rz.assign_form_orders(STUDENTS, seed="fo", frozen_at="2026-10-01T00:00:00", **KW)
    rec = rz.draw_cluster_allocation(fo, cohort_ids=COHORTS, seed="x", drawn_at="2026-10-02T00:00:00", **KW)
    assert ep.exact_randomization_test(changes, rec).p_two_sided >= 1 / 35


def test_requires_cohort_coverage():
    import pytest
    fo = rz.assign_form_orders(STUDENTS, seed="fo", frozen_at="2026-10-01T00:00:00", **KW)
    rec = rz.draw_cluster_allocation(fo, cohort_ids=COHORTS, seed="x", drawn_at="2026-10-02T00:00:00", **KW)
    with pytest.raises(ep.ResearchError):
        ep.exact_randomization_test({c: 1.0 for c in COHORTS[:6]}, rec)
