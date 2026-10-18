"""R2.2/R2.3: server-driven stages, drafts, idempotency, windows and UTC, retakes."""
import threading
from datetime import timedelta

from fastapi.testclient import TestClient

from app.assessment_models import (
    AssessmentAnswer, AssessmentAnswerRevision, AssessmentEvent, AssessmentReview, AssessmentSitting,
)
from tests.assessment_helpers import (
    build_world, blind_code_for, iso, login, now_utc, publish_form, rate, schedule, sit_exam, window,
)


def _setup(db_factory, client, **kw):
    w = build_world(db_factory, **kw.pop("world", {}))
    form = publish_form(client, w)
    sid = schedule(client, w, w.students[0], form, **kw)
    login(client, w.student_users[0])
    return w, form, sid


def _events(db_factory, sid):
    db = db_factory()
    try:
        return [e.event_type for e in db.query(AssessmentEvent).filter_by(sitting_id=sid).order_by(AssessmentEvent.id)]
    finally:
        db.close()


def test_content_requires_start_and_future_stages_are_unreachable(db_factory, client):
    _, _, sid = _setup(db_factory, client)
    before = client.get(f"/api/assessments/my/{sid}").json()
    assert before["can_start"] is True and "stage" not in before and "A信息0" not in str(before)
    assert client.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": 0, "answer_text": "x"}).status_code == 409
    client.post(f"/api/assessments/my/{sid}/start")
    skip = client.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": 3, "answer_text": "skip"})
    assert skip.status_code == 409 and skip.json()["detail"]["code"] == "stage_skip"
    assert "stage_skip_refused" in _events(db_factory, sid)
    view = client.get(f"/api/assessments/my/{sid}").json()
    assert view["completed"] == 0 and "A信息1" not in str(view)
    assert client.put(f"/api/assessments/my/{sid}/draft", json={"stage_index": 2, "answer_text": "d"}).status_code == 409
    assert client.post(f"/api/assessments/my/{sid}/answer", json={"answer_text": "no index"}).status_code == 422
    assert client.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": 9, "answer_text": "x"}).status_code == 422


def test_stage_answer_is_idempotent_and_immutable(db_factory, client):
    _, _, sid = _setup(db_factory, client)
    client.post(f"/api/assessments/my/{sid}/start")
    body = {"stage_index": 0, "answer_text": "第一阶段答案"}
    first = client.post(f"/api/assessments/my/{sid}/answer", json=body).json()
    again = client.post(f"/api/assessments/my/{sid}/answer", json=body).json()  # double click
    assert first["completed"] == again["completed"] == 1
    assert first["idempotent"] is False and again["idempotent"] is True
    changed = client.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": 0, "answer_text": "改答案"})
    assert changed.status_code == 409 and changed.json()["detail"]["code"] == "answer_immutable"
    db = db_factory()
    assert db.query(AssessmentAnswer).filter_by(sitting_id=sid).count() == 1
    assert db.get(AssessmentSitting, sid).stage_index == 1
    revs = db.query(AssessmentAnswerRevision).filter_by(sitting_id=sid).all()
    assert [r.kind for r in revs] == ["final"]
    db.close()


def test_draft_save_survives_refresh_and_keeps_history(db_factory, client):
    w, _, sid = _setup(db_factory, client)
    client.post(f"/api/assessments/my/{sid}/start")
    d1 = client.put(f"/api/assessments/my/{sid}/draft", json={"stage_index": 0, "answer_text": "草稿一"})
    assert d1.status_code == 200 and d1.json()["unchanged"] is False
    assert client.put(f"/api/assessments/my/{sid}/draft", json={"stage_index": 0, "answer_text": "草稿一"}).json()["unchanged"] is True
    client.put(f"/api/assessments/my/{sid}/draft", json={"stage_index": 0, "answer_text": "草稿二"})
    # "Network drop": a brand-new session logs in and resumes.
    with TestClient(client.app) as other:
        login(other, w.student_users[0])
        view = other.get(f"/api/assessments/my/{sid}").json()
        assert view["draft"]["answer_text"] == "草稿二" and view["stage"]["index"] == 0
        resumed = other.post(f"/api/assessments/my/{sid}/start").json()
        assert resumed["draft"]["answer_text"] == "草稿二"
        other.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": 0, "answer_text": "最终答案"})
        view = other.get(f"/api/assessments/my/{sid}").json()
        assert view["history"][0]["answer_text"] == "最终答案" and view["draft"] is None
    db = db_factory()
    kinds = [r.kind for r in db.query(AssessmentAnswerRevision).filter_by(sitting_id=sid).order_by(AssessmentAnswerRevision.id)]
    assert kinds == ["draft", "draft", "final"]
    db.close()
    assert "resumed" in _events(db_factory, sid)


def test_submit_is_idempotent_and_locks_the_sitting(db_factory, client):
    w, _, sid = _setup(db_factory, client)
    client.post(f"/api/assessments/my/{sid}/start")
    assert client.post(f"/api/assessments/my/{sid}/submit").status_code == 409  # not all stages
    sit_exam(client, w.student_users[0], sid)
    again = client.post(f"/api/assessments/my/{sid}/submit")
    assert again.status_code == 200 and again.json()["already_submitted"] is True
    assert _events(db_factory, sid).count("submitted") == 1
    assert client.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": 4, "answer_text": "晚了"}).status_code == 409
    assert client.put(f"/api/assessments/my/{sid}/draft", json={"stage_index": 4, "answer_text": "晚了"}).status_code == 409
    assert client.get("/api/assessments/my").json()[0]["status"] == "submitted"


def test_concurrent_duplicate_stage_posts_record_one_answer(db_factory, client):
    w, _, sid = _setup(db_factory, client)
    client.post(f"/api/assessments/my/{sid}/start")
    results = []

    def fire(text):
        with TestClient(client.app) as c:
            login(c, w.student_users[0])
            barrier.wait()
            results.append(c.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": 0, "answer_text": text}).status_code)

    barrier = threading.Barrier(2)
    threads = [threading.Thread(target=fire, args=("并发同一答案",)) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results == [200, 200]
    db = db_factory()
    assert db.query(AssessmentAnswer).filter_by(sitting_id=sid).count() == 1
    assert db.get(AssessmentSitting, sid).stage_index == 1
    db.close()
    # Two *different* answers racing: exactly one wins, the other is refused, never both.
    results.clear()
    barrier = threading.Barrier(2)
    threads = [threading.Thread(target=fire_idx, args=(client, w, sid, t, results, barrier)) for t in ("甲", "乙")]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == [200, 409]
    db = db_factory()
    assert db.query(AssessmentAnswer).filter_by(sitting_id=sid, stage_index=1).count() == 1
    db.close()


def fire_idx(client, w, sid, text, results, barrier):
    with TestClient(client.app) as c:
        login(c, w.student_users[0])
        barrier.wait()
        results.append(c.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": 1, "answer_text": text}).status_code)


def test_window_is_utc_and_timezone_aware_input_is_required(db_factory, client):
    w = build_world(db_factory)
    form = publish_form(client, w)
    login(client, "admin_user")
    n = now_utc()
    base = {"student_id": w.students[0], "form_id": form, "cohort_code": "c", "study_group": "CBL", "timepoint": "T0",
            "rater_a_id": w.users["rater_a"], "rater_b_id": w.users["rater_b"]}
    naive = client.post("/api/assessments/admin/sittings", json={**base, "window_start": n.isoformat(),
                                                                "window_end": (n + timedelta(hours=1)).isoformat()})
    assert naive.status_code == 422  # a bare local time is ambiguous; refuse to guess
    # +08:00 wall-clock that is already 5 minutes in the past in UTC terms.
    local = (n + timedelta(hours=8) - timedelta(minutes=5)).isoformat() + "+08:00"
    end = (n + timedelta(hours=9)).isoformat() + "+08:00"
    ok = client.post("/api/assessments/admin/sittings", json={**base, "window_start": local, "window_end": end})
    assert ok.status_code == 200, ok.text
    sid = ok.json()["id"]
    db = db_factory()
    s = db.get(AssessmentSitting, sid)
    assert abs((s.window_start - (n - timedelta(minutes=5))).total_seconds()) < 5  # stored as naive UTC
    db.close()
    login(client, w.student_users[0])
    view = client.get(f"/api/assessments/my/{sid}").json()
    assert view["window_end"].endswith("Z") and view["server_time"].endswith("Z")


def test_window_closed_before_open_and_after_close(db_factory, client):
    w = build_world(db_factory)
    form = publish_form(client, w)
    future = schedule(client, w, w.students[0], form, start=30, end=90)
    login(client, w.student_users[0])
    assert client.get("/api/assessments/my").json() == []  # unreleased schedule stays hidden
    r = client.get(f"/api/assessments/my/{future}")
    assert r.status_code == 403 and r.json()["detail"]["code"] == "window_not_open"
    assert client.post(f"/api/assessments/my/{future}/start").status_code == 403


def test_timeout_is_recorded_drafts_kept_and_extension_reopens(db_factory, client):
    w, _, sid = _setup(db_factory, client)
    client.post(f"/api/assessments/my/{sid}/start")
    client.put(f"/api/assessments/my/{sid}/draft", json={"stage_index": 0, "answer_text": "未交草稿"})
    db = db_factory()
    s = db.get(AssessmentSitting, sid)
    s.window_end = now_utc() - timedelta(seconds=1)  # the clock ran out mid-exam
    db.commit()
    db.close()
    late = client.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": 0, "answer_text": "迟交"})
    assert late.status_code == 403 and late.json()["detail"]["code"] == "window_closed"
    assert client.put(f"/api/assessments/my/{sid}/draft", json={"stage_index": 0, "answer_text": "迟存"}).status_code == 403
    assert client.post(f"/api/assessments/my/{sid}/submit").status_code == 403
    view = client.get(f"/api/assessments/my/{sid}")
    assert view.status_code == 200 and view.json()["status"] == "expired" and "stage" not in view.json()
    ev = _events(db_factory, sid)
    assert ev.count("window_expired") == 1 and "late_write_refused" in ev
    db = db_factory()
    assert db.query(AssessmentAnswer).filter_by(sitting_id=sid).count() == 0
    assert [r.answer_text for r in db.query(AssessmentAnswerRevision).filter_by(sitting_id=sid)] == ["未交草稿"]
    db.close()
    # A controlled extension (audited) lets the same attempt continue from its draft.
    login(client, "admin_user")
    bad = client.post(f"/api/assessments/admin/sittings/{sid}/extend", json={"new_window_end": iso(now_utc() - timedelta(hours=1)), "reason": "过去的时间"})
    assert bad.status_code == 400
    ok = client.post(f"/api/assessments/admin/sittings/{sid}/extend",
                     json={"new_window_end": iso(now_utc() + timedelta(minutes=30)), "reason": "网络故障，已核实"})
    assert ok.status_code == 200 and ok.json()["status"] == "in_progress"
    login(client, w.student_users[0])
    assert client.get(f"/api/assessments/my/{sid}").json()["draft"]["answer_text"] == "未交草稿"
    assert client.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": 0, "answer_text": "续答"}).status_code == 200
    login(client, "admin_user")
    audit = client.get("/api/assessments/admin/audit?action=sitting.extend").json()
    assert audit and audit[0]["detail"]["reason"] == "网络故障，已核实"


def test_interruption_report_and_sweep(db_factory, client):
    w, _, sid = _setup(db_factory, client)
    client.post(f"/api/assessments/my/{sid}/start")
    assert client.post(f"/api/assessments/my/{sid}/interruption", json={"reason": "校园网中断"}).status_code == 200
    assert "interruption_reported" in _events(db_factory, sid)
    db = db_factory()
    db.get(AssessmentSitting, sid).window_end = now_utc() - timedelta(minutes=1)
    db.commit()
    db.close()
    login(client, "admin_user")
    assert client.post("/api/assessments/admin/sweep-expired").json() == {"expired": 1}
    assert client.post("/api/assessments/admin/sweep-expired").json() == {"expired": 0}
    detail = client.get(f"/api/assessments/admin/sittings/{sid}").json()
    assert detail["status"] == "expired" and [e["type"] for e in detail["events"]].count("window_expired") == 1


def test_students_cannot_touch_each_others_sittings(db_factory, client):
    w = build_world(db_factory, n_students=2)
    form = publish_form(client, w)
    sid = schedule(client, w, w.students[0], form)
    login(client, w.student_users[1])
    for method, path, body in (("get", "", None), ("post", "/start", None), ("post", "/submit", None),
                               ("put", "/draft", {"stage_index": 0, "answer_text": "x"}),
                               ("post", "/answer", {"stage_index": 0, "answer_text": "x"})):
        r = getattr(client, method)(f"/api/assessments/my/{sid}{path}", **({"json": body} if body else {}))
        assert r.status_code == 404, (path, r.status_code)
    assert client.get("/api/assessments/my").json() == []


def test_controlled_retake_voids_the_old_attempt_and_keeps_one_live(db_factory, client):
    w, form, sid = _setup(db_factory, client)
    sit_exam(client, w.student_users[0], sid)
    login(client, "admin_user")
    s, e = window()
    # A scored attempt can never be retaken.
    code = blind_code_for(client, "rater_a")[0]
    rate(client, "rater_a", code)
    login(client, "admin_user")
    refused = client.post(f"/api/assessments/admin/sittings/{sid}/retake", json={"reason": "学生想要重新考试", "window_start": s, "window_end": e})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "already_scored"
    # Void the unscored review first (audited), then retake.
    db = db_factory()
    rid = db.query(AssessmentReview).one().id
    db.close()
    assert client.post(f"/api/assessments/admin/reviews/{rid}/reopen", json={"reason": "录入错误，评分者要求重评"}).status_code == 200
    ok = client.post(f"/api/assessments/admin/sittings/{sid}/retake", json={"reason": "考试期间机房断电，已核实", "window_start": s, "window_end": e})
    assert ok.status_code == 200, ok.text
    new_id = ok.json()["id"]
    assert ok.json()["attempt_no"] == 2
    db = db_factory()
    old = db.get(AssessmentSitting, sid)
    new = db.get(AssessmentSitting, new_id)
    assert old.status == "voided" and new.retake_of_id == sid and new.blind_code != old.blind_code
    live = db.query(AssessmentSitting).filter(AssessmentSitting.status != "voided").count()
    assert live == 1
    db.close()
    login(client, w.student_users[0])
    assert client.get(f"/api/assessments/my/{sid}").status_code == 404  # the voided attempt is gone for the student
    assert [x["id"] for x in client.get("/api/assessments/my").json()] == [new_id]
    login(client, "admin_user")
    rows = client.get("/api/assessments/admin/export?data_origin=pilot_test").json()["records"]
    assert len(rows) == 1 and rows[0]["attempt_no"] == 2
