"""Work package D: the synthetic research demo must stay synthetic.

The interesting failure mode here is not a crash — it is a page that quietly
presents seeded numbers as a real teaching study. These tests pin four things:

1. the served statistics reproduce the offline generator's workbook,
2. the demo router never touches the application database,
3. the synthetic markers survive every surface (API, CSV header, CSV rows),
4. authorization matches the rest of the teacher area.
"""

from __future__ import annotations

import csv
import io
import math

import pytest

from app.auth import create_access_token
from app.models import (
    CaseSession,
    LearningEvidenceEvent,
    Student,
    TeacherScoreReview,
    User,
)
from app.services import demo_research


@pytest.fixture(scope="module")
def dataset() -> demo_research.DemoDataset:
    return demo_research.load_dataset()


def _login(client, db_factory, username: str, role: str) -> None:
    db = db_factory()
    try:
        user = User(username=username, password_hash="x", role=role)
        db.add(user)
        db.commit()
        token = create_access_token(user)
    finally:
        db.close()
    client.cookies.set("access_token", token)


# --- data integrity ---------------------------------------------------------


def test_dataset_shape_matches_the_offline_package(dataset):
    participants = dataset.participants
    assert len(participants) == 60
    assert len({row["study_id"] for row in participants}) == 60

    groups = [row["group"] for row in participants]
    assert groups.count("CBL") == 30
    assert groups.count("CLINPATH") == 30

    # Exactly one T0 and one T1 per participant, and nothing else.
    per_student: dict[str, list[str]] = {}
    for row in dataset.assessments:
        per_student.setdefault(row["study_id"], []).append(row["timepoint"])
    assert len(per_student) == 60
    assert all(sorted(timepoints) == ["T0", "T1"] for timepoints in per_student.values())
    assert len(dataset.assessments) == 120

    assert len(dataset.sessions) == 180
    assert len(dataset.reasoning_steps) == 450


def test_every_row_is_marked_synthetic_and_raters_are_not_human(dataset):
    for row in dataset.participants + dataset.assessments + dataset.sessions + dataset.reasoning_steps:
        assert row["data_origin"] == demo_research.DATA_ORIGIN
    for row in dataset.assessments:
        assert row["rater_origin"] == demo_research.RATER_ORIGIN
        assert "REAL" not in row["rater_origin"]


def test_reasoning_steps_are_traceable_to_a_session(dataset):
    session_ids = {row["session_id"] for row in dataset.sessions}
    for row in dataset.reasoning_steps:
        assert row["session_id"] in session_ids
        assert row["is_real_student"] == "NO"
        session = next(s for s in dataset.sessions if s["session_id"] == row["session_id"])
        assert session["study_id"] == row["study_id"]

    # Every ClinPath-arm session has all five stages; CBL sessions have none.
    steps_per_session: dict[str, int] = {}
    for row in dataset.reasoning_steps:
        steps_per_session[row["session_id"]] = steps_per_session.get(row["session_id"], 0) + 1
    assert set(steps_per_session.values()) == {5}
    assert len(steps_per_session) == 90


def test_statistics_reproduce_the_offline_workbook(dataset):
    summary = demo_research.compute_summary(dataset)
    offline = dataset.offline_metrics

    for group in ("CBL", "CLINPATH"):
        served = summary["groups"][group]
        expected = offline["groups"][group]
        for field in ("n", "pre_mean", "post_mean", "gain_mean", "gain_sd"):
            assert served[field] == pytest.approx(expected[field], abs=1e-9), (group, field)

    reference = offline["illustrative_statistics"]
    assert summary["difference"]["value"] == pytest.approx(
        reference["gain_diff_clinpath_minus_cbl"], abs=0.005
    )
    assert summary["difference"]["welch_t"] == pytest.approx(reference["welch_t_stat"], abs=0.001)
    assert summary["difference"]["ci95"] == pytest.approx(reference["gain_diff_ci95"], abs=0.005)
    # P-values span 20 orders of magnitude; compare on the log scale.
    assert math.log10(summary["difference"]["welch_p"]) == pytest.approx(
        math.log10(reference["welch_t_p"]), abs=0.001
    )
    assert summary["ancova"]["value"] == pytest.approx(
        reference["ancova_clinpath_effect_adjusting_T0"], abs=0.005
    )
    assert summary["ancova"]["ci95"] == pytest.approx(reference["ancova_ci95"], abs=0.005)
    assert math.log10(summary["ancova"]["p_value"]) == pytest.approx(
        math.log10(reference["ancova_hc3_p"]), abs=0.001
    )


def test_summary_always_states_that_the_effect_was_assumed(dataset):
    summary = demo_research.compute_summary(dataset)
    assert "模拟" in summary["difference"]["label"]
    assert "不能作为真实教学效果的证据" in summary["analysis_note"]
    assert summary["scenario"]["nominal_CLINPATH_gain"] > summary["scenario"]["nominal_CBL_gain"]


# --- isolation from the application database --------------------------------


def test_demo_router_never_touches_the_database(client, db_factory, dataset):
    _login(client, db_factory, "teacher_demo_readonly", "teacher")
    db = db_factory()
    try:
        before = {
            "students": db.query(Student).count(),
            "case_sessions": db.query(CaseSession).count(),
            "learning_evidence_events": db.query(LearningEvidenceEvent).count(),
            "teacher_score_reviews": db.query(TeacherScoreReview).count(),
        }
    finally:
        db.close()

    for path in (
        "/api/teacher/demo-research/meta",
        "/api/teacher/demo-research/summary",
        "/api/teacher/demo-research/students",
        "/api/teacher/demo-research/students/SYN-001",
        "/api/teacher/demo-research/dictionary",
        "/api/teacher/demo-research/expert-review",
        "/api/teacher/demo-research/export.csv",
    ):
        assert client.get(path).status_code == 200, path

    db = db_factory()
    try:
        after = {
            "students": db.query(Student).count(),
            "case_sessions": db.query(CaseSession).count(),
            "learning_evidence_events": db.query(LearningEvidenceEvent).count(),
            "teacher_score_reviews": db.query(TeacherScoreReview).count(),
        }
    finally:
        db.close()
    assert after == before


def test_service_does_not_import_the_orm_or_a_db_session():
    source = (
        demo_research.__file__ or ""
    )
    assert source
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    for forbidden in ("from app.models", "from app.database", "import app.models"):
        assert forbidden not in text
    # Docstrings may name the session factory; an actual call must not appear.
    assert "Depends(get_db)" not in text


# --- authorization ----------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/teacher/demo-research/meta",
        "/api/teacher/demo-research/students/SYN-001",
        "/api/teacher/demo-research/export.csv",
    ],
)
def test_anonymous_and_students_cannot_read_the_demo(client, db_factory, path):
    client.cookies.clear()
    assert client.get(path).status_code == 401

    _login(client, db_factory, "student_demo_denied", "student")
    assert client.get(path).status_code == 403
    client.cookies.clear()


# --- payloads ---------------------------------------------------------------


def test_meta_names_the_seed_generator_and_pending_reviews(client, db_factory):
    _login(client, db_factory, "teacher_demo_meta", "teacher")
    payload = client.get("/api/teacher/demo-research/meta").json()

    assert payload["data_origin"] == demo_research.DATA_ORIGIN
    assert payload["rater_origin"] == demo_research.RATER_ORIGIN
    assert payload["seed"] == 20261018
    assert payload["counts"] == {
        "students": 60,
        "assessments": 120,
        "learning_sessions": 180,
        "reasoning_steps": 450,
    }
    assert payload["expert_review"]["status"] == "PENDING_REAL_REVIEW"
    assert payload["expert_review"]["pending_rows"] == payload["expert_review"]["total_rows"]
    assert payload["generator"]["ai_text_generation"] == (
        "MODEL_AUTHORED_TEMPLATE_PLUS_DETERMINISTIC_VARIATION"
    )
    assert len(payload["files"]) >= 5
    assert all(len(entry["sha256"]) == 64 for entry in payload["files"])


def test_students_endpoint_filters_by_group_and_search(client, db_factory):
    _login(client, db_factory, "teacher_demo_students", "teacher")

    every = client.get("/api/teacher/demo-research/students").json()
    assert every["count"] == 60
    assert len(every["students"]) == 60

    cbl = client.get("/api/teacher/demo-research/students", params={"group": "CBL"}).json()
    assert cbl["count"] == 30
    assert {row["group"] for row in cbl["students"]} == {"CBL"}

    search = client.get("/api/teacher/demo-research/students", params={"q": "SYN-00"}).json()
    assert search["count"] == 9
    assert all(row["study_id"].startswith("SYN-00") for row in search["students"])


def test_student_detail_exposes_six_dimensions_and_five_stages(client, db_factory):
    _login(client, db_factory, "teacher_demo_detail", "teacher")

    detail = client.get("/api/teacher/demo-research/students/SYN-001").json()
    assert detail["study_id"] == "SYN-001"
    assert len(detail["assessments"]) == 2
    for assessment in detail["assessments"]:
        assert len(assessment["dimensions"]) == 6
        assert assessment["rater_origin"] == demo_research.RATER_ORIGIN

    if detail["group"] == "CLINPATH":
        assert len(detail["sessions"]) == 3
        for session in detail["sessions"]:
            assert len(session["reasoning_steps"]) == 5
            for step in session["reasoning_steps"]:
                assert step["is_real_student"] == "NO"
                assert step["initial_answer"] and step["tutor_question"] and step["revised_answer"]
        assert any("训练分" in note for note in detail["notes"])
    else:
        assert detail["sessions"]
        assert all(not session["reasoning_steps"] for session in detail["sessions"])


def test_unknown_study_id_is_a_404(client, db_factory):
    _login(client, db_factory, "teacher_demo_404", "teacher")
    assert client.get("/api/teacher/demo-research/students/SYN-999").status_code == 404


def test_export_csv_is_synthetic_in_name_header_and_rows(client, db_factory):
    _login(client, db_factory, "teacher_demo_csv", "teacher")
    response = client.get("/api/teacher/demo-research/export.csv")

    assert response.status_code == 200
    assert "SYNTHETIC" in response.headers["content-disposition"]
    assert response.headers["x-data-origin"] == demo_research.DATA_ORIGIN

    text = response.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 60
    assert all(row["SYNTHETIC_DATA_ORIGIN"] == demo_research.DATA_ORIGIN for row in rows)
    assert all(row["rater_origin"] == demo_research.RATER_ORIGIN for row in rows)
    assert all(row["DISCLAIMER"] for row in rows)

    # The CSV is the same data the page summarises: recompute the group means
    # from the download itself and compare.
    served = client.get("/api/teacher/demo-research/summary").json()
    for group in ("CBL", "CLINPATH"):
        gains = [
            float(row["gain_score"])
            for row in rows
            if row["group"] == group
        ]
        assert sum(gains) / len(gains) == pytest.approx(
            served["groups"][group]["gain_mean"], abs=0.01
        )


def test_expert_review_never_claims_real_approval(client, db_factory, dataset):
    _login(client, db_factory, "teacher_demo_review", "teacher")
    payload = client.get("/api/teacher/demo-research/expert-review").json()
    assert payload["status"] == "PENDING_REAL_REVIEW"
    assert len(payload["rows"]) == len(dataset.expert_review)
    for row in payload["rows"]:
        assert row["final_approval"] == "PENDING_REAL_REVIEW"
        assert row["reviewer_name"] == ""
        assert row["review_date"] == ""
