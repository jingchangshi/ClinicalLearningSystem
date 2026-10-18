import pytest

from app.research import DATA_ORIGIN_DEMO, DATA_ORIGIN_REAL, MixedDataOriginError, ResearchError
from app.research import cohort_stats as cs
from app.research import dataset_export as de
from app.research.agreement import icc_two_way_random

SHROUT_FLEISS = [[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8], [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]]


def test_icc_matches_published_reference():
    r = icc_two_way_random(SHROUT_FLEISS, min_subjects=3)
    assert r["status"] == "ok"
    assert r["icc_2_1"] == pytest.approx(0.2898, abs=1e-3)
    assert r["icc_2_k"] == pytest.approx(0.6200, abs=1e-3)
    assert r["ci_2_1"] == pytest.approx((0.02, 0.76), abs=0.01)
    assert r["ci_2_k"] == pytest.approx((0.07, 0.93), abs=0.01)


def test_icc_insufficient_data_has_no_numbers():
    r = icc_two_way_random(SHROUT_FLEISS)  # 6 < default minimum
    assert r["status"] == "insufficient_data" and r["icc_2_1"] is None and r["ci_2_1"] is None
    assert icc_two_way_random([])["status"] == "insufficient_data"
    r = icc_two_way_random([[1, None]] * 20)
    assert r["status"] == "insufficient_data" and r["n_dropped_incomplete"] == 20


def test_icc_degenerate_and_perfect():
    assert icc_two_way_random([[5, 5]] * 12)["status"] == "degenerate"
    perfect = icc_two_way_random([[i, i] for i in range(12)])
    assert perfect["icc_2_1"] == pytest.approx(1.0)


def rows(origin=DATA_ORIGIN_REAL, drop_t1=()):
    out = []
    for ci in range(1, 8):
        for j in range(1, 8):
            code = f"C{ci}-S{j}"
            order = "X" if j <= 4 else "Y"
            t0 = 50.0 + j
            t1 = None if code in drop_t1 else t0 + (10 if ci <= 3 else 4) + (2 if order == "X" else -2)
            out.append(cs.StudentScores(code, f"C{ci}", order, t0, t1, origin,
                                        "absent" if t1 is None else None))
    return out


def test_cohort_stats_and_between_arm():
    st = cs.per_cohort_stats(rows())
    assert len(st) == 7 and st["C1"]["n_paired"] == 7
    ch = cs.cohort_changes(st)
    d = cs.between_arm_difference(ch, ["C1", "C2", "C3"])
    assert d["difference"] == pytest.approx(6.0 + (4 * 2 - 3 * 2) / 7 - (4 * 2 - 3 * 2) / 7)


def test_order_sensitivity_removes_form_effect():
    s = cs.order_sensitivity(rows(), ["C1", "C2", "C3"])
    assert s["form_effect"]["status"] == "ok" and s["form_effect"]["delta_hat"] == pytest.approx(2.0)
    assert s["adjusted"]["difference"] == pytest.approx(6.0)


def test_missingness_and_blocking():
    r = rows(drop_t1={"C1-S1", "C1-S2"})
    m = cs.missingness(r)
    assert m["missing_t1"] == 2 and m["by_reason"] == {"absent": 2} and m["per_cohort"]["C1"] == 2
    all_missing = rows(drop_t1={f"C1-S{j}" for j in range(1, 8)})
    with pytest.raises(ResearchError):
        cs.cohort_changes(cs.per_cohort_stats(all_missing))


def test_mixed_and_demo_origin_refused():
    with pytest.raises(MixedDataOriginError):
        cs.per_cohort_stats(rows() + rows(DATA_ORIGIN_DEMO))
    with pytest.raises(MixedDataOriginError):
        cs.real_study_expected_effect(rows(DATA_ORIGIN_DEMO))
    assert cs.real_study_expected_effect(rows())["n_paired"] == 49


def long_rows(origin=DATA_ORIGIN_REAL):
    out = []
    for s in rows(origin):
        for tp, score in (("T0", s.t0), ("T1", s.t1)):
            form = {"X": {"T0": "A01", "T1": "A02"}, "Y": {"T0": "A02", "T1": "A01"}}[s.form_order][tp]
            out.append(dict(study_student_code=s.study_student_code, cohort_id=s.cohort_id,
                            batch_index=int(s.cohort_id[1:]), study_group="clinpath", randomization_version="r1", timepoint=tp,
                            assessment_form_id=form, assessment_form_version="1", form_order=s.form_order,
                            final_score=score, missingness=None if score is not None else "absent",
                            data_origin=origin))
    return out


def test_dataset_freeze_is_reproducible_and_hash_detects_change():
    text, man = de.freeze(long_rows(), dataset_version="ds-1", data_origin=DATA_ORIGIN_REAL)
    text2, man2 = de.freeze(list(reversed(long_rows())), dataset_version="ds-1", data_origin=DATA_ORIGIN_REAL)
    assert text == text2 and man == man2 and man.row_count == 98
    assert text.splitlines()[0].split(",") == list(de.COLUMNS)
    assert de.verify_frozen(text, man)
    assert not de.verify_frozen(text.replace("observed", "absent", 1), man)


def test_dataset_rules():
    with pytest.raises(MixedDataOriginError):
        de.build_rows(long_rows(DATA_ORIGIN_DEMO), dataset_version="v", data_origin=DATA_ORIGIN_REAL)
    bad = long_rows()
    bad[0]["assessment_form_id"] = "A02" if bad[0]["assessment_form_id"] == "A01" else "A01"
    with pytest.raises(ResearchError):
        de.build_rows(bad, dataset_version="v", data_origin=DATA_ORIGIN_REAL)
    bad = long_rows()
    bad[1]["final_score"], bad[1]["missingness"] = None, None
    with pytest.raises(ResearchError):
        de.build_rows(bad, dataset_version="v", data_origin=DATA_ORIGIN_REAL)
    with pytest.raises(ResearchError):
        de.build_rows(long_rows() + long_rows()[:1], dataset_version="v", data_origin=DATA_ORIGIN_REAL)


def test_data_dictionary_lists_exactly_the_export_columns():
    from pathlib import Path
    doc = Path(__file__).resolve().parents[2] / "docs/teaching_grant_2026/workpackages/DATA_DICTIONARY.md"
    documented = [line.split("`")[1] for line in doc.read_text(encoding="utf-8").splitlines()
                  if line.startswith("| `")]
    assert documented == list(de.COLUMNS)


def test_batch_exposure_sensitivity_recovers_batch_trend():
    cp = ["C2", "C4", "C6"]
    idx = {f"C{i}": i for i in range(1, 8)}
    data = []
    for r in rows():
        b = idx[r.cohort_id]
        bump = 1.5 * b + (5.0 if r.cohort_id in cp else 0.0)  # later batches gain more
        data.append(cs.StudentScores(r.study_student_code, r.cohort_id, r.form_order, r.t0, r.t0 + bump,
                                     r.data_origin))
    s = cs.batch_exposure_sensitivity(data, idx, cp)
    assert s["per_cohort"]["C1"]["n_prior_informants_nominal"] == 0
    assert s["per_cohort"]["C7"]["n_prior_informants_nominal"] == 42
    assert s["per_cohort"]["C7"]["n_prior_informants_actual"] == 42
    assert s["per_cohort"]["C1"]["mean_same_form_peers"] == pytest.approx((4 * 3 + 3 * 2) / 7)
    assert s["batch_trend_adjusted_difference"]["batch_slope"] == pytest.approx(1.5)
    assert s["batch_trend_adjusted_difference"]["arm_effect"] == pytest.approx(5.0)
    assert s["r_batch_index_vs_change_within_arm"] == pytest.approx(1.0)
    assert "p_value" not in s


def test_batch_exposure_guards():
    idx = {f"C{i}": i for i in range(1, 8)}
    with pytest.raises(ResearchError):
        cs.batch_exposure_sensitivity(rows(), {**idx, "C7": 3}, ["C1", "C2", "C3"])
    with pytest.raises(MixedDataOriginError):
        cs.batch_exposure_sensitivity(rows() + rows(DATA_ORIGIN_DEMO), idx, ["C1", "C2", "C3"])


def test_batch_index_required_and_cbl_topics_reported():
    bad = long_rows()
    bad[0]["batch_index"] = None
    with pytest.raises(ResearchError):
        de.build_rows(bad, dataset_version="v", data_origin=DATA_ORIGIN_REAL)
    ok = long_rows()
    for r in ok:
        r["study_group"] = "cbl"
    first = ok[0]["study_student_code"]
    for r in ok:
        if r["study_student_code"] == first:
            r["cbl_case_topics"] = "SLE;RA"
    missing = de.cbl_rows_missing_topics(ok)
    assert first not in missing and len(missing) == 48
