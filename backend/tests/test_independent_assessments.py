"""End-to-end happy path for the independent assessment domain (R2 + R3)."""
from app.assessment_models import AssessmentFinalScore, AssessmentReview
from tests.assessment_helpers import (
    SCORES, build_world, blind_code_for, login, publish_form, rate, schedule, sit_exam,
)


def test_independent_exam_stages_and_blind_double_review(db_factory, client):
    w = build_world(db_factory)
    form_id = publish_form(client, w)
    sid = schedule(client, w, w.students[0], form_id)
    login(client, w.student_users[0])
    assert client.get("/api/assessments/blind/queue").status_code == 403
    assert client.post(f"/api/assessments/my/{sid}/start").status_code == 200
    for index in range(5):
        got = client.get(f"/api/assessments/my/{sid}")
        assert got.status_code == 200
        data = got.json()
        assert data["stage"]["index"] == index
        text = str(data)
        assert "answer_key" not in text and "HIDDEN-REFERENCE" not in text and "ANCHOR-TEXT" not in text
        assert f"A信息{index + 1}" not in text  # later stages are not released
        post = client.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": index, "answer_text": f"独立作答{index}"})
        assert post.status_code == 200, post.text
    assert client.post(f"/api/assessments/my/{sid}/submit").status_code == 200
    done = client.get(f"/api/assessments/my/{sid}")
    assert done.status_code == 200 and done.json()["status"] == "submitted" and "stage" not in done.json()
    codes = {}
    for rater in ("rater_a", "rater_b"):
        queue = blind_code_for(client, rater)
        assert len(queue) == 1
        codes[rater] = queue[0]
        detail = client.get("/api/assessments/blind/" + queue[0]).json()
        for banned in ("student_id", "timepoint", "study_group", "cohort_code", "scores", "sitting_id"):
            assert banned not in detail
        assert rate(client, rater, queue[0])["status"] == "locked"
        # Re-sending different scores is refused; identical scores are an idempotent no-op.
        again = client.post("/api/assessments/blind/" + queue[0] + "/review", json={"scores": {**SCORES, "medical_knowledge": 1}})
        assert again.status_code == 409
        assert client.get("/api/assessments/admin/export?data_origin=pilot_test").status_code == 403
    assert codes["rater_a"] == codes["rater_b"]
    db = db_factory()
    assert db.query(AssessmentReview).count() == 2
    db.close()
    login(client, "admin_user")
    fin = client.post(f"/api/assessments/admin/sittings/{sid}/finalize")
    assert fin.status_code == 200, fin.text
    assert fin.json()["scoring_provenance"] == "dual_mean"
    exported = client.get("/api/assessments/admin/export?data_origin=pilot_test")
    assert exported.status_code == 200
    rec = exported.json()["records"][0]
    assert rec["blinded_rater_1_score"] == rec["blinded_rater_2_score"] == rec["final_score"]
    assert "student_id" not in rec and rec["study_student_code"].startswith("S")
    db = db_factory()
    assert db.query(AssessmentFinalScore).count() == 1
    db.close()


def test_reject_unapproved_form(db_factory, client):
    w = build_world(db_factory)
    login(client, "admin_user")
    r = client.post("/api/assessments/forms", json={"code": "PENDING", "title": "待审核考核", "stages": __import__("tests.assessment_helpers", fromlist=["stages"]).stages(),
                                                    "answer_key": {}, "rubric": {}})
    assert r.status_code == 200
    from tests.assessment_helpers import window
    s, e = window()
    sit = client.post("/api/assessments/admin/sittings", json={
        "student_id": w.students[0], "form_id": r.json()["id"], "cohort_code": "B2", "study_group": "CBL",
        "timepoint": "T1", "window_start": s, "window_end": e,
        "rater_a_id": w.users["rater_a"], "rater_b_id": w.users["rater_b"]})
    assert sit.status_code == 409 and sit.json()["detail"]["code"] == "form_not_approved"
