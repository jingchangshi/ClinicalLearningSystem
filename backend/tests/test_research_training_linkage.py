"""R9 §4: read-only Research linkage to the training and CBL teaching records.

The export is written by the Assessment domain; the process indicators are joined
by the Research layer from *stored rows only*. These tests use a real 7-cohort
study scaffold in an isolated database, drive the actual training routes (offline:
the scoring and tutor paths run their rule fallback), and then read the export.

What must hold: the numbers come from rows (not page views, not synthetic data);
missing records are reported as missing with a reason, never as zero; a malformed
or foreign teaching log is never applied; the Assessment score and the Training
score stay separate; the export writes nothing; and a frozen dataset keeps the
numbers it froze.
"""
import json
from datetime import datetime, timedelta

import pytest

from app.assessment_models import AssessmentSitting
from app.auth import hash_password
from app.core import ai_audit
from app.database import Base
from app.models import AIInvocation, CaseSession, Score, User
from app.research import DATA_ORIGIN_DEMO, MixedDataOriginError, ResearchError
from app.research import cohort_stats as cs
from app.research import dataset_export as de
from app.research import teaching_log as tl
from app.research.linkage import LINKAGE_VERSION
from tests.assessment_helpers import (
    SCORES, build_study, build_world, design_rows, login, post_schedule, publish_form, rate, sit_exam,
    study_windows,
)
from tests.factories import ANSWER_TEXTS, make_case, make_catalog
from tests.test_assessment_isolation import DOMAIN_PREFIXES, _training_snapshot

ORIGIN = "real_study"


@pytest.fixture(autouse=True)
def _hermetic_teaching_log(tmp_path, monkeypatch):
    """Never read the operator's real register from a test."""
    monkeypatch.setenv("CLINPATH_CBL_TEACHING_LOG", str(tmp_path / "absent.json"))


@pytest.fixture(autouse=True)
def audit_into_test_db(db_factory):
    """Point the AI audit writer at this test's database (as tests/test_ai_audit.py does)."""
    from sqlalchemy.orm import sessionmaker

    db = db_factory()
    engine = db.get_bind()
    db.close()
    previous = ai_audit._session_factory
    ai_audit.set_session_factory(sessionmaker(bind=engine, autoflush=False))
    try:
        yield
    finally:
        ai_audit.set_session_factory(previous)


class Study:
    pass


def _today():
    return datetime.utcnow().date()


def set_window(client, cohort_code, start_offset=-1, end_offset=1):
    login(client, "admin_user")
    r = client.post(f"/api/assessments/admin/cohorts/{cohort_code}/actual-dates",
                    json={"actual_start": str(_today() + timedelta(days=start_offset)),
                          "actual_end": str(_today() + timedelta(days=end_offset))})
    assert r.status_code == 200, r.text


def _add_login(db, student_id, username):
    db.add(User(username=username, password_hash=hash_password("secret1"), role="student",
                student_id=student_id))


def build(db_factory, client, window=(-1, 1)):
    """A 7-cohort study with frozen arms, two published forms and all 14 T0/T1 sittings."""
    w = build_world(db_factory, n_students=7, student_accounts=False)
    db = db_factory()
    case_a = make_case(db, title="训练病例A")
    case_b = make_case(db, title="训练病例B")
    make_catalog(db)
    case_ids = (case_a.id, case_b.id)
    db.commit()
    db.close()
    forms = {name: publish_form(client, w, code=f"ASSESS-{name}-TEST", tag=name[-2:])
             for name in ("A01", "A02")}
    codes = build_study(client, w, size=1)
    rows = design_rows(client)
    cp = next(r for r in rows if r["study_group"] == "CLINPATH")
    cbl = next(r for r in rows if r["study_group"] == "CBL")
    db = db_factory()
    _add_login(db, cp["student_id"], "cp_student")
    _add_login(db, cbl["student_id"], "cbl_student")
    db.commit()
    db.close()
    planned = post_schedule(client, w, forms, study_windows(codes))
    assert planned.status_code == 200, planned.text
    study = Study()
    study.w, study.codes, study.case_ids, study.cp, study.cbl = w, codes, case_ids, cp, cbl
    if window:
        for code in codes:
            set_window(client, code, *window)
    return study


def sitting_id(db_factory, student_id, timepoint="T0"):
    db = db_factory()
    try:
        return db.query(AssessmentSitting).filter_by(student_id=student_id, timepoint=timepoint).one().id
    finally:
        db.close()


def start(client, case_id):
    r = client.post("/api/sessions/start", json={"case_id": case_id})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def answer_all(client, session_id):
    for step, text in ANSWER_TEXTS.items():
        assert client.post(f"/api/sessions/{session_id}/answers",
                           json={"step": step, "answer_text": text}).status_code == 200


def train(client, case_id, *, coach=False):
    session_id = start(client, case_id)
    answer_all(client, session_id)
    if coach:
        # A deliberately thin answer keeps the tutor inside its coverage loop, so the
        # route really asks for a question (and writes one audit row) instead of
        # declaring the step covered.
        r = client.post(f"/api/sessions/{session_id}/coach",
                        json={"step": "differential_diagnosis", "answer_text": "不确定"})
        assert r.status_code == 200, r.text
        assert r.json()["message"]
    assert client.post(f"/api/sessions/{session_id}/submit").status_code == 200
    ai_audit.flush()
    return session_id


def latest_recommended_case(db_factory, student_id):
    from app.models import LearningRecommendation
    db = db_factory()
    try:
        row = (db.query(LearningRecommendation).filter_by(student_id=student_id)
               .order_by(LearningRecommendation.id.desc()).first())
        return row.recommended_case_id
    finally:
        db.close()


def add_intervention(client, student_id, kind="reinforce"):
    login(client, "plain_teacher")
    r = client.post("/api/teacher/interventions", json={
        "title": "夹具教师干预", "target_ability": "differential_diagnosis",
        "target_students": [student_id], "intervention_type": kind, "description": "测试夹具，非真实教学"})
    assert r.status_code == 200, r.text


def finalize(client, db_factory, sitting_id, a=85, b=95):
    db = db_factory()
    code = db.get(AssessmentSitting, sitting_id).blind_code
    db.close()
    rate(client, "rater_a", code, dict.fromkeys(SCORES, a))
    rate(client, "rater_b", code, dict.fromkeys(SCORES, b))
    login(client, "admin_user")
    assert client.post(f"/api/assessments/admin/sittings/{sitting_id}/finalize").status_code == 200


def export(client, origin=ORIGIN):
    login(client, "admin_user")
    r = client.get(f"/api/assessments/admin/export?data_origin={origin}")
    assert r.status_code == 200, r.text
    return r.json()


def record_for(export_body, cohort_code, timepoint="T0"):
    return next(r for r in export_body["records"]
                if r["cohort_id"] == cohort_code and r["timepoint"] == timepoint)


def write_log(tmp_path, monkeypatch, entries, origin=ORIGIN):
    path = tmp_path / "cbl_teaching_log.json"
    path.write_text(json.dumps({"teaching_log_version": tl.LOG_VERSION, "data_origin": origin,
                                "entries": entries}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("CLINPATH_CBL_TEACHING_LOG", str(path))
    return path


def entry(cohort_code, topic, minutes=60, day_offset=0, **extra):
    body = {"cohort_code": cohort_code, "date": str(_today() + timedelta(days=day_offset)),
            "case_topic": topic, "duration_minutes": minutes, "supervising_teacher": "测试教师",
            "completed": True, "overlaps_assessment_case_topic": False, "notes": "测试夹具，非真实教学"}
    body.update(extra)
    return body


# --- the ClinPath arm: real process indicators -------------------------------------

def test_clinpath_process_indicators_come_from_stored_rows(db_factory, client):
    study = build(db_factory, client)
    cp = study.cp
    login(client, "cp_student")
    first = train(client, study.case_ids[0], coach=True)
    second = train(client, latest_recommended_case(db_factory, cp["student_id"]))
    add_intervention(client, cp["student_id"])
    add_intervention(client, cp["student_id"], kind="follow_up")

    # An independent T0 assessment, scored by the two blind raters, is the only
    # number that may reach final_score.
    T0 = sitting_id(db_factory, cp["student_id"], "T0")
    sit_exam(client, "cp_student", T0)
    finalize(client, db_factory, T0, a=85, b=95)

    body = export(client)
    row = record_for(body, cp["cohort_code"])
    link = row["linkage"]
    process = link["clinpath_process"]

    assert process["status"] == "observed" and link["window"]["state"] == "open"
    assert process["completed_five_stage_runs"] == 2
    # Two runs over the same case count as one completed *case*: a repeat is not a second case.
    assert process["completed_formative_cases"] == 1
    assert [s["case_id"] for s in process["training_scores"]]  # real per-run dimension scores
    assert all({"total_score", "medical_knowledge", "evaluation_mode", "degraded"}
               <= set(score) for score in process["training_scores"])
    assert process["profile_evidence"]["evidence_events"] == 2
    assert process["profile_evidence"]["has_profile_row"] is True

    # AI usage vs shown questions are two different measures and are not summed.
    db = db_factory()
    invocations = (db.query(AIInvocation).filter(AIInvocation.task_type == "tutor_question").count())
    db.close()
    assert process["ai_tutor_invocations"] == invocations >= 1
    assert process["tutor_questions_shown"] >= 1
    assert process["rule_fallback_count"] >= 1  # no model configured: every AI task degraded
    assert process["rule_fallback_by_task"]["tutor_question"] >= 1
    assert process["d4_d5_recommendations"]["completion"]["denominator"] == 2
    assert process["d4_d5_recommendations"]["completion"]["numerator"] == 1
    assert process["teacher_interventions"]["count"] == 2
    assert set(process["teacher_interventions"]["types"]) == {"reinforce", "follow_up"}
    assert process["actual_training_window"]["first_started_at"] <= process["actual_training_window"]["last_completed_at"]

    # training_exposure and intervention_count are populated from those rows, not None.
    assert row["training_exposure"] == "clinpath_cases=1;five_stage_runs=2;ai_tutor_invocations=1"
    assert row["intervention_count"] == 2
    assert link["intervention_count"] == 2
    # The only gap on a ClinPath row is the CBL register, which this row never uses.
    assert link["missing"] == [{"indicator": "cbl_teaching", "reason": "cbl_teaching_log_not_registered"}]

    # Assessment and Training scores stay separate: 90 (dual-rated assessment) is not
    # the rule-based training score, and no training score is written into final_score.
    assert row["final_score"] == 90.0
    db = db_factory()
    training_totals = [s.total_score for s in db.query(Score).filter(
        Score.session_id.in_([first, second]))]
    db.close()
    assert training_totals and all(total != row["final_score"] for total in training_totals)
    assert [s["total_score"] for s in process["training_scores"]] == training_totals
    assert first != second


def test_sources_are_distinguished(db_factory, client):
    study = build(db_factory, client)
    body = export(client)
    provenance = body["provenance"]
    assert set(provenance) == {"independent_assessment", "training", "teaching_log",
                               "study_allocation", "research_metadata"}
    assert provenance["research_metadata"]["linkage_version"] == LINKAGE_VERSION
    assert provenance["teaching_log"]["status"] == tl.NOT_REGISTERED
    link = body["records"][0]["linkage"]
    assert set(link["sources"]) == {"independent_assessment", "training", "teaching_log",
                                    "study_allocation", "research_metadata"}
    for table in ("case_sessions", "scores", "tutor_turns", "ai_invocations", "learning_recommendations",
                  "learning_evidence_events", "teaching_interventions"):
        assert table in link["sources"]["training"]
    assert "cbl_teaching_log" in link["sources"]["teaching_log"]


# --- the CBL arm: a structured teaching register -----------------------------------

def test_cbl_teaching_log_feeds_the_export(db_factory, client, tmp_path, monkeypatch):
    study = build(db_factory, client)
    cohort = study.cbl["cohort_code"]
    write_log(tmp_path, monkeypatch, [
        entry(cohort, "发热伴皮疹的鉴别", 90),
        entry(cohort, "关节痛的多学科评估", 60, day_offset=-1, overlaps_assessment_case_topic=True),
        entry(study.cp["cohort_code"], "不属于本批次的记录", 30),
    ])
    body = export(client)
    row = record_for(body, cohort)
    teaching = row["linkage"]["cbl_teaching"]
    assert teaching["status"] == "observed"
    assert len(teaching["entries"]) == 2 and teaching["total_minutes"] == 150
    assert teaching["completed_sessions"] == 2 and teaching["overlap_days"] == 1
    # Entries are ordered by date: the day-before teaching comes first.
    assert teaching["case_topics"] == "关节痛的多学科评估;发热伴皮疹的鉴别"
    assert row["cbl_case_topics"] == teaching["case_topics"]
    assert row["training_exposure"] == "cbl_logged_sessions=2;minutes=150"
    assert body["provenance"]["teaching_log"]["status"] == tl.REGISTERED
    assert body["provenance"]["teaching_log"]["sha256"]
    # The ClinPath row is described by its training records, never by the CBL log.
    cp_row = record_for(body, study.cp["cohort_code"])
    assert cp_row["cbl_case_topics"] is None


def test_an_unregistered_log_is_not_no_teaching(db_factory, client):
    study = build(db_factory, client)
    body = export(client)
    row = record_for(body, study.cbl["cohort_code"])
    teaching = row["linkage"]["cbl_teaching"]
    assert teaching["status"] == tl.NOT_REGISTERED
    assert teaching["reason"] == "cbl_teaching_log_not_registered"
    assert "absence_of_a_log_entry_is_not_evidence_of_absence_of_teaching" == teaching["interpretation"]
    assert row["training_exposure"] is None and row["cbl_case_topics"] is None
    assert {"indicator": "cbl_teaching", "reason": "cbl_teaching_log_not_registered"} in row["linkage"]["missing"]
    # The frozen CSV reports the gap instead of filling it. (build_rows compares the
    # CSV contract's form code, so hand it the code column the export carries.)
    form_by_order = {"X": {"T0": "A01", "T1": "A02"}, "Y": {"T0": "A02", "T1": "A01"}}
    rows = de.build_rows([dict(r, batch_index=r["batch_index"] or 1,
                               assessment_form_id=form_by_order[r["form_order"]][r["timepoint"]])
                          for r in body["records"] if r["cohort_id"] != study.cp["cohort_code"]],
                         dataset_version="v1", data_origin=ORIGIN)
    missing = de.cbl_rows_missing_topics(rows)
    assert study.cbl["study_student_code"] in missing
    assert study.cp["study_student_code"] not in missing


def test_batch_index_comes_from_the_recorded_timetable(db_factory, client):
    study = build(db_factory, client)
    records = export(client)["records"]
    assert {r["batch_index"] for r in records} == set(range(1, len(study.codes) + 1))
    # A batch's index follows its recorded start date, not its code.
    order = {r["cohort_id"]: r["batch_index"] for r in records}
    db = db_factory()
    from app.assessment_models import StudyCohort
    starts = {c.cohort_code: (c.actual_start or c.planned_start) for c in db.query(StudyCohort)}
    db.close()
    assert sorted(order, key=lambda c: order[c]) == sorted(starts, key=lambda c: starts[c])


def test_a_foreign_origin_log_is_never_applied(db_factory, client, tmp_path, monkeypatch):
    study = build(db_factory, client)
    write_log(tmp_path, monkeypatch, [entry(study.cbl["cohort_code"], "合成演示病例", 90)],
              origin=DATA_ORIGIN_DEMO)
    row = record_for(export(client), study.cbl["cohort_code"])
    assert row["linkage"]["cbl_teaching"]["status"] == "origin_mismatch"
    assert row["training_exposure"] is None and row["cbl_case_topics"] is None


def test_a_malformed_log_is_refused_not_partially_used(tmp_path, monkeypatch):
    write_log(tmp_path, monkeypatch, [entry("C1", "有效主题", 60), {"cohort_code": "C1"}])
    log, status = tl.load()
    assert log is None and status.status == tl.INVALID and status.provenance()["status"] == tl.INVALID
    assert any("missing required field" in problem for problem in status.problems)
    assert "path" not in status.provenance()  # no local path frozen into a research artifact


# --- missing data is explicit -------------------------------------------------------

def test_an_unrecorded_window_is_undetermined_not_zero(db_factory, client):
    study = build(db_factory, client, window=None)
    row = record_for(export(client), study.cp["cohort_code"])
    link = row["linkage"]
    process = link["clinpath_process"]
    assert process["status"] == "undetermined"
    assert process["reason"] == "cohort_teaching_window_not_recorded"
    assert "observed_all_records" in process  # the rows are still reported, and labelled as unwindowed
    assert row["training_exposure"] is None and row["intervention_count"] is None
    assert {"indicator": "intervention_count", "reason": "cohort_teaching_window_not_recorded"} in link["missing"]
    assert row["missingness"] == "not_submitted"  # the assessment's own honesty is untouched


# --- read-only, reproducible, never mixed -------------------------------------------

def test_export_and_freeze_do_not_mutate_training_rows(db_factory, client):
    study = build(db_factory, client)
    login(client, "cp_student")
    train(client, study.case_ids[0])
    db = db_factory()
    before = _training_snapshot(db)
    db.close()
    export(client)
    login(client, "admin_user")
    assert client.post("/api/assessments/admin/dataset-locks",
                       json={"dataset_version": "ro-v1", "data_origin": ORIGIN,
                             "allow_incomplete": True}).status_code == 200
    db = db_factory()
    assert _training_snapshot(db) == before
    db.close()


def test_a_frozen_version_keeps_its_numbers(db_factory, client):
    study = build(db_factory, client)
    login(client, "cp_student")
    train(client, study.case_ids[0])
    login(client, "admin_user")
    assert client.post("/api/assessments/admin/dataset-locks",
                       json={"dataset_version": "frozen-v1", "data_origin": ORIGIN,
                             "allow_incomplete": True}).status_code == 200
    frozen = client.get("/api/assessments/admin/dataset-locks/frozen-v1").json()
    assert frozen["integrity_ok"] and frozen["snapshot"]["provenance"]["research_metadata"][
        "linkage_version"] == LINKAGE_VERSION
    frozen_row = record_for(frozen["snapshot"], study.cp["cohort_code"])

    # New training after the freeze changes the working export but never the lock.
    login(client, "cp_student")
    train(client, study.case_ids[1])
    working_row = record_for(export(client), study.cp["cohort_code"])
    assert working_row["linkage"]["clinpath_process"]["completed_five_stage_runs"] == 2
    assert frozen_row["linkage"]["clinpath_process"]["completed_five_stage_runs"] == 1
    again = client.get("/api/assessments/admin/dataset-locks/frozen-v1").json()
    assert again["snapshot"] == frozen["snapshot"] and again["sha256"] == frozen["sha256"]


def test_the_same_state_produces_the_same_rows(db_factory, client):
    study = build(db_factory, client)
    login(client, "cp_student")
    train(client, study.case_ids[0])
    first = export(client)["records"]
    second = export(client)["records"]
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert [r for r in first if r["cohort_id"] == study.cp["cohort_code"]][0]["training_exposure"] == \
        "clinpath_cases=1;five_stage_runs=1;ai_tutor_invocations=0"


# --- statistics accept the real export shape ----------------------------------------

def test_stats_accept_the_real_export_shape(db_factory, client):
    study = build(db_factory, client)
    records = export(client)["records"]
    rows = cs.student_scores_from_export(records, require=ORIGIN)
    assert len(rows) == 7 and {r.cohort_id for r in rows} == set(study.codes)
    assert all(r.t0 is None and r.t1 is None for r in rows)
    stats = cs.per_cohort_stats(rows)
    assert set(stats) == set(study.codes) and all(s["n_paired"] == 0 for s in stats.values())
    missing = cs.missingness(rows)
    assert missing["n"] == 7 and missing["proportion_incomplete"] == 1.0
    assert missing["by_reason"] == {"not_submitted": 7}
    with pytest.raises(ResearchError):
        cs.cohort_changes(stats)  # no paired student anywhere: the analysis is blocked, not faked


def test_stats_shape_guards():
    base = {"study_student_code": "S1", "cohort_id": "C1", "timepoint": "T0", "form_order": "X",
            "final_score": 70.0, "missingness": "observed", "data_origin": ORIGIN,
            "training_exposure": "clinpath_cases=1", "linkage": {"anything": True}}
    rows = cs.student_scores_from_export([base, dict(base, timepoint="T1", final_score=None,
                                                     missingness="absent")])
    assert len(rows) == 1 and rows[0].t0 == 70.0 and rows[0].t1 is None and rows[0].missing_reason == "absent"
    with pytest.raises(ResearchError):
        cs.student_scores_from_export([dict(base, form_order=None)])
    with pytest.raises(ResearchError):
        cs.student_scores_from_export([dict(base, cohort_id="")])
    with pytest.raises(ResearchError):
        cs.student_scores_from_export([base, dict(base)])  # duplicate student x timepoint
    with pytest.raises(ResearchError):
        cs.student_scores_from_export([base, dict(base, timepoint="T1", data_origin=DATA_ORIGIN_DEMO)])
    with pytest.raises(MixedDataOriginError):
        cs.student_scores_from_export([base], require=DATA_ORIGIN_DEMO)
