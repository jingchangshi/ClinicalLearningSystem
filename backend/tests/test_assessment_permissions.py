"""R1.3: role / permission matrix for every assessment endpoint.

Roles: anonymous, the sitting's student, another student, a plain teacher, a blinded
rater, the adjudicator, an invited form reviewer, and the study admin.
Each row lists who is *allowed*; every other role must be refused (401/403/404).
"""
import pytest
from fastapi.testclient import TestClient

from tests.assessment_helpers import SCORES, build_world, login, publish_form, schedule, seed_submitted, window

S, T, A = "student", "teacher", "admin"
OWN, OTHER = "own_student", "other_student"
ROLES = ["anonymous", OWN, OTHER, "plain_teacher", "rater_a", "adjudicator", "rev_one", "admin_user"]
TEACHERS = {"plain_teacher", "rater_a", "adjudicator", "rev_one"}


def endpoints(fid, sid, code, rid):
    P = "/api/assessments"
    stage = {"stage_index": 0, "answer_text": "x"}
    ws, we = window()
    sit = {"student_id": 1, "form_id": fid, "cohort_code": "zz", "study_group": "CBL", "timepoint": "T1",
           "window_start": ws, "window_end": we, "rater_a_id": 1, "rater_b_id": 2}
    # (method, path, json, allowed roles)
    return [
        ("POST", f"{P}/forms", {"code": "PM", "title": "t", "stages": [], "answer_key": {}, "rubric": {}}, {"admin_user", *TEACHERS}),
        ("POST", f"{P}/forms/{fid}/versions", {}, {"admin_user", *TEACHERS}),
        ("GET", f"{P}/forms/admin/all", None, {"admin_user"}),
        ("GET", f"{P}/forms/{fid}/admin", None, {"admin_user"}),
        ("POST", f"{P}/forms/{fid}/reviewers", {"teacher_user_ids": [1, 2]}, {"admin_user"}),
        ("POST", f"{P}/forms/{fid}/approve", None, {"admin_user"}),
        ("GET", f"{P}/forms/reviewable", None, TEACHERS),
        ("POST", f"{P}/forms/{fid}/review", {"decision": "approve", "comment": "ok"}, {"rev_one"}),
        ("GET", f"{P}/my", None, {OWN, OTHER}),
        ("GET", f"{P}/my/{sid}", None, {OWN}),
        ("POST", f"{P}/my/{sid}/start", None, {OWN}),
        ("PUT", f"{P}/my/{sid}/draft", stage, {OWN}),
        ("POST", f"{P}/my/{sid}/answer", stage, {OWN}),
        ("POST", f"{P}/my/{sid}/submit", None, {OWN}),
        ("POST", f"{P}/my/{sid}/interruption", {"reason": "net down"}, {OWN}),
        ("GET", f"{P}/blind/queue", None, TEACHERS),
        ("GET", f"{P}/blind/{code}", None, {"rater_a"}),
        ("POST", f"{P}/blind/{code}/review", {"scores": SCORES}, {"rater_a"}),
        ("GET", f"{P}/adjudication/queue", None, TEACHERS),
        ("GET", f"{P}/adjudication/{code}", None, {"adjudicator"}),
        ("POST", f"{P}/adjudication/{code}", {"scores": SCORES, "rationale": "reason text"}, {"adjudicator"}),
        ("POST", f"{P}/admin/sittings", sit, {"admin_user"}),
        ("POST", f"{P}/sittings", sit, {"admin_user"}),
        ("GET", f"{P}/admin/sittings", None, {"admin_user"}),
        ("GET", f"{P}/admin/sittings/{sid}", None, {"admin_user"}),
        ("POST", f"{P}/admin/sittings/{sid}/extend", {"new_window_end": we, "reason": "reason"}, {"admin_user"}),
        ("POST", f"{P}/admin/sittings/{sid}/retake", {"reason": "reason", "window_start": ws, "window_end": we}, {"admin_user"}),
        ("POST", f"{P}/admin/sittings/{sid}/finalize", None, {"admin_user"}),
        ("POST", f"{P}/admin/sweep-expired", None, {"admin_user"}),
        ("POST", f"{P}/admin/reviews/{rid}/reopen", {"reason": "reason"}, {"admin_user"}),
        ("GET", f"{P}/admin/audit", None, {"admin_user"}),
        ("GET", f"{P}/admin/identity-map", None, {"admin_user"}),
        ("GET", f"{P}/admin/export?data_origin=pilot_test", None, {"admin_user"}),
        ("GET", f"{P}/admin/agreement?data_origin=pilot_test", None, {"admin_user"}),
        ("POST", f"{P}/admin/dataset-locks", {"dataset_version": "perm-1", "data_origin": "pilot_test"}, {"admin_user"}),
        ("GET", f"{P}/admin/dataset-locks", None, {"admin_user"}),
        ("GET", f"{P}/admin/dataset-locks/perm-1", None, {"admin_user"}),
        ("POST", f"{P}/admin/cohorts", {"cohort_code": "pm", "label": "pm"}, {"admin_user"}),
        ("GET", f"{P}/admin/cohorts", None, {"admin_user"}),
        ("POST", f"{P}/admin/cohorts/pm/enrollments", {"student_ids": [1]}, {"admin_user"}),
        ("POST", f"{P}/admin/cohorts/pm/actual-dates", {"actual_start": "2026-11-02", "actual_end": "2026-11-08"}, {"admin_user"}),
        ("POST", f"{P}/admin/allocations/form-order", {"protocol_version": "v1"}, {"admin_user"}),
        ("POST", f"{P}/admin/allocations/cluster", {"protocol_version": "v1"}, {"admin_user"}),
        ("GET", f"{P}/admin/allocations", None, {"admin_user"}),
    ]


def test_every_endpoint_refuses_every_role_that_is_not_allowed(db_factory, client):
    w = build_world(db_factory, n_students=2)
    fid = publish_form(client, w)
    sid = schedule(client, w, w.students[0], fid)
    seed_submitted(db_factory, sid)
    from app.assessment_models import AssessmentSitting
    db = db_factory()
    code = db.get(AssessmentSitting, sid).blind_code
    db.close()
    rid = 1  # does not need to exist: a refusal must come before any lookup
    rows = endpoints(fid, sid, code, rid)
    checked = 0
    for role in ROLES:
        c = TestClient(client.app)
        if role != "anonymous":
            login(c, {OWN: w.student_users[0], OTHER: w.student_users[1]}.get(role, role))
        for method, path, body, allowed in rows:
            if role in allowed:
                continue
            r = c.request(method, path, json=body)
            assert r.status_code in (401, 403, 404), (role, method, path, r.status_code, r.text[:200])
            if role == "anonymous":
                assert r.status_code == 401, (method, path)
            checked += 1
    assert checked > 250
    # Nothing the refused calls attempted took effect.
    login(client, "admin_user")
    assert client.get("/api/assessments/admin/audit?action=sitting.create").json().__len__() == 1
    assert client.get("/api/assessments/admin/sittings").json()[0]["reviews"] == 0


def test_admin_is_not_a_teacher_student_or_rater_by_accident(db_factory, client):
    w = build_world(db_factory)
    fid = publish_form(client, w)
    sid = schedule(client, w, w.students[0], fid)
    seed_submitted(db_factory, sid)
    login(client, "admin_user")
    for path in ("/api/assessments/my", "/api/assessments/blind/queue", "/api/assessments/forms/reviewable",
                 "/api/assessments/adjudication/queue"):
        assert client.get(path).status_code == 403, path
    assert client.post(f"/api/assessments/forms/{fid}/review", json={"decision": "approve", "comment": "admin"}).status_code == 403
