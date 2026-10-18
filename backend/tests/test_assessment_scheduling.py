"""Scheduling invariants: indivisible batches, longitudinal consistency, blinding-risk flag, data origins."""
from datetime import timedelta

from app.assessment_models import AssessmentSitting
from tests.assessment_helpers import build_world, login, now_utc, publish_form, schedule, window


def _post(client, w, form, student, **kw):
    login(client, "admin_user")
    s, e = window()
    body = {"student_id": student, "form_id": form, "cohort_code": kw.pop("cohort", "cohort1"), "study_group": kw.pop("group", "CLINPATH"),
            "timepoint": kw.pop("tp", "T0"), "window_start": s, "window_end": e,
            "rater_a_id": w.users["rater_a"], "rater_b_id": w.users["rater_b"], **kw}
    return client.post("/api/assessments/admin/sittings", json=body)


def test_cannot_split_one_batch_into_two_study_groups(db_factory, client):
    w = build_world(db_factory, n_students=2)
    form = publish_form(client, w)
    assert _post(client, w, form, w.students[0]).status_code == 200
    r = _post(client, w, form, w.students[1], group="CBL")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "cohort_split"


def test_a_batch_holds_at_most_seven_students_and_a_student_has_one_arm(db_factory, client):
    w = build_world(db_factory, n_students=8)
    form = publish_form(client, w)
    for st in w.students[:7]:
        assert _post(client, w, form, st).status_code == 200
    full = _post(client, w, form, w.students[7])
    assert full.status_code == 409 and full.json()["detail"]["code"] == "cohort_full"
    # The same student in another batch/arm at T1 is a longitudinal inconsistency.
    form2 = publish_form(client, w, code="ASSESS-B-TEST", tag="B")
    other = _post(client, w, form2, w.students[0], tp="T1", cohort="cohort2", group="CBL")
    assert other.status_code == 409 and other.json()["detail"]["code"] == "longitudinal_mismatch"
    ok = _post(client, w, form2, w.students[0], tp="T1")
    assert ok.status_code == 200
    again = _post(client, w, form2, w.students[0], tp="T1")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "timepoint_assigned"


def test_t0_and_t1_must_use_different_forms_and_valid_values(db_factory, client):
    w = build_world(db_factory)
    form = publish_form(client, w)
    assert _post(client, w, form, w.students[0]).status_code == 200
    same = _post(client, w, form, w.students[0], tp="T1")
    assert same.status_code == 409 and same.json()["detail"]["code"] == "same_form_twice"
    assert _post(client, w, form, w.students[0], tp="T2").status_code == 400
    assert _post(client, w, form, w.students[0], group="OTHER").status_code == 400
    login(client, "admin_user")
    n = now_utc()
    inverted = client.post("/api/assessments/admin/sittings", json={
        "student_id": w.students[0], "form_id": form, "cohort_code": "q", "study_group": "CBL", "timepoint": "T1",
        "window_start": (n + timedelta(hours=2)).isoformat() + "Z", "window_end": n.isoformat() + "Z",
        "rater_a_id": w.users["rater_a"], "rater_b_id": w.users["rater_b"]})
    assert inverted.status_code == 400 and inverted.json()["detail"]["code"] == "bad_window"


def test_rater_who_teaches_the_cohort_is_flagged_not_called_blind(db_factory, client):
    w = build_world(db_factory, n_students=2)
    form = publish_form(client, w)
    login(client, "admin_user")
    # No roster at all: blinding cannot be verified.
    first = _post(client, w, form, w.students[0], cohort="free-text")
    assert first.json()["blinding_risk"] == "UNVERIFIED_NO_COHORT_ROSTER"
    # Roster says rater_a also teaches batch B1 => explicit risk record.
    c = client.post("/api/assessments/admin/cohorts", json={"cohort_code": "B1", "label": "批次1", "teaching_user_ids": [w.users["rater_a"]]})
    assert c.status_code == 200
    assert client.post("/api/assessments/admin/cohorts/B1/enrollments", json={"student_ids": [w.students[1]]}).status_code == 200
    risky = _post(client, w, form, w.students[1], cohort="B1")
    assert risky.status_code == 200 and risky.json()["blinding_risk"] == "TEACHES_COHORT"
    # With an independent pair the record says only that no conflict is on file — never "blind".
    clean = client.post("/api/assessments/admin/cohorts", json={"cohort_code": "B2", "label": "批次2", "teaching_user_ids": [w.users["plain_teacher"]]})
    assert clean.status_code == 200
    rows = {r["cohort_code"]: r["blinding_risk"] for r in client.get("/api/assessments/admin/sittings").json()}
    assert rows == {"free-text": "UNVERIFIED_NO_COHORT_ROSTER", "B1": "TEACHES_COHORT"}
    export = client.get("/api/assessments/admin/export?data_origin=pilot_test").json()["records"]
    assert {r["blinding_risk"] for r in export} == {"UNVERIFIED_NO_COHORT_ROSTER", "TEACHES_COHORT"}


def test_cohort_members_must_be_enrolled_and_origins_cannot_mix(db_factory, client):
    w = build_world(db_factory, n_students=2)
    form = publish_form(client, w)
    login(client, "admin_user")
    client.post("/api/assessments/admin/cohorts", json={"cohort_code": "B1", "label": "批次1", "data_origin": "pilot_test"})
    r = _post(client, w, form, w.students[0], cohort="B1")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_enrolled"
    client.post("/api/assessments/admin/cohorts/B1/enrollments", json={"student_ids": [w.students[0]]})
    assert _post(client, w, form, w.students[0], cohort="B1", data_origin="synthetic_demo").status_code == 409
    assert _post(client, w, form, w.students[0], cohort="B1", data_origin="made_up").status_code == 400
    assert client.post("/api/assessments/admin/cohorts/B1/enrollments", json={"student_ids": [w.students[0]]}).status_code == 409
    # A real-study sitting needs a registered cohort and frozen allocations first.
    client.post("/api/assessments/admin/cohorts", json={"cohort_code": "R1", "label": "真实1", "data_origin": "real_study"})
    client.post("/api/assessments/admin/cohorts/R1/enrollments", json={"student_ids": [w.students[1]]})
    real = _post(client, w, form, w.students[1], cohort="R1", data_origin="real_study")
    assert real.status_code == 409 and real.json()["detail"]["code"] == "allocation_required"
    assert _post(client, w, form, w.students[1], cohort="unregistered", data_origin="real_study").status_code == 409
