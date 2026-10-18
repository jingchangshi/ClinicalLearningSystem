"""Shared fixtures for the independent-assessment tests.

Every account here is a clearly named TEST fixture; none represents a real teacher
or student, and the "approvals" they give are exercises of the review API only.
"""
from datetime import datetime, timedelta, timezone

from app.auth import hash_password
from app.models import Teacher, User
from tests.factories import make_student

ABILITIES = ("medical_knowledge", "key_information", "differential_diagnosis",
             "evidence_integration", "clinical_decision", "evidence_based_medicine")
SCORES = {"medical_knowledge": 75, "key_information": 80, "differential_diagnosis": 85,
          "evidence_integration": 70, "clinical_decision": 80, "evidence_based_medicine": 90}
SECRET_KEY = {"diagnosis": "HIDDEN-REFERENCE-DIAGNOSIS", "plan": "HIDDEN-REFERENCE-PLAN"}
ANCHORS = {"differential_diagnosis": "ANCHOR-TEXT-ONLY-FOR-RATERS"}


def stages(tag="A"):
    return [{"title": f"{tag}阶段{i}", "clinical_information": f"{tag}信息{i}", "question": f"{tag}问题{i}"}
            for i in range(5)]


def iso(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat()


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def window(start_min=-1, end_min=120):
    n = now_utc()
    return iso(n + timedelta(minutes=start_min)), iso(n + timedelta(minutes=end_min))


class World:
    pass


def build_world(db_factory, n_students=1, extra_teachers=(), student_accounts=True):
    db = db_factory()
    w = World()
    w.students, w.student_users = [], []
    for i in range(n_students):
        st, u = make_student(db, name=f"测试学生{i}", username=f"exam_student{i}" if student_accounts else None)
        w.students.append(st.id)
        w.student_users.append(u.username if u else None)
    w.users = {}
    for name in ("admin_user", "rev_one", "rev_two", "rater_a", "rater_b", "adjudicator", "plain_teacher", *extra_teachers):
        role = "admin" if name == "admin_user" else "teacher"
        teacher = None
        if role == "teacher":
            teacher = Teacher(name=name, teacher_no=name, department="TEST")
            db.add(teacher)
            db.flush()
        user = User(username=name, password_hash=hash_password("secret1"), role=role,
                    teacher_id=teacher.id if teacher else None)
        db.add(user)
        db.flush()
        w.users[name] = user.id
    db.commit()
    w.student_no = {}
    from app.models import Student
    for sid in w.students:
        s = db.get(Student, sid)
        w.student_no[sid] = (s.name, s.student_no)
    db.close()
    w.db_factory = db_factory
    return w


def login(client, name):
    r = client.post("/api/auth/login", json={"username": name, "password": "secret1"})
    assert r.status_code == 200, r.text


def publish_form(client, w, code="ASSESS-A-TEST", tag="A", rubric=None):
    login(client, "admin_user")
    r = client.post("/api/assessments/forms", json={
        "code": code, "title": f"保密考核{tag}", "stages": stages(tag),
        "answer_key": SECRET_KEY, "rubric": rubric if rubric is not None else {"anchors": ANCHORS}})
    assert r.status_code == 200, r.text
    fid = r.json()["id"]
    assert client.post(f"/api/assessments/forms/{fid}/approve").status_code == 409
    r = client.post(f"/api/assessments/forms/{fid}/reviewers",
                    json={"teacher_user_ids": [w.users["rev_one"], w.users["rev_two"]]})
    assert r.status_code == 200, r.text
    for name in ("rev_one", "rev_two"):
        login(client, name)
        r = client.post(f"/api/assessments/forms/{fid}/review",
                        json={"decision": "approve", "comment": "测试夹具：非真实医师签名"})
        assert r.status_code == 200, r.text
    login(client, "admin_user")
    r = client.post(f"/api/assessments/forms/{fid}/approve")
    assert r.status_code == 200, r.text
    return fid


def schedule(client, w, student_id, form_id, timepoint="T0", cohort="cohort1", group="CLINPATH", start=-1, end=120,
             adjudicator=True, **extra):
    login(client, "admin_user")
    s, e = window(start, end)
    body = {"student_id": student_id, "form_id": form_id, "cohort_code": cohort, "study_group": group,
            "timepoint": timepoint, "window_start": s, "window_end": e,
            "rater_a_id": w.users["rater_a"], "rater_b_id": w.users["rater_b"]}
    if adjudicator:
        body["adjudicator_user_id"] = w.users["adjudicator"]
    body.update(extra)
    r = client.post("/api/assessments/admin/sittings", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def sit_exam(client, username, sitting_id, prefix="答"):
    login(client, username)
    assert client.post(f"/api/assessments/my/{sitting_id}/start").status_code == 200
    for i in range(5):
        r = client.post(f"/api/assessments/my/{sitting_id}/answer", json={"stage_index": i, "answer_text": f"{prefix}{i}"})
        assert r.status_code == 200, r.text
    r = client.post(f"/api/assessments/my/{sitting_id}/submit")
    assert r.status_code == 200, r.text


def blind_code_for(client, rater):
    login(client, rater)
    q = client.get("/api/assessments/blind/queue").json()
    return [row["blind_code"] for row in q]


def rate(client, rater, code, scores=None):
    login(client, rater)
    r = client.post(f"/api/assessments/blind/{code}/review", json={"scores": scores or SCORES})
    assert r.status_code == 200, r.text
    return r.json()


def with_scores(delta=0, **overrides):
    s = {k: min(100, max(0, v + delta)) for k, v in SCORES.items()}
    s.update(overrides)
    return s


def seed_submitted(db_factory, sitting_id, texts=None):
    """Mark a sitting as submitted with five answers, without bcrypt logins (fast path for bulk tests)."""
    from app.assessment_models import AssessmentAnswer, AssessmentSitting
    from app.assessment.audit import sha256_text
    db = db_factory()
    s = db.get(AssessmentSitting, sitting_id)
    for i in range(5):
        t = (texts or {}).get(i, f"回答{i}")
        db.add(AssessmentAnswer(sitting_id=s.id, stage_index=i, answer_text=t, answer_sha256=sha256_text(t)))
    s.status, s.stage_index, s.started_at, s.submitted_at = "submitted", 5, now_utc(), now_utc()
    db.commit()
    db.close()


# --- the 7-batch study scaffold -------------------------------------------------

STUDY_ORIGIN = "real_study"


def build_study(client, w, n_cohorts=7, size=7, origin=STUDY_ORIGIN, seed="study-seed-1", protocol="v4",
                freeze=True, code_prefix="C", student_offset=0):
    """Register ``n_cohorts`` complete cohorts and (by default) freeze both research draws.

    Enrollment happens before either draw, exactly as the protocol requires (form
    order first, then the cluster-group allocation). Returns the cohort codes.
    """
    assert len(w.students) >= student_offset + n_cohorts * size, "build_world needs enough students"
    login(client, "admin_user")
    codes = []
    for i in range(n_cohorts):
        code = f"{code_prefix}{i + 1}"
        r = client.post("/api/assessments/admin/cohorts", json={
            "cohort_code": code, "label": f"批次{code}", "expected_size": size, "data_origin": origin})
        assert r.status_code == 200, r.text
        slice_ = w.students[student_offset + i * size:student_offset + (i + 1) * size]
        r = client.post(f"/api/assessments/admin/cohorts/{code}/enrollments", json={"student_ids": slice_})
        assert r.status_code == 200, r.text
        codes.append(code)
    if not freeze:
        return codes
    r = client.post("/api/assessments/admin/allocations/form-order",
                    json={"data_origin": origin, "protocol_version": protocol, "seed": seed + "-order"})
    assert r.status_code == 200, r.text
    r = client.post("/api/assessments/admin/allocations/cluster",
                    json={"data_origin": origin, "protocol_version": protocol, "mode": "randomized",
                          "seed": seed + "-group"})
    assert r.status_code == 200, r.text
    return codes


def _win(start_min, end_min):
    s, e = window(start_min, end_min)
    return {"start": s, "end": e}


def study_windows(codes, t0=(-1, 120), t1=(121, 600)):
    """One T0 and one T1 window per cohort, with T0 closing before T1 opens."""
    return {code: {"T0": _win(*t0), "T1": _win(*t1)} for code in codes}


def post_schedule(client, w, forms, windows, **extra):
    login(client, "admin_user")
    body = {"data_origin": STUDY_ORIGIN, "forms": forms, "windows": windows,
            "rater_a_id": w.users["rater_a"], "rater_b_id": w.users["rater_b"],
            "adjudicator_user_id": w.users["adjudicator"]}
    body.update(extra)
    return client.post("/api/assessments/admin/design/schedule", json=body)


def design_rows(client, origin=STUDY_ORIGIN):
    login(client, "admin_user")
    r = client.get(f"/api/assessments/admin/design/assignments?data_origin={origin}")
    assert r.status_code == 200, r.text
    return r.json()


def scheduled_rows(db_factory):
    """(student_id, timepoint) -> (form_id, form_order, study_group, cohort_code) as stored."""
    from app.assessment_models import AssessmentSitting
    db = db_factory()
    rows = {(s.student_id, s.timepoint): (s.form_id, s.form_order, s.study_group, s.cohort_code)
            for s in db.query(AssessmentSitting).filter(AssessmentSitting.status != "voided")}
    db.close()
    return rows

