"""R1.2: the Assessment domain shares nothing with Training scoring, AI, profiles or recommendations.

This file is the positive replacement for the old xfail
``test_an_assessment_session_does_not_enter_the_formative_profile``: an
independent assessment now has its own domain, API and tables, and these tests
prove (not assume) that running one leaves every Training table and the AI
audit untouched.
"""
import json
import subprocess
import sys
from pathlib import Path

from app.assessment_models import AssessmentSitting
from app.core import ai_audit
from app.database import Base
from app.models import Case, CompetencyProfile, LearningRecommendation, Score, Student, User
from app.services.llm_service import LLMService
from tests.assessment_helpers import (
    SCORES, build_world, blind_code_for, login, publish_form, rate, schedule, sit_exam,
)
from tests.factories import make_case

BACKEND = Path(__file__).resolve().parents[1]
DOMAIN_PREFIXES = ("assessment_", "study_", "research_")


def _training_snapshot(db):
    counts = {name: db.query(table).count() for name, table in Base.metadata.tables.items()
              if not name.startswith(DOMAIN_PREFIXES)}
    profiles = sorted((p.student_id, p.medical_knowledge, p.key_information, p.differential_diagnosis,
                       p.evidence_integration, p.clinical_decision, p.evidence_based_medicine, p.learning_engagement)
                      for p in db.query(CompetencyProfile))
    return counts, profiles


def test_full_assessment_lifecycle_leaves_training_and_ai_untouched(db_factory, client, monkeypatch):
    ai_calls = []

    def forbidden(name):
        def _raise(*a, **k):
            ai_calls.append(name)
            raise AssertionError(f"assessment code called AI: {name}")
        return _raise

    for name in ("chat_json", "chat_completion", "generate_case", "generate_sp_feedback", "explain_recommendation",
                 "explain_recommendation_batch", "generate_teacher_insight"):
        assert hasattr(LLMService, name), name
        monkeypatch.setattr(LLMService, name, forbidden(name))
    monkeypatch.setattr(ai_audit, "ai_invocation", forbidden("ai_invocation"))

    w = build_world(db_factory)
    db = db_factory()
    make_case(db)
    db.commit()
    before = _training_snapshot(db)
    db.close()

    form = publish_form(client, w)
    sid = schedule(client, w, w.students[0], form)
    sit_exam(client, w.student_users[0], sid)
    code = blind_code_for(client, "rater_a")[0]
    rate(client, "rater_a", code, dict.fromkeys(SCORES, 95))
    rate(client, "rater_b", code, dict.fromkeys(SCORES, 40))
    login(client, "adjudicator")
    assert client.post(f"/api/assessments/adjudication/{code}", json={"scores": SCORES, "rationale": "裁决：两评分差异过大"}).status_code == 200
    login(client, "admin_user")
    assert client.post(f"/api/assessments/admin/sittings/{sid}/finalize").status_code == 200
    assert client.post("/api/assessments/admin/dataset-locks", json={"dataset_version": "iso-v1", "data_origin": "pilot_test"}).status_code == 200
    assert client.get("/api/assessments/admin/export?data_origin=pilot_test").status_code == 200
    assert client.get("/api/assessments/admin/agreement?data_origin=pilot_test").status_code == 200

    db = db_factory()
    after = _training_snapshot(db)
    assert after == before  # every Training/AI table: same row counts; every profile: same numbers
    assert db.query(Score).count() == 0 and db.query(LearningRecommendation).count() == 0
    assert all(p[1:7] == (60.0,) * 6 for p in after[1])  # the factory baseline, never moved by a 95/40 assessment
    db.close()
    assert ai_calls == [] and ai_audit.queue_depth() == 0


def test_training_submission_creates_no_assessment_rows(db_factory, client):
    from tests.test_7day_personalization_loop import _sign_in, _submit_case
    db = db_factory()
    make_case(db)
    from tests.factories import make_student
    st, user = make_student(db, username="trainee")
    db.commit()
    uid = user.id
    db.close()
    _sign_in(client, db_factory, uid)
    _submit_case(client, 1)
    db = db_factory()
    for name, table in Base.metadata.tables.items():
        if name.startswith(DOMAIN_PREFIXES):
            assert db.query(table).count() == 0, name
    db.close()


def test_assessment_forms_are_unreachable_through_case_and_session_apis(db_factory, client):
    w = build_world(db_factory)
    form = publish_form(client, w)
    db = db_factory()
    assert db.query(Case).count() == 0  # a form is never materialised as a Case
    db.close()
    for who in (w.student_users[0], "plain_teacher", "admin_user"):
        login(client, who)
        listing = client.get("/api/cases")
        assert "保密考核" not in listing.text and "HIDDEN-REFERENCE" not in listing.text
        assert client.get(f"/api/cases/{form}").status_code == 404
    login(client, w.student_users[0])
    started = client.post("/api/sessions/start", json={"case_id": form})
    assert started.status_code == 404  # the form id is not a training case id
    for path in ("/api/knowledge", "/api/guidelines", "/api/skills", "/api/sp/cases"):
        r = client.get(path)
        assert "保密考核" not in r.text and "HIDDEN-REFERENCE" not in r.text, path


def test_student_never_sees_reference_answers_rubric_or_scores(db_factory, client):
    w = build_world(db_factory)
    form = publish_form(client, w)
    sid = schedule(client, w, w.students[0], form, cohort="COHORT-SECRET", group="CBL")
    login(client, w.student_users[0])
    seen = [client.get("/api/assessments/my").text]
    seen.append(client.post(f"/api/assessments/my/{sid}/start").text)
    for i in range(5):
        seen.append(client.get(f"/api/assessments/my/{sid}").text)
        seen.append(client.put(f"/api/assessments/my/{sid}/draft", json={"stage_index": i, "answer_text": "草稿"}).text)
        seen.append(client.post(f"/api/assessments/my/{sid}/answer", json={"stage_index": i, "answer_text": f"答{i}"}).text)
    seen.append(client.get(f"/api/assessments/my/{sid}").text)  # ready_to_submit
    seen.append(client.post(f"/api/assessments/my/{sid}/submit").text)
    seen.append(client.get(f"/api/assessments/my/{sid}").text)  # submitted
    seen.append(client.get("/api/assessments/my").text)
    blob = "\n".join(seen)
    for banned in ("HIDDEN-REFERENCE", "ANCHOR-TEXT", "answer_key", "rubric", "weights", "保密考核", "COHORT-SECRET",
                   "CBL", "CLINPATH", "final_score", "total_score", "blind_code", "rater", "ASSESS-A-TEST", "diagnosis"):
        assert banned not in blob, banned
    # Mid-exam the student sees their own released stages only.
    assert "A信息4" in blob and "A信息5" not in blob


def test_assessment_package_imports_no_training_or_ai_code():
    code = (
        f"import sys; sys.path.insert(0, {str(BACKEND)!r})\n"
        "import app.routes.assessments, app.assessment.admin, app.assessment.dataset, app.assessment.design, "
        "app.assessment.forms, app.assessment.rating, app.assessment.student, app.assessment_models\n"
        "import json; print(json.dumps(sorted(m for m in sys.modules if m.startswith('app.'))))"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], cwd=BACKEND, capture_output=True, text=True,
                         env={"CLINPATH_ENV": "development", "PATH": ""}, timeout=120)
    assert out.returncode == 0, out.stderr[-800:]
    modules = set(json.loads(out.stdout.strip().splitlines()[-1]))
    forbidden = [m for m in modules if m.startswith(("app.services", "app.llm", "app.routes.sessions", "app.routes.sp",
                                                     "app.routes.teacher", "app.core.ai_", "app.core.llm_config"))]
    assert forbidden == [], forbidden
