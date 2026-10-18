"""R2.1: form authoring, two-real-teacher approval, publication and freezing."""
import json

from app.assessment_models import AssessmentForm
from tests.assessment_helpers import (
    SECRET_KEY, build_world, login, publish_form, schedule, stages, window,
)


def _new_form(client, code="F-1", **extra):
    return client.post("/api/assessments/forms", json={"code": code, "title": "题本", "stages": stages(), "answer_key": SECRET_KEY,
                                                       "rubric": {}, **extra})


def test_only_staff_author_forms_and_students_see_nothing(db_factory, client):
    w = build_world(db_factory)
    login(client, w.student_users[0])
    assert _new_form(client).status_code == 403
    assert client.get("/api/assessments/forms/admin/all").status_code == 403
    login(client, "plain_teacher")
    ok = _new_form(client, "F-T")
    assert ok.status_code == 200 and ok.json()["review_status"] == "PENDING_REAL_REVIEW"
    bad = client.post("/api/assessments/forms", json={"code": "F-BAD", "title": "题本", "stages": stages()[:4], "answer_key": {}, "rubric": {}})
    assert bad.status_code == 400 and bad.json()["detail"]["code"] == "bad_stages"
    assert _new_form(client, "F-T").status_code == 409


def test_approval_needs_two_distinct_assigned_teachers_and_admin_cannot_forge_it(db_factory, client):
    w = build_world(db_factory)
    login(client, "admin_user")
    fid = _new_form(client).json()["id"]
    # An admin has no review endpoint: it is teacher-only.
    assert client.post(f"/api/assessments/forms/{fid}/review", json={"decision": "approve", "comment": "管理员伪造"}).status_code == 403
    one = client.post(f"/api/assessments/forms/{fid}/reviewers", json={"teacher_user_ids": [w.users["rev_one"]]})
    assert one.status_code == 422  # at least two reviewers must be named
    same = client.post(f"/api/assessments/forms/{fid}/reviewers", json={"teacher_user_ids": [w.users["rev_one"], w.users["rev_one"]]})
    assert same.status_code == 400
    notteacher = client.post(f"/api/assessments/forms/{fid}/reviewers", json={"teacher_user_ids": [w.users["rev_one"], w.users["admin_user"]]})
    assert notteacher.status_code == 400 and notteacher.json()["detail"]["code"] == "not_teachers"
    assert client.post(f"/api/assessments/forms/{fid}/reviewers", json={"teacher_user_ids": [w.users["rev_one"], w.users["rev_two"]]}).status_code == 200
    # Not invited => the form does not exist for that teacher.
    login(client, "plain_teacher")
    assert client.get("/api/assessments/forms/reviewable").json() == []
    assert client.post(f"/api/assessments/forms/{fid}/review", json={"decision": "approve", "comment": "未受邀"}).status_code == 404
    login(client, "rev_one")
    listing = client.get("/api/assessments/forms/reviewable").json()
    assert [f["id"] for f in listing] == [fid] and listing[0]["answer_key"] == SECRET_KEY
    assert client.post(f"/api/assessments/forms/{fid}/review", json={"decision": "approve", "comment": "通过"}).status_code == 200
    assert client.post(f"/api/assessments/forms/{fid}/review", json={"decision": "approve", "comment": "再次"}).status_code == 409
    login(client, "admin_user")
    short = client.post(f"/api/assessments/forms/{fid}/approve")
    assert short.status_code == 409 and short.json()["detail"]["code"] == "two_approvals_required"
    login(client, "rev_two")
    client.post(f"/api/assessments/forms/{fid}/review", json={"decision": "approve", "comment": "通过"})
    login(client, "admin_user")
    assert client.post(f"/api/assessments/forms/{fid}/approve").status_code == 200
    detail = client.get(f"/api/assessments/forms/{fid}/admin").json()
    assert detail["review_status"] == "APPROVED_FOR_ASSESSMENT" and all(r["matches_current_content"] for r in detail["reviews"])
    log = client.get("/api/assessments/admin/audit?action=form.publish").json()
    assert sorted(log[0]["detail"]["approving_teacher_user_ids"]) == sorted([w.users["rev_one"], w.users["rev_two"]])


def test_two_logins_of_one_teacher_count_once_and_the_author_cannot_review(db_factory, client):
    w = build_world(db_factory)
    from app.models import User
    db = db_factory()
    db.get(User, w.users["rev_two"]).teacher_id = db.get(User, w.users["rev_one"]).teacher_id
    db.commit()
    db.close()
    login(client, "admin_user")
    fid = _new_form(client).json()["id"]
    r = client.post(f"/api/assessments/forms/{fid}/reviewers", json={"teacher_user_ids": [w.users["rev_one"], w.users["rev_two"]]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "distinct_reviewers"
    login(client, "plain_teacher")
    tid = _new_form(client, "F-AUTH").json()["id"]
    login(client, "admin_user")
    r = client.post(f"/api/assessments/forms/{tid}/reviewers", json={"teacher_user_ids": [w.users["plain_teacher"], w.users["rev_two"]]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "author_cannot_review"


def test_a_rejection_blocks_publication_until_a_new_version_is_reviewed(db_factory, client):
    w = build_world(db_factory)
    login(client, "admin_user")
    fid = _new_form(client).json()["id"]
    client.post(f"/api/assessments/forms/{fid}/reviewers", json={"teacher_user_ids": [w.users["rev_one"], w.users["rev_two"]]})
    login(client, "rev_one")
    client.post(f"/api/assessments/forms/{fid}/review", json={"decision": "approve", "comment": "可以"})
    login(client, "rev_two")
    client.post(f"/api/assessments/forms/{fid}/review", json={"decision": "reject", "comment": "鉴别诊断不充分"})
    login(client, "admin_user")
    r = client.post(f"/api/assessments/forms/{fid}/approve")
    assert r.status_code == 409
    assert client.get(f"/api/assessments/forms/{fid}/admin").json()["review_status"] == "CHANGES_REQUESTED"
    v2 = client.post(f"/api/assessments/forms/{fid}/versions", json={"title": "题本（修订）"})
    assert v2.status_code == 200 and v2.json()["version"] == 2
    new_id = v2.json()["id"]
    # Old approvals do not carry over: the new version has no reviewers and no reviews.
    assert client.post(f"/api/assessments/forms/{new_id}/approve").status_code == 409
    assert client.get(f"/api/assessments/forms/{fid}/admin").json()["review_status"] == "SUPERSEDED"
    # Rejected content is no longer reviewable either.
    login(client, "rev_one")
    assert client.post(f"/api/assessments/forms/{fid}/review", json={"decision": "approve", "comment": "晚了"}).status_code in (404, 409)


def test_published_form_is_frozen_and_changes_create_a_new_version(db_factory, client):
    w = build_world(db_factory)
    v1 = publish_form(client, w)
    sid = schedule(client, w, w.students[0], v1)
    login(client, "rev_one")
    assert client.post(f"/api/assessments/forms/{v1}/review", json={"decision": "reject", "comment": "已发布后试图拒绝"}).status_code == 409
    login(client, "admin_user")
    assert client.post(f"/api/assessments/forms/{v1}/reviewers", json={"teacher_user_ids": [w.users["rev_one"], w.users["plain_teacher"]]}).status_code == 409
    assert client.post(f"/api/assessments/forms/{v1}/approve").status_code == 409  # already frozen
    assert client.post(f"/api/assessments/forms/{v1}/versions", json={}).status_code == 409  # nothing changed
    new_stages = stages()
    new_stages[2]["clinical_information"] = "修订后的阶段二资料"
    v2 = client.post(f"/api/assessments/forms/{v1}/versions", json={"stages": new_stages}).json()
    assert v2["version"] == 2 and v2["id"] != v1
    # The historic sitting still points at the exact v1 content.
    db = db_factory()
    f1 = db.get(AssessmentForm, v1)
    assert f1.review_status == "APPROVED_FOR_ASSESSMENT" and json.loads(f1.stages_json) == stages()
    assert db.get(AssessmentForm, v2["id"]).content_sha256 != f1.content_sha256
    db.close()
    # v2 is unreviewed => unusable for a sitting.
    s, e = window()
    r = client.post("/api/assessments/admin/sittings", json={"student_id": w.students[0], "form_id": v2["id"], "cohort_code": "x2",
                                                             "study_group": "CBL", "timepoint": "T1", "window_start": s, "window_end": e,
                                                             "rater_a_id": w.users["rater_a"], "rater_b_id": w.users["rater_b"]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "form_not_approved"
    login(client, w.student_users[0])
    client.post(f"/api/assessments/my/{sid}/start")
    assert "修订后的阶段二资料" not in client.get(f"/api/assessments/my/{sid}").text


def test_a_form_that_is_not_published_cannot_be_sat_even_if_scheduled_directly(db_factory, client):
    w = build_world(db_factory)
    v1 = publish_form(client, w)
    sid = schedule(client, w, w.students[0], v1)
    db = db_factory()
    db.get(AssessmentForm, v1).review_status = "CHANGES_REQUESTED"  # tampering with the row must not open the exam
    db.commit()
    db.close()
    login(client, w.student_users[0])
    r = client.get(f"/api/assessments/my/{sid}")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "form_not_approved"
