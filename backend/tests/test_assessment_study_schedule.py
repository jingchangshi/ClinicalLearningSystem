"""R4.2 / R4.5 / R8.1: planning the real 7-batch, 49-student study in one atomic call.

``/design/assignments`` shows who the frozen records place in which batch, arm and
form order; ``/design/schedule`` turns those records into the 98 T0/T1 sittings.
Nothing here is a real student or teacher: the accounts come from
``tests.assessment_helpers``, the batches are test batches and no real physician
signature is involved anywhere.
"""

import json

from app.assessment_models import AssessmentSitting
from app.core import ai_audit
from app.models import CaseSession, LearningRecommendation, Score, Student, User
from app.services.llm_service import LLMService
from tests.assessment_helpers import (
    ANCHORS, SECRET_KEY, _win, build_study, build_world, design_rows, login, post_schedule, publish_form,
    schedule, seed_submitted, study_windows, stages,
)
from tests.factories import make_case
from tests.test_assessment_isolation import _training_snapshot

ORIGIN = "real_study"


def approved_forms(client, w):
    """Two published forms, each approved through the API by two different test teachers."""
    return {name: publish_form(client, w, code=f"ASSESS-{name}-TEST", tag=name[-2:]) for name in ("A01", "A02")}


def study(db_factory, client, n_students=49, freeze=True):
    """A complete 7 x 7 study: two approved forms and both frozen draws."""
    w = build_world(db_factory, n_students=n_students, student_accounts=False)
    forms = approved_forms(client, w)
    codes = build_study(client, w, freeze=freeze)
    return w, forms, codes


def sitting_tuples(db_factory):
    """student_id -> {timepoint: (form_id, form_order, study_group, cohort_code, status, data_origin)}."""
    db = db_factory()
    rows = db.query(AssessmentSitting).all()
    out = {}
    for s in rows:
        out.setdefault(s.student_id, {})[s.timepoint] = (
            s.form_id, s.form_order, s.study_group, s.cohort_code, s.status, s.data_origin)
    db.close()
    return out


def audit_actions(client):
    login(client, "admin_user")
    return [r["action"] for r in client.get("/api/assessments/admin/audit?limit=1000").json()]


def test_one_call_schedules_all_49_students_of_seven_cohorts(db_factory, client):
    w, forms, codes = study(db_factory, client)
    rows = design_rows(client)
    assert len(rows) == 49 and {r["cohort_code"] for r in rows} == set(codes)
    assert all(r["study_student_code"] for r in rows)

    r = post_schedule(client, w, forms, study_windows(codes))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 98 and body["existing"] == 0 and body["students"] == 49
    assert body["cohorts"] == {c: 7 for c in codes} and len(body["sitting_ids"]) == 98

    stored = sitting_tuples(db_factory)
    assert len(stored) == 49 and all(set(v) == {"T0", "T1"} for v in stored.values())
    assert all(t[4] == "assigned" and t[5] == ORIGIN for v in stored.values() for t in v.values())
    # A whole seven-student batch stays in one arm; the draw gives 3 ClinPath + 4 CBL batches.
    arms = {cohort: {t[2] for v in stored.values() for t in v.values() if t[3] == cohort} for cohort in codes}
    assert all(len(a) == 1 for a in arms.values()), arms
    assert sorted(next(iter(a)) for a in arms.values()) == ["CBL"] * 4 + ["CLINPATH"] * 3
    # Every sitting sits in the batch and arm its frozen record names.
    for row in rows:
        for tp in ("T0", "T1"):
            assert stored[row["student_id"]][tp][3] == row["cohort_code"]
            assert stored[row["student_id"]][tp][2] == row["study_group"]
    # The whole plan is one audited action.
    assert audit_actions(client).count("design.schedule") == 1


def test_t0_and_t1_forms_follow_each_students_frozen_order(db_factory, client):
    w, forms, codes = study(db_factory, client)
    assert post_schedule(client, w, forms, study_windows(codes)).status_code == 200

    rows = design_rows(client)
    stored = sitting_tuples(db_factory)
    want = {"X": {"T0": forms["A01"], "T1": forms["A02"]}, "Y": {"T0": forms["A02"], "T1": forms["A01"]}}
    assert {r["form_order"] for r in rows} == {"X", "Y"}  # both arms of the order really occur
    for row in rows:
        for tp in ("T0", "T1"):
            assert stored[row["student_id"]][tp][0] == want[row["form_order"]][tp], (row, tp)
    per_cohort = {}
    for row in rows:
        per_cohort.setdefault(row["cohort_code"], []).append(row["form_order"])
    for cohort, orders in per_cohort.items():
        assert sorted([orders.count("X"), orders.count("Y")]) == [3, 4], cohort  # 题本顺序 4/3


def test_a_refusal_in_the_last_batch_rolls_the_whole_plan_back(db_factory, client):
    w, forms, codes = study(db_factory, client)
    by_student = {r["student_id"]: r for r in design_rows(client)}
    victim = w.students[-1]  # the highest student id: the last target of the last batch
    v = by_student[victim]
    assert v["cohort_code"] == codes[-1]
    # The victim already holds a T0 sitting for the same form but on a different window, so the
    # planner stages six complete batches and most of the seventh before it refuses.
    already = forms["A01"] if v["form_order"] == "X" else forms["A02"]
    schedule(client, w, victim, already, cohort=v["cohort_code"], group=v["study_group"],
             data_origin=ORIGIN, start=-5, end=110)
    before_audit = audit_actions(client)

    r = post_schedule(client, w, forms, study_windows(codes))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "schedule_conflict"

    db = db_factory()
    assert db.query(AssessmentSitting).count() == 1  # only the sitting that existed before the call
    db.close()
    assert audit_actions(client) == before_audit  # no half-written sittings, no audit row


def test_an_invalid_window_in_the_last_batch_also_rolls_back(db_factory, client):
    w, forms, codes = study(db_factory, client)
    windows = study_windows(codes)
    windows[codes[-1]]["T1"] = _win(601, 600)  # a T1 window that closes before it opens
    before_audit = audit_actions(client)

    r = post_schedule(client, w, forms, windows)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_window"
    assert sitting_tuples(db_factory) == {}
    assert audit_actions(client) == before_audit


def test_a_repeat_call_creates_no_second_sitting_and_a_changed_plan_is_refused(db_factory, client):
    w, forms, codes = study(db_factory, client)
    windows = study_windows(codes)
    first = post_schedule(client, w, forms, windows)
    assert first.status_code == 200 and first.json()["created"] == 98
    ids = sorted(first.json()["sitting_ids"])

    again = post_schedule(client, w, forms, windows)
    assert again.status_code == 200, again.text
    assert again.json()["created"] == 0 and again.json()["existing"] == 98
    assert again.json()["sitting_ids"] == [] and sorted(again.json()["existing_ids"]) == ids
    assert len(sitting_tuples(db_factory)) == 49  # nothing duplicated

    changed = study_windows(codes)
    changed[codes[2]]["T1"] = _win(200, 700)  # one batch re-planned onto a different window
    conflict = post_schedule(client, w, forms, changed)
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "schedule_conflict"
    assert len(sitting_tuples(db_factory)) == 49
    assert audit_actions(client).count("design.schedule") == 2  # the refused call wrote nothing

    # Once a sitting has been sat it is never re-planned, even with identical inputs.
    seed_submitted(db_factory, ids[0])
    sat = post_schedule(client, w, forms, windows)
    assert sat.status_code == 409 and sat.json()["detail"]["code"] == "schedule_conflict"
    assert len(sitting_tuples(db_factory)) == 49


def test_nothing_is_scheduled_from_an_unapproved_unknown_or_odd_form(db_factory, client):
    w, forms, codes = study(db_factory, client)
    windows = study_windows(codes)
    login(client, "admin_user")
    draft = client.post("/api/assessments/forms", json={
        "code": "ASSESS-A02-DRAFT", "title": "保密考核草案", "stages": stages("B"),
        "answer_key": SECRET_KEY, "rubric": {"anchors": ANCHORS}})
    assert draft.status_code == 200, draft.text
    assert draft.json()["review_status"] != "APPROVED_FOR_ASSESSMENT"

    # An unapproved form is refused before the first sitting is staged.
    r = post_schedule(client, w, {"A01": forms["A01"], "A02": draft.json()["id"]}, windows)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "form_not_approved"
    assert sitting_tuples(db_factory) == {}

    r = post_schedule(client, w, {"A01": forms["A01"], "A02": 999999}, windows)
    assert r.status_code == 404 and r.json()["detail"]["code"] == "form_not_found"
    r = post_schedule(client, w, {"A01": forms["A01"], "A02": forms["A01"]}, windows)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_forms"
    r = post_schedule(client, w, {"A01": forms["A01"]}, windows)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_forms"
    assert sitting_tuples(db_factory) == {}
    actions = audit_actions(client)
    assert "design.schedule" not in actions and "sitting.create" not in actions


def test_the_planner_refuses_until_the_whole_allocation_is_frozen(db_factory, client):
    w, forms, codes = study(db_factory, client, freeze=False)
    unfrozen = design_rows(client)
    assert len(unfrozen) == 49
    assert {r["study_group"] for r in unfrozen} == {None} and {r["form_order"] for r in unfrozen} == {None}

    r = post_schedule(client, w, forms, study_windows(codes))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "allocation_required"
    assert sitting_tuples(db_factory) == {}


def test_the_planner_validates_the_origin_batches_and_windows(db_factory, client):
    w, forms, codes = study(db_factory, client)
    windows = study_windows(codes)

    r = post_schedule(client, w, forms, windows, data_origin="pilot-test")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_data_origin"
    r = post_schedule(client, w, forms, windows, data_origin="synthetic_demo")  # no batches of that origin
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_cohorts"
    r = post_schedule(client, w, forms, {**windows, "C99": windows["C1"]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_cohort"
    r = post_schedule(client, w, forms, {k: v for k, v in windows.items() if k != codes[4]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "missing_window"
    r = post_schedule(client, w, forms, {**windows, codes[0]: {"T0": windows[codes[0]]["T0"]}})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "missing_window"
    r = post_schedule(client, w, forms, study_windows(codes, t0=(300, 400), t1=(121, 600)))  # T1 opens before T0 closes
    assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_timepoint_order"
    assert sitting_tuples(db_factory) == {}
    assert "design.schedule" not in audit_actions(client)


def test_the_planner_needs_two_distinct_real_teachers_as_raters(db_factory, client):
    w, forms, codes = study(db_factory, client)
    windows = study_windows(codes)
    r = post_schedule(client, w, forms, windows, rater_b_id=w.users["rater_a"])
    assert r.status_code == 400 and r.json()["detail"]["code"] == "two_raters_required"
    r = post_schedule(client, w, forms, windows, rater_a_id=w.users["plain_teacher"],
                      adjudicator_user_id=w.users["plain_teacher"])
    assert r.status_code == 400 and r.json()["detail"]["code"] == "adjudicator_is_rater"
    r = post_schedule(client, w, forms, windows, rater_a_id=w.users["admin_user"])
    assert r.status_code == 400 and r.json()["detail"]["code"] == "not_teacher"
    assert sitting_tuples(db_factory) == {}


def test_only_a_study_administrator_may_read_the_design_or_plan_the_study(db_factory, client):
    w = build_world(db_factory, n_students=2)
    forms = approved_forms(client, w)
    body = {"data_origin": ORIGIN, "forms": forms, "windows": {}, "rater_a_id": w.users["rater_a"],
            "rater_b_id": w.users["rater_b"]}
    for who in ("plain_teacher", "rater_a", "rev_one", w.student_users[0]):
        login(client, who)
        assert client.get(f"/api/assessments/admin/design/assignments?data_origin={ORIGIN}").status_code == 403, who
        assert client.post("/api/assessments/admin/design/schedule", json=body).status_code == 403, who
    login(client, "admin_user")
    assert client.get("/api/assessments/admin/audit?action=design.read").json() == []  # refusals wrote nothing
    assert client.get(f"/api/assessments/admin/design/assignments?data_origin={ORIGIN}").status_code == 200
    assert len(client.get("/api/assessments/admin/audit?action=design.read").json()) == 1


def test_the_design_read_is_audited_and_carries_no_identity(db_factory, client):
    study(db_factory, client)
    rows = design_rows(client)
    assert len(rows) == 49
    assert all(set(r) == {"student_id", "study_student_code", "cohort_code", "enrollment_status", "study_group",
                          "form_order"} for r in rows)
    db = db_factory()
    names = {s.name for s in db.query(Student).all()} | {u.username for u in db.query(User).all()}
    db.close()
    blob = str(rows)
    assert not [n for n in names if n and n in blob]  # codes, never names or logins
    login(client, "admin_user")
    audit = client.get("/api/assessments/admin/audit?action=design.read").json()
    assert len(audit) == 1 and audit[0]["detail"] == {"rows": 49}


def test_planning_the_whole_study_touches_no_training_or_ai_state(db_factory, client, monkeypatch):
    ai_calls = []

    def forbidden(name):
        def _raise(*a, **k):
            ai_calls.append(name)
            raise AssertionError(f"study planning called AI: {name}")
        return _raise

    for name in ("chat_json", "chat_completion", "generate_case", "generate_sp_feedback", "explain_recommendation",
                 "explain_recommendation_batch", "generate_teacher_insight"):
        assert hasattr(LLMService, name), name
        monkeypatch.setattr(LLMService, name, forbidden(name))
    monkeypatch.setattr(ai_audit, "ai_invocation", forbidden("ai_invocation"))

    w = build_world(db_factory, n_students=49, student_accounts=False)
    db = db_factory()
    make_case(db)
    db.commit()
    before = _training_snapshot(db)
    db.close()

    forms = approved_forms(client, w)
    codes = build_study(client, w)
    r = post_schedule(client, w, forms, study_windows(codes))
    assert r.status_code == 200 and r.json()["created"] == 98

    db = db_factory()
    after = _training_snapshot(db)
    assert after == before  # every Training/AI table: same rows, same competency numbers
    assert db.query(Score).count() == 0 and db.query(LearningRecommendation).count() == 0
    assert db.query(CaseSession).count() == 0
    assert all(p[1:7] == (60.0,) * 6 for p in after[1])  # the factory baseline, never moved
    db.close()
    assert ai_calls == [] and ai_audit.queue_depth() == 0


def test_freezing_the_group_draw_never_rewrites_the_form_order_record(db_factory, client):
    """R4.5: the form order is frozen first and the teaching groups are a separate draw."""
    w = build_world(db_factory, n_students=49, student_accounts=False)
    login(client, "admin_user")
    build_study(client, w, freeze=False)
    r = client.post("/api/assessments/admin/allocations/form-order",
                    json={"data_origin": ORIGIN, "protocol_version": "v4", "seed": "order-seed-1"})
    assert r.status_code == 200, r.text
    order_before = stored_record(db_factory, "form_order")
    # Nothing is schedulable yet: the arm is undecided, so the design has no rows to place.
    assert {x["study_group"] for x in design_rows(client)} == {None}
    assert {x["form_order"] for x in design_rows(client)} == {None}

    r = client.post("/api/assessments/admin/allocations/cluster",
                    json={"data_origin": ORIGIN, "protocol_version": "v4", "mode": "randomized", "seed": "group-seed-1"})
    assert r.status_code == 200, r.text
    # The group draw left the frozen form-order record byte-identical: same hash, same
    # content, still exactly one row of each kind.
    assert stored_record(db_factory, "form_order") == order_before
    allocs = client.get("/api/assessments/admin/allocations").json()
    assert sorted(a["kind"] for a in allocs) == ["cluster_group", "form_order"]
    assert allocs[0]["content_hash"] != allocs[1]["content_hash"]
    # R4.2: an administrator must be able to audit the form-order draw through the API,
    # not only by opening the database: seed, frozen timestamp and per-student X/Y.
    order = next(a for a in allocs if a["kind"] == "form_order")["record"]
    assert order["seed"] == "order-seed-1"
    assert order["frozen_at"] and order["algorithm"] and order["protocol_version"] == "v4"
    assert len(order["assignments"]) == 49
    assert {entry[2] for entry in order["assignments"]} == {"X", "Y"}
    # Grouping is now decidable, and it did not disturb any student's frozen form order.
    assert {x["study_group"] for x in design_rows(client)} == {"CLINPATH", "CBL"}
    assert {x["form_order"] for x in design_rows(client)} == {"X", "Y"}


def test_the_export_of_a_planned_study_is_coded_complete_and_origin_scoped(db_factory, client):
    """R4.6: 98 coded rows, each carrying its frozen arm, form order and form version."""
    w, forms, codes = study(db_factory, client)
    assert post_schedule(client, w, forms, study_windows(codes)).status_code == 200
    login(client, "admin_user")
    export = client.get(f"/api/assessments/admin/export?data_origin={ORIGIN}").json()
    recs = export["records"]
    assert export["dataset_status"] == "WORKING_NOT_FROZEN" and len(recs) == 98

    design = {r["study_student_code"]: r for r in design_rows(client)}
    assert {r["study_student_code"] for r in recs} == set(design)  # codes only, one per student
    want = {"X": {"T0": "A01", "T1": "A02"}, "Y": {"T0": "A02", "T1": "A01"}}
    for r in recs:
        d = design[r["study_student_code"]]
        assert r["cohort_id"] == d["cohort_code"] and r["form_order"] == d["form_order"]
        assert r["study_group"] == d["study_group"].lower()
        assert r["assessment_form_id"] == forms[want[d["form_order"]][r["timepoint"]]]
        assert r["randomization_version"] and r["randomization_mode"] == "randomized"
        assert r["data_origin"] == ORIGIN
    # Nothing is invented for sittings that have not run yet.
    assert {r["missingness"] for r in recs} == {"not_submitted"}
    assert {r["blinded_rater_1_score"] for r in recs} == {None}
    assert {r["blinded_rater_2_score"] for r in recs} == {None}
    assert {r["final_score"] for r in recs} == {None} and {r["scoring_provenance"] for r in recs} == {None}
    db = db_factory()
    names = {s.name for s in db.query(Student).all()}
    db.close()
    blob = json.dumps(export, ensure_ascii=False)
    assert not [n for n in names if n and n in blob]  # no student name reaches a research export
    # Another origin exports nothing: the two studies never mix in one file.
    assert client.get("/api/assessments/admin/export?data_origin=pilot_test").json()["records"] == []


def test_real_and_synthetic_study_data_never_mix(db_factory, client):
    """R1.2 / R6.4: a demo cohort can never stand in for, or be frozen into, the real study."""
    w = build_world(db_factory, n_students=14, student_accounts=False)
    forms = approved_forms(client, w)
    real = build_study(client, w, n_cohorts=7, size=1, origin="real_study", seed="real", code_prefix="R",
                       student_offset=0)
    demo = build_study(client, w, n_cohorts=7, size=1, origin="synthetic_demo", seed="demo", code_prefix="D",
                       student_offset=7)
    real_windows, demo_windows = study_windows(real), study_windows(demo)
    assert post_schedule(client, w, forms, real_windows).json()["created"] == 14
    assert post_schedule(client, w, forms, demo_windows, data_origin="synthetic_demo").json()["created"] == 14

    login(client, "admin_user")
    # Each origin exports only its own rows, and the row itself says which it is.
    real_rows = client.get("/api/assessments/admin/export?data_origin=real_study").json()["records"]
    demo_rows = client.get("/api/assessments/admin/export?data_origin=synthetic_demo").json()["records"]
    assert {r["data_origin"] for r in real_rows} == {"real_study"} and len(real_rows) == 14
    assert {r["data_origin"] for r in demo_rows} == {"synthetic_demo"} and len(demo_rows) == 14
    assert not {r["study_student_code"] for r in real_rows} & {r["study_student_code"] for r in demo_rows}
    # A frozen dataset version carries one origin and cannot be read as the other.
    lock = client.post("/api/assessments/admin/dataset-locks",
                       json={"dataset_version": "demo-only-v1", "data_origin": "synthetic_demo",
                             "allow_incomplete": True})
    assert lock.status_code == 200, lock.text
    snapshot = client.get("/api/assessments/admin/dataset-locks/demo-only-v1").json()["snapshot"]
    assert snapshot["data_origin"] == "synthetic_demo"
    assert {r["data_origin"] for r in snapshot["records"]} == {"synthetic_demo"}
    # Re-running for either origin is a no-op; the other origin's batches are never touched.
    assert post_schedule(client, w, forms, real_windows).json()["created"] == 0
    assert post_schedule(client, w, forms, demo_windows, data_origin="synthetic_demo").json()["created"] == 0
    # A batch code that belongs to the other origin is not a batch of this one.
    r = post_schedule(client, w, forms, {**real_windows, demo[0]: real_windows[real[0]]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_cohort"


def stored_record(db_factory, kind):
    """(allocation_version, content_sha256, record_json) of the one frozen draw of a kind."""
    db = db_factory()
    from app.assessment_models import StudyAllocation
    rows = [(a.allocation_version, a.record_sha256, a.record_json)
            for a in db.query(StudyAllocation).filter_by(kind=kind).order_by(StudyAllocation.id)]
    db.close()
    assert len(rows) == 1, rows
    return rows[0]
