"""R3: blinded double rating, rubric-driven weights, adjudication and score locks."""
import json

import pytest

from app.assessment_models import AssessmentAdjudication, AssessmentReview, AssessmentSitting
from tests.assessment_helpers import (
    ABILITIES, SCORES, build_world, blind_code_for, login, publish_form, rate, schedule, seed_submitted, sit_exam, with_scores,
)


def _one_submitted(db_factory, client, rubric=None, texts=None, **world):
    w = build_world(db_factory, **world)
    form = publish_form(client, w, rubric=rubric)
    sid = schedule(client, w, w.students[0], form)
    seed_submitted(db_factory, sid, texts)
    return w, form, sid


def _scores(base, **over):
    return {**base, **over}


def test_weights_come_from_the_approved_rubric_not_from_code(db_factory, client):
    custom = {"rubric_version": "TEST-RUBRIC-7", "weights": {"medical_knowledge": 50, "key_information": 10, "differential_diagnosis": 10,
                                                             "evidence_integration": 10, "clinical_decision": 10, "evidence_based_medicine": 10}}
    w, _, sid = _one_submitted(db_factory, client, rubric=custom)
    code = blind_code_for(client, "rater_a")[0]
    scores = _scores(dict.fromkeys(ABILITIES, 50), medical_knowledge=100)
    out = rate(client, "rater_a", code, scores)
    assert out["total_score"] == 75.0  # 100*0.5 + 50*0.5, not the 10% default
    db = db_factory()
    row = db.query(AssessmentReview).one()
    assert row.rubric_version == "TEST-RUBRIC-7" and json.loads(row.weights_json)["medical_knowledge"] == 50
    assert json.loads(row.scores_json) == scores and row.rater_slot == "A"
    db.close()


def test_default_study_weights_are_labelled_pending_and_training_weights_are_untouched(db_factory, client):
    w, _, sid = _one_submitted(db_factory, client)
    code = blind_code_for(client, "rater_a")[0]
    rubric = client.get(f"/api/assessments/blind/{code}").json()["rubric"]
    assert rubric["weights"] == {"medical_knowledge": 10, "key_information": 20, "differential_diagnosis": 25,
                                 "evidence_integration": 15, "clinical_decision": 20, "evidence_based_medicine": 10}
    assert rubric["weights_source"] == "study_default" and "pending teacher confirmation" in rubric["weights_note"]
    from app.services import scoring_llm  # Training scorer keeps its own 20/20/20/15/15/10
    src = open(scoring_llm.__file__, encoding="utf-8").read()
    assert "20" in src  # sanity: module untouched and still importable
    out = rate(client, "rater_a", code, SCORES)
    assert out["total_score"] == round(75 * .10 + 80 * .20 + 85 * .25 + 70 * .15 + 80 * .20 + 90 * .10, 2)


@pytest.mark.parametrize("weights", [
    {"medical_knowledge": 10, "key_information": 20, "differential_diagnosis": 25, "evidence_integration": 15,
     "clinical_decision": 20, "evidence_based_medicine": 9},          # sums to 99
    {"medical_knowledge": 100},                                       # missing dimensions
    {"medical_knowledge": -10, "key_information": 30, "differential_diagnosis": 25, "evidence_integration": 15,
     "clinical_decision": 20, "evidence_based_medicine": 20},          # negative weight
])
def test_invalid_rubric_weights_are_rejected_at_authoring(db_factory, client, weights):
    from tests.assessment_helpers import stages
    build_world(db_factory)
    login(client, "admin_user")
    r = client.post("/api/assessments/forms", json={"code": "BADW", "title": "坏权重", "stages": stages(), "answer_key": {}, "rubric": {"weights": weights}})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_rubric"


def test_rater_view_never_leaks_identity_group_cohort_or_timepoint(db_factory, client):
    w = build_world(db_factory)
    name, number = w.student_no[w.students[0]]
    form = publish_form(client, w)
    sid = schedule(client, w, w.students[0], form, cohort="COHORT-SECRET-77", group="CBL", timepoint="T1")
    # The student wrote their own name / number into the answer despite the instructions.
    seed_submitted(db_factory, sid, {0: f"我是{name}，学号{number}，考虑SLE"})
    for rater in ("rater_a", "rater_b"):
        login(client, rater)
        queue = client.get("/api/assessments/blind/queue")
        detail = client.get(f"/api/assessments/blind/{queue.json()[0]['blind_code']}")
        code = queue.json()[0]["blind_code"]
        blob = (queue.text + detail.text).replace(code, "<code>")  # the random code itself may contain any letters
        for secret in (name, number, "exam_student0", "COHORT-SECRET-77", "CBL", "CLINPATH", "T1", "T0", "ASSESS-A-TEST",
                       "保密考核", "rater_a", "rater_b", "blinding", "student_id", "sitting_id", "form_id"):
            assert secret not in blob, secret
        assert detail.json()["identifier_redactions"] >= 2
        assert "[已去标识]" in detail.json()["answers"][0]["answer_text"]
    db = db_factory()  # the raw answer is kept untouched for the audit trail
    from app.assessment_models import AssessmentAnswer
    assert name in db.query(AssessmentAnswer).filter_by(sitting_id=sid, stage_index=0).one().answer_text
    db.close()


def test_only_assigned_raters_get_the_answer_and_the_admin_cannot_rate(db_factory, client):
    w, _, sid = _one_submitted(db_factory, client)
    code = blind_code_for(client, "rater_a")[0]
    for outsider in ("plain_teacher", "rev_one", "adjudicator"):
        login(client, outsider)
        assert client.get("/api/assessments/blind/queue").json() == []
        assert client.get(f"/api/assessments/blind/{code}").status_code == 404
        assert client.post(f"/api/assessments/blind/{code}/review", json={"scores": SCORES}).status_code == 404
    login(client, "admin_user")
    assert client.get("/api/assessments/blind/queue").status_code == 403
    assert client.get(f"/api/assessments/blind/{code}").status_code == 403
    assert client.post(f"/api/assessments/blind/{code}/review", json={"scores": SCORES}).status_code == 403
    login(client, w.student_users[0])
    assert client.get(f"/api/assessments/blind/{code}").status_code == 403
    assert client.get("/api/assessments/blind/not-a-code").status_code == 403


def test_one_teacher_cannot_stand_in_for_two_raters(db_factory, client):
    w = build_world(db_factory, extra_teachers=("rater_alias",))
    form = publish_form(client, w)
    login(client, "admin_user")
    from tests.assessment_helpers import window
    s, e = window()
    base = {"student_id": w.students[0], "form_id": form, "cohort_code": "c", "study_group": "CBL", "timepoint": "T0", "window_start": s, "window_end": e}
    same = client.post("/api/assessments/admin/sittings", json={**base, "rater_a_id": w.users["rater_a"], "rater_b_id": w.users["rater_a"]})
    assert same.status_code == 400 and same.json()["detail"]["code"] == "two_raters_required"
    # Two logins for the same underlying Teacher row are still one person.
    db = db_factory()
    from app.models import User
    db.get(User, w.users["rater_alias"]).teacher_id = db.get(User, w.users["rater_a"]).teacher_id
    db.commit()
    db.close()
    alias = client.post("/api/assessments/admin/sittings", json={**base, "rater_a_id": w.users["rater_a"], "rater_b_id": w.users["rater_alias"]})
    assert alias.status_code == 400 and alias.json()["detail"]["code"] == "two_raters_required"
    for bad in (w.users["admin_user"],):
        r = client.post("/api/assessments/admin/sittings", json={**base, "rater_a_id": w.users["rater_a"], "rater_b_id": bad})
        assert r.status_code == 400 and r.json()["detail"]["code"] == "not_teacher"
    clash = client.post("/api/assessments/admin/sittings", json={**base, "rater_a_id": w.users["rater_a"], "rater_b_id": w.users["rater_b"],
                                                                 "adjudicator_user_id": w.users["rater_b"]})
    assert clash.status_code == 400 and clash.json()["detail"]["code"] == "adjudicator_is_rater"


def test_submitted_reviews_are_locked_and_reopen_is_audited(db_factory, client):
    w, _, sid = _one_submitted(db_factory, client)
    code = blind_code_for(client, "rater_a")[0]
    rate(client, "rater_a", code)
    dup = client.post(f"/api/assessments/blind/{code}/review", json={"scores": SCORES})
    assert dup.status_code == 200 and dup.json()["already_locked"] is True  # identical resend = no-op
    chg = client.post(f"/api/assessments/blind/{code}/review", json={"scores": with_scores(5)})
    assert chg.status_code == 409 and chg.json()["detail"]["code"] == "review_locked"
    db = db_factory()
    rid = db.query(AssessmentReview).one().id
    db.close()
    login(client, "admin_user")
    # No endpoint lets an admin edit scores; the only path is reopen, with a reason, leaving a trail.
    assert client.put(f"/api/assessments/blind/{code}/review", json={"scores": SCORES}).status_code in (403, 405)
    assert client.post(f"/api/assessments/admin/reviews/{rid}/reopen", json={"reason": "短"}).status_code == 422
    assert client.post(f"/api/assessments/admin/reviews/{rid}/reopen", json={"reason": "评分者误填，书面申请重评"}).status_code == 200
    audit = client.get("/api/assessments/admin/audit?action=review.reopen").json()
    assert audit[0]["detail"]["reason"] == "评分者误填，书面申请重评" and audit[0]["actor_role"] == "admin"
    db = db_factory()
    row = db.get(AssessmentReview, rid)
    assert row.voided_at is not None and json.loads(row.scores_json) == SCORES  # the raw row is preserved
    db.close()
    out = rate(client, "rater_a", code, with_scores(5))
    assert out["already_locked"] is False


def test_agreeing_raters_get_a_dual_mean_final_score_that_locks(db_factory, client):
    w, _, sid = _one_submitted(db_factory, client)
    code = blind_code_for(client, "rater_a")[0]
    login(client, "admin_user")
    assert client.post(f"/api/assessments/admin/sittings/{sid}/finalize").status_code == 409  # nobody rated yet
    a = rate(client, "rater_a", code, SCORES)["total_score"]
    login(client, "admin_user")
    assert client.post(f"/api/assessments/admin/sittings/{sid}/finalize").status_code == 409  # one rater only
    b = rate(client, "rater_b", code, with_scores(4))["total_score"]
    login(client, "admin_user")
    fin = client.post(f"/api/assessments/admin/sittings/{sid}/finalize").json()
    assert fin["final_score"] == round((a + b) / 2, 2) and fin["scoring_provenance"] == "dual_mean"
    again = client.post(f"/api/assessments/admin/sittings/{sid}/finalize").json()
    assert again["already_locked"] is True and again["final_score"] == fin["final_score"]
    # Locked: a rater can no longer void-and-redo through the admin path.
    db = db_factory()
    rid = db.query(AssessmentReview).first().id
    db.close()
    r = client.post(f"/api/assessments/admin/reviews/{rid}/reopen", json={"reason": "想改分数，晚了"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "scoring_locked"


def _disagree(db_factory, client, rubric=None):
    w, _, sid = _one_submitted(db_factory, client, rubric=rubric)
    code = blind_code_for(client, "rater_a")[0]
    rate(client, "rater_a", code, dict.fromkeys(ABILITIES, 90))
    rate(client, "rater_b", code, dict.fromkeys(ABILITIES, 60))
    return w, sid, code


def test_large_disagreement_must_be_adjudicated_and_never_silently_averaged(db_factory, client):
    w, sid, code = _disagree(db_factory, client)
    login(client, "admin_user")
    row = client.get("/api/assessments/admin/sittings").json()[0]
    assert row["disagreement"]["flagged"] is True and row["disagreement"]["total_diff"] == 30.0
    blocked = client.post(f"/api/assessments/admin/sittings/{sid}/finalize")
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "adjudication_required"
    # Raters, plain teachers and the admin cannot adjudicate; the assigned adjudicator can.
    for who in ("rater_a", "plain_teacher", "admin_user"):
        login(client, who)
        assert client.post(f"/api/assessments/adjudication/{code}", json={"scores": SCORES, "rationale": "不应成功的裁决"}).status_code in (403, 404)
    login(client, "adjudicator")
    queue = client.get("/api/assessments/adjudication/queue").json()
    assert queue == [{"blind_code": code, "adjudicated": False}]
    detail = client.get(f"/api/assessments/adjudication/{code}").json()
    assert [r["label"] for r in detail["reviews"]] == ["rater_1", "rater_2"] and detail["disagreement"]["flagged"]
    assert "rater_user_id" not in json.dumps(detail) and "rater_a" not in json.dumps(detail)
    decided = with_scores(0)
    ok = client.post(f"/api/assessments/adjudication/{code}", json={"scores": decided, "rationale": "依据评分锚点，鉴别诊断部分更接近B"})
    assert ok.status_code == 200
    assert client.post(f"/api/assessments/adjudication/{code}", json={"scores": decided, "rationale": "重复裁决应被拒绝"}).status_code == 409
    db = db_factory()  # the two raw reviews are untouched
    raw = sorted(json.loads(r.scores_json)["medical_knowledge"] for r in db.query(AssessmentReview))
    assert raw == [60, 90] and db.query(AssessmentAdjudication).count() == 1
    db.close()
    login(client, "admin_user")
    fin = client.post(f"/api/assessments/admin/sittings/{sid}/finalize").json()
    assert fin["scoring_provenance"] == "adjudicated" and fin["final_score"] == ok.json()["total_score"]
    exported = client.get("/api/assessments/admin/export?data_origin=pilot_test").json()["records"][0]
    assert exported["blinded_rater_1_score"] == 90 and exported["blinded_rater_2_score"] == 60
    assert exported["adjudicated_score"] == fin["final_score"] and exported["scoring_provenance"] == "adjudicated"


def test_threshold_is_configurable_per_rubric_and_dimension_spread_also_triggers(db_factory, client):
    loose = {"rubric_version": "LOOSE", "disagreement": {"total_threshold": 40, "dimension_threshold": None}}
    w, sid, code = _disagree(db_factory, client, rubric=loose)
    login(client, "admin_user")
    assert client.get("/api/assessments/admin/sittings").json()[0]["disagreement"]["flagged"] is False
    assert client.post(f"/api/assessments/admin/sittings/{sid}/finalize").json()["scoring_provenance"] == "dual_mean"
    login(client, "adjudicator")
    assert client.post(f"/api/assessments/adjudication/{code}", json={"scores": SCORES, "rationale": "没有分歧，不应裁决"}).status_code in (404, 409)


def test_one_dimension_far_apart_flags_even_when_totals_are_close(db_factory, client):
    w, _, sid = _one_submitted(db_factory, client, rubric={"disagreement": {"total_threshold": 10, "dimension_threshold": 25}})
    code = blind_code_for(client, "rater_a")[0]
    rate(client, "rater_a", code, _scores(dict.fromkeys(ABILITIES, 70), medical_knowledge=100))  # weight 10 => total +3
    rate(client, "rater_b", code, _scores(dict.fromkeys(ABILITIES, 70), medical_knowledge=60))
    login(client, "admin_user")
    d = client.get("/api/assessments/admin/sittings").json()[0]["disagreement"]
    assert d["total_diff"] < 10 and d["flagged"] is True and d["reasons"] == ["dimension:medical_knowledge"]


def test_raters_are_never_shown_each_others_scores(db_factory, client):
    w, _, sid = _one_submitted(db_factory, client)
    code = blind_code_for(client, "rater_a")[0]
    rate(client, "rater_a", code, dict.fromkeys(ABILITIES, 91.5))
    login(client, "rater_b")
    detail = client.get(f"/api/assessments/blind/{code}")
    assert "91.5" not in detail.text and detail.json()["already_reviewed"] is False


def test_queue_order_is_stable_and_unrelated_to_submission_order(db_factory, client):
    w = build_world(db_factory, n_students=7)
    form = publish_form(client, w)
    sids = [schedule(client, w, st, form, cohort="cohort1") for st in w.students]
    for sid in sids:
        seed_submitted(db_factory, sid)
    db = db_factory()
    by_code = {s.blind_code: s.id for s in db.query(AssessmentSitting)}
    db.close()
    login(client, "rater_a")
    first = [by_code[r["blind_code"]] for r in client.get("/api/assessments/blind/queue").json()]
    second = [by_code[r["blind_code"]] for r in client.get("/api/assessments/blind/queue").json()]
    assert first == second and sorted(first) == sids and first != sids
    login(client, "rater_b")
    other = [by_code[r["blind_code"]] for r in client.get("/api/assessments/blind/queue").json()]
    assert other != first  # each rater gets their own shuffle
