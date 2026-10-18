import itertools
from dataclasses import replace

import pytest

from app.research import MODE_QUASI, MODE_RANDOMIZED, QuasiExperimentalError, RandomizationOrderError, ResearchError
from app.research import randomization as rz
from app.research.exact_permutation import exact_randomization_test

COHORTS = [f"C{i}" for i in range(1, 8)]
STUDENTS = {c: [f"{c}-S{j}" for j in range(1, 8)] for c in COHORTS}
KW = dict(protocol_version="v4", executor="tester")


def form_order(seed="fo-seed", at="2026-10-01T09:00:00"):
    return rz.assign_form_orders(STUDENTS, seed=seed, frozen_at=at, **KW)


def draw(fo=None, seed="grp-seed", at="2026-10-02T09:00:00"):
    return rz.draw_cluster_allocation(fo or form_order(), cohort_ids=COHORTS, seed=seed, drawn_at=at, **KW)


def test_form_order_balanced_4_3_and_reproducible():
    fo = form_order()
    for counts in rz.form_order_balance(fo).values():
        assert sorted(counts.values()) == [3, 4]
    assert fo == form_order()
    assert fo != form_order(seed="other")
    rz.verify_form_order_record(fo)


def test_form_order_tamper_detected():
    fo = form_order()
    flipped = tuple((c, k, "Y" if o == "X" else "X") if i == 0 else (c, k, o)
                    for i, (c, k, o) in enumerate(fo.assignments))
    with pytest.raises(RandomizationOrderError):
        rz.verify_form_order_record(replace(fo, assignments=flipped))


def test_allocation_is_3_plus_4_reproducible_and_immutable():
    rec = draw()
    assert rec.mode == MODE_RANDOMIZED and len(rec.clinpath_cohorts) == 3 and len(rec.cbl_cohorts) == 4
    assert rec == draw()
    assert rec.executor == "tester" and rec.seed == "grp-seed" and rec.algorithm and rec.drawn_at
    with pytest.raises(Exception):
        rec.seed = "x"
    rz.verify_allocation_record(rec, form_order())
    rz.verify_allocation_record(rec.to_dict())


def test_35_allocations_each_reachable_and_roughly_uniform():
    assert len(rz.all_allocations(COHORTS)) == 35
    fo = form_order()
    seen = {}
    for i in range(3500):
        r = draw(fo, seed=f"s{i}")
        seen[r.allocation_index] = seen.get(r.allocation_index, 0) + 1
    assert len(seen) == 35
    assert min(seen.values()) > 50 and max(seen.values()) < 160  # expected 100


def test_tampered_or_forged_allocation_rejected():
    rec = draw()
    other = next(a for a in rz.all_allocations(COHORTS) if a != rec.clinpath_cohorts)
    forged = replace(rec, clinpath_cohorts=other,
                     cbl_cohorts=tuple(c for c in COHORTS if c not in other))
    with pytest.raises(ResearchError):
        rz.verify_allocation_record(forged)  # content hash
    with pytest.raises(ResearchError):
        rz.verify_allocation_record(replace(rec, executor="someone else"))


def test_form_order_must_be_frozen_before_draw():
    fo = form_order(at="2026-10-02T09:00:00")
    with pytest.raises(RandomizationOrderError):
        draw(fo, at="2026-10-02T09:00:00")  # same instant is not "before"
    with pytest.raises(RandomizationOrderError):
        draw(fo, at="2026-10-01T00:00:00")
    with pytest.raises(RandomizationOrderError):
        draw("not-a-record")
    with pytest.raises(RandomizationOrderError):
        draw(form_order(seed="grp-seed"), seed="grp-seed")  # must be a separate process


def test_draw_requires_form_order_for_same_cohorts():
    fo = rz.assign_form_orders({c: STUDENTS[c] for c in COHORTS}, seed="a", frozen_at="2026-10-01T00:00:00", **KW)
    other_ids = COHORTS[:-1] + ["C9"]
    with pytest.raises(RandomizationOrderError):
        rz.draw_cluster_allocation(fo, cohort_ids=other_ids, seed="b", drawn_at="2026-10-02T00:00:00", **KW)


def test_allocation_bound_to_its_form_order():
    rec = draw()
    with pytest.raises(RandomizationOrderError):
        rz.verify_allocation_record(rec, form_order(seed="different"))


def test_quasi_experimental_is_recorded_but_refuses_randomization_test():
    q = rz.record_quasi_experimental_allocation(
        form_order(), clinpath_cohorts=COHORTS[:3], cohort_ids=COHORTS, assigned_at="2026-10-02T09:00:00", **KW)
    assert q.mode == MODE_QUASI and q.seed is None
    rz.verify_allocation_record(q)
    with pytest.raises(QuasiExperimentalError):
        exact_randomization_test({c: float(i) for i, c in enumerate(COHORTS)}, q)


def test_requires_exactly_seven_cohorts():
    with pytest.raises(ResearchError):
        rz.assign_form_orders({c: STUDENTS[c] for c in COHORTS[:6]}, seed="a", frozen_at="2026-10-01T00:00:00", **KW)


def test_no_redraw_api():
    public = {n for n in dir(rz) if not n.startswith("_")}
    assert not {n for n in public if "redraw" in n.lower() or "reroll" in n.lower()}
