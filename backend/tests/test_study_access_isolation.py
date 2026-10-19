"""R9 §3: the CBL study arm cannot reach the ClinPath formative intervention.

The study allocates whole teaching batches to an arm. A batch frozen into the CBL
arm must not receive the ClinPath-only training during the intervention: not by
opening the new-session route, not through the AI tutor, not by submitting, not by
reading the personalised recommendation, and not through a session that already
existed when the restriction began. The independent T0/T1 assessment and the
ordinary teaching resources (case library, knowledge, guidelines, skills, SP) stay
open, and students outside the study and staff accounts are unaffected.

Every account here is a TEST fixture: the batches are test batches, the teachers
are fixture accounts, and nothing represents a real learner or physician.
"""
import json
from datetime import datetime, timedelta

from app.assessment_models import AssessmentSitting, StudyEnrollment
from app.auth import hash_password
from app.models import CaseSession, User
from app.research.study_access import access_for
from tests.assessment_helpers import (
    build_study, build_world, design_rows, login, publish_form, schedule, sit_exam,
)
from tests.factories import ANSWER_TEXTS, make_case, make_catalog, make_student

ORIGIN = "real_study"
STUDENT_PASSWORD = "secret1"


class Study:
    pass


def _today():
    return datetime.utcnow().date()


def _d(offset):
    return _today() + timedelta(days=offset)


def set_window(client, cohort_code, start_offset=-1, end_offset=1):
    login(client, "admin_user")
    r = client.post(f"/api/assessments/admin/cohorts/{cohort_code}/actual-dates",
                    json={"actual_start": str(_d(start_offset)), "actual_end": str(_d(end_offset))})
    assert r.status_code == 200, r.text


def _add_student_login(db, student_id, username):
    user = User(username=username, password_hash=hash_password(STUDENT_PASSWORD), role="student",
                student_id=student_id)
    db.add(user)
    db.flush()
    return user.id


def build(db_factory, client, window=(-1, 1), freeze=True):
    """A complete 7x7 study with both draws frozen, a training case and three logins."""
    w = build_world(db_factory, n_students=49, student_accounts=False)
    db = db_factory()
    case = make_case(db)
    make_catalog(db)
    plain, plain_user = make_student(db, name="非研究学生", username="plain_student")
    case_id, plain_id, plain_username = case.id, plain.id, plain_user.username
    db.commit()
    db.close()
    codes = build_study(client, w, freeze=freeze)
    study = Study()
    study.w, study.codes, study.case_id, study.plain_id = w, codes, case_id, plain_id
    study.plain_user = plain_username
    study.rows = design_rows(client) if freeze else []
    study.by_student = {r["student_id"]: r for r in study.rows}
    if freeze:
        study.cbl = next(r for r in study.rows if r["study_group"] == "CBL")
        study.clinpath = next(r for r in study.rows if r["study_group"] == "CLINPATH")
        db = db_factory()
        _add_student_login(db, study.cbl["student_id"], "cbl_student")
        _add_student_login(db, study.clinpath["student_id"], "clinpath_student")
        db.commit()
        db.close()
        study.cbl_user = "cbl_student"
        study.clinpath_user = "clinpath_student"
    if window is not None:
        for code in codes:
            set_window(client, code, *window)
    return study


def blocked(response, code="study_training_restricted"):
    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert set(detail) == {"code", "message"} and detail["code"] == code, detail
    return detail


def session_ids(db_factory, student_id):
    db = db_factory()
    try:
        return [row.id for row in db.query(CaseSession).filter_by(student_id=student_id)]
    finally:
        db.close()


# --- the negative path: the intervention is closed --------------------------------

def test_cbl_student_cannot_start_a_training_session(db_factory, client):
    study = build(db_factory, client)
    login(client, study.cbl_user)
    r = client.post("/api/sessions/start", json={"case_id": study.case_id})
    blocked(r)
    assert session_ids(db_factory, study.cbl["student_id"]) == []  # no row was created


def test_cbl_student_cannot_bypass_through_an_old_session(db_factory, client):
    # The batch trains while its window is still closed (allowed); the restriction
    # then begins and every way of continuing or reading that old session is refused.
    study = build(db_factory, client, window=(-10, -5))
    login(client, study.cbl_user)
    started = client.post("/api/sessions/start", json={"case_id": study.case_id})
    assert started.status_code == 200, started.text
    session_id = started.json()["id"]
    for step, text in ANSWER_TEXTS.items():
        assert client.post(f"/api/sessions/{session_id}/answers",
                           json={"step": step, "answer_text": text}).status_code == 200
    assert client.post(f"/api/sessions/{session_id}/submit").status_code == 200
    assert client.get(f"/api/sessions/{session_id}/result").status_code == 200  # before the window

    set_window(client, study.cbl["cohort_code"], -1, 1)
    login(client, study.cbl_user)

    for path, body in (
        ((f"/api/sessions/{session_id}/answers"), {"step": "treatment", "answer_text": "改写"}),
        ((f"/api/sessions/{session_id}/coach"), {"step": "treatment", "answer_text": "改写"}),
        ((f"/api/sessions/{session_id}/tutor"), {"step": "treatment", "message": "还有呢？"}),
        ((f"/api/sessions/{session_id}/submit"), None),
    ):
        r = client.post(path, json=body) if body is not None else client.post(path)
        blocked(r)
    blocked(client.get(f"/api/sessions/{session_id}/result"))
    blocked(client.get(f"/api/sessions/{session_id}/tutor?step=treatment"))
    blocked(client.get("/api/student/history"))


def test_cbl_student_cannot_read_personalisation_or_competency(db_factory, client):
    study = build(db_factory, client)
    student_id = study.cbl["student_id"]
    login(client, study.cbl_user)
    for path in ("/api/student/pathway", "/api/student/competency", "/api/student/dashboard",
                 f"/api/students/{student_id}/pathway", f"/api/students/{student_id}/competency",
                 f"/api/students/{student_id}/dashboard"):
        blocked(client.get(path))
    # Not intervention content: the account itself and the knowledge-progress tracker stay readable.
    assert client.get("/api/student/me").status_code == 200
    assert client.get("/api/student/knowledge-progress").status_code == 200


def test_refusal_reveals_no_arm_or_cohort(db_factory, client):
    study = build(db_factory, client)
    login(client, study.cbl_user)
    responses = [
        client.post("/api/sessions/start", json={"case_id": study.case_id}),
        client.get("/api/student/pathway"),
        client.get("/api/student/dashboard"),
    ]
    forbidden = {"CBL", "CLINPATH", "cbl", "clinpath", "C1", "C2", "C3", "C4", "C5", "C6", "C7",
                 study.cbl["cohort_code"], study.cbl["study_student_code"]}
    for r in responses:
        blob = json.dumps(blocked(r), ensure_ascii=False)
        for token in forbidden:
            assert token not in blob, (token, blob)


# --- the window decides when the restriction applies -------------------------------

def test_restriction_follows_the_recorded_window(db_factory, client):
    study = build(db_factory, client, window=None)
    cohort = study.cbl["cohort_code"]
    login(client, study.cbl_user)

    # No dates recorded: the arm is frozen, so the intervention stays closed rather
    # than being guessed open. The refusal says nothing about why.
    blocked(client.post("/api/sessions/start", json={"case_id": study.case_id}))
    db = db_factory()
    assert access_for(db, study.cbl["student_id"]).reason == "cbl_arm_window_undetermined"
    db.close()

    set_window(client, cohort, 2, 5)  # not started yet: still closed
    login(client, study.cbl_user)
    blocked(client.post("/api/sessions/start", json={"case_id": study.case_id}))

    set_window(client, cohort, -9, -3)  # recorded as finished: the teaching plan releases it
    login(client, study.cbl_user)
    assert client.post("/api/sessions/start", json={"case_id": study.case_id}).status_code == 200


def test_a_withdrawn_student_is_no_longer_restricted(db_factory, client):
    study = build(db_factory, client)
    db = db_factory()
    db.query(StudyEnrollment).filter_by(student_id=study.cbl["student_id"]).one().status = "withdrawn"
    db.commit()
    db.close()
    login(client, study.cbl_user)
    assert client.post("/api/sessions/start", json={"case_id": study.case_id}).status_code == 200


def test_an_unfrozen_arm_is_never_guessed(db_factory, client):
    study = build(db_factory, client, freeze=False)
    enrolled = study.w.students[0]
    db = db_factory()
    _add_student_login(db, enrolled, "unfrozen_student")
    db.commit()
    db.close()
    login(client, "unfrozen_student")
    assert client.post("/api/sessions/start", json={"case_id": study.case_id}).status_code == 200
    assert client.get("/api/student/pathway").status_code == 200


# --- the positive path: everything else keeps working ------------------------------

def test_cbl_student_can_complete_the_independent_assessment(db_factory, client):
    study = build(db_factory, client)
    form = publish_form(client, study.w)
    row = study.cbl
    sitting_id = schedule(client, study.w, row["student_id"], form, cohort=row["cohort_code"], group="CBL",
                          data_origin=ORIGIN)
    sit_exam(client, study.cbl_user, sitting_id)
    db = db_factory()
    stored = db.get(AssessmentSitting, sitting_id)
    assert stored.status == "submitted" and stored.study_group == "CBL"
    db.close()
    # The training side stays closed in the same login session.
    blocked(client.post("/api/sessions/start", json={"case_id": study.case_id}))


def test_clinpath_student_trains_normally(db_factory, client):
    study = build(db_factory, client)
    login(client, study.clinpath_user)
    started = client.post("/api/sessions/start", json={"case_id": study.case_id})
    assert started.status_code == 200, started.text
    session_id = started.json()["id"]
    for step, text in ANSWER_TEXTS.items():
        assert client.post(f"/api/sessions/{session_id}/answers",
                           json={"step": step, "answer_text": text}).status_code == 200
    assert client.post(f"/api/sessions/{session_id}/submit").status_code == 200
    assert client.get(f"/api/sessions/{session_id}/result").status_code == 200
    for path in ("/api/student/pathway", "/api/student/competency", "/api/student/dashboard",
                 "/api/student/history"):
        assert client.get(path).status_code == 200, path


def test_non_study_student_is_unaffected(db_factory, client):
    study = build(db_factory, client)
    login(client, study.plain_user)
    started = client.post("/api/sessions/start", json={"case_id": study.case_id})
    assert started.status_code == 200, started.text
    session_id = started.json()["id"]
    for step, text in ANSWER_TEXTS.items():
        assert client.post(f"/api/sessions/{session_id}/answers",
                           json={"step": step, "answer_text": text}).status_code == 200
    assert client.post(f"/api/sessions/{session_id}/submit").status_code == 200
    assert client.get("/api/student/pathway").status_code == 200


def test_ordinary_teaching_resources_stay_open(db_factory, client):
    study = build(db_factory, client)
    login(client, study.cbl_user)
    assert client.get("/api/cases").status_code == 200
    assert client.get(f"/api/cases/{study.case_id}").status_code == 200
    for path in ("/api/knowledge", "/api/guidelines", "/api/skills", "/api/sp-cases"):
        assert client.get(path).status_code == 200, path
    # The session shell (case material + the student's own ungraded answers) is not
    # intervention output and stays readable; /result above is the graded record.
    db = db_factory()
    shell = CaseSession(student_id=study.cbl["student_id"], case_id=study.case_id)
    db.add(shell)
    db.commit()
    shell_id = shell.id
    db.close()
    assert client.get(f"/api/sessions/{shell_id}").status_code == 200


def test_staff_keep_their_view_of_a_restricted_student(db_factory, client):
    study = build(db_factory, client)
    student_id = study.cbl["student_id"]
    login(client, "plain_teacher")
    for path in (f"/api/students/{student_id}/pathway", f"/api/students/{student_id}/competency",
                 f"/api/students/{student_id}/dashboard"):
        assert client.get(path).status_code == 200, path


def test_policy_agrees_with_the_frozen_allocation(db_factory, client):
    study = build(db_factory, client)
    login(client, "admin_user")
    allocations = client.get("/api/assessments/admin/allocations").json()
    cluster = next(a for a in allocations if a["kind"] == "cluster_group")["record"]
    by_cohort = {"CLINPATH": set(cluster["clinpath_cohorts"]), "CBL": set(cluster["cbl_cohorts"])}
    db = db_factory()
    try:
        for row in study.rows:
            access = access_for(db, row["student_id"])
            assert access.enrolled and access.group is not None
            assert access.group.upper() == row["study_group"]
            assert row["cohort_code"] in by_cohort[row["study_group"]]
    finally:
        db.close()
