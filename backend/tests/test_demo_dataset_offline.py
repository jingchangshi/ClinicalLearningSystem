"""The acceptance demo dataset is offline, reproducible, and honest about itself.

`frontend/tests/e2e/demo-readiness.spec.ts` reads three surfaces a clinical teacher
actually looks at -- a learner's growth trend, the anonymised research export, and
the learner's own case history -- and asserts they show a *class*, not one test
run. The acceptance stack is keyless, so `scripts/grant/e2e/build_demo_dataset.py`
builds that dataset from the rule engine instead of a model.

Two claims are load-bearing and are tested here rather than assumed:

1. The guard is the exact inverse of `prepare_presentation_data.py`'s. That tool
   refuses to run without a model; this one must refuse to run *with* one. If a
   provider were configured, a rule-fallback dataset would be written where an AI
   dataset was intended, and nothing downstream could tell.
2. A replayed case score is stored as `rule_fallback` with no provider or model,
   which is what the student-visible badge and the research CSV both report.

The plan itself is the operator tool's, so these tests exercise the real plan and
not a copy of it.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
# Score requires every dimension; the value is irrelevant to a provenance check.
_DIMENSIONS = {key: 72.0 for key in (
    "medical_knowledge", "key_information", "differential_diagnosis",
    "evidence_integration", "clinical_decision", "evidence_based_medicine",
)}
SCRIPT = REPO / "scripts" / "grant" / "e2e" / "build_demo_dataset.py"


def _load(monkeypatch):
    """Import the script as a module without running ``main``."""
    monkeypatch.setenv("CLINPATH_SKIP_OPERATOR_ENV", "1")
    name = "build_demo_dataset_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script(monkeypatch):
    return _load(monkeypatch)


def test_the_script_is_the_one_the_harness_runs(script):
    """A guard on a script nobody runs proves nothing."""
    harness = (REPO / "scripts" / "grant" / "e2e" / "run_all_inside.sh").read_text()
    assert "build_demo_dataset.py" in harness


def test_a_configured_provider_is_refused(script, monkeypatch):
    """The inverse of the operator tool's guard, and the reason it exists."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-not-a-real-key")
    with pytest.raises(SystemExit) as excinfo:
        script.require_keyless()
    assert "must be keyless" in str(excinfo.value)


def test_a_configured_provider_is_refused_even_from_an_alias(script, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-not-a-real-key")
    with pytest.raises(SystemExit):
        script.require_keyless()


def test_no_provider_key_means_keyless(script, monkeypatch):
    """The acceptance stack's own shape: all provider keys blanked."""
    for name in ("LLM_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(name, "")
    from app.core import llm_config

    if llm_config.LLM_CONFIGURED:  # pragma: no cover - depends on the environment
        pytest.skip("this environment has a provider configured; the refusal is covered above")
    script.require_keyless()  # must not raise


def test_a_database_outside_tmp_is_refused(script):
    with pytest.raises(Exception) as excinfo:
        script.guard.check_database_url("sqlite:////home/jcshi/workspace/clinical_learning_system/backend/clinical_learning.db")
    assert "production" in str(excinfo.value).lower() or "/tmp" in str(excinfo.value)


def test_the_plan_is_the_operators_plan_not_a_copy(script):
    """One definition of the demo timeline: the script imports the operator tool."""
    plan = script.load_plan()
    assert Path(plan.__file__).resolve() == script.PLAN_SCRIPT.resolve()
    # The four demo students, including the one the seed does not create yet.
    names = [entry.name for entry in plan.DEMO_STUDENTS]
    assert names == ["李明", "王佳", "陈晨", "赵敏"]
    assert len(plan.ACTIVITIES) >= 16


def test_loading_the_plan_never_reads_operator_secrets(script, monkeypatch):
    """The plan module reads ~/.config/clinpath unless it is told not to."""
    monkeypatch.delenv("CLINPATH_SKIP_OPERATOR_ENV", raising=False)
    script.load_plan()
    import os

    assert os.environ["CLINPATH_SKIP_OPERATOR_ENV"] == "1"


def test_a_replayed_score_is_stored_as_rule_fallback(db_factory, script):
    """What the student badge and the research CSV both read back."""
    from app.models import CaseSession, Score, Student

    db = db_factory()
    student = Student(name="演示", student_no="T1", class_name="演示班", current_stage="阶段1")
    db.add(student)
    db.flush()
    session = CaseSession(student_id=student.id, case_id=1, status="completed")
    db.add(session)
    db.flush()
    db.add(Score(session_id=session.id, total_score=72.0, evaluation_mode="rule_fallback",
                 degraded=True, rule_score=72.0, feedback="规则降级评价", strengths="要点完整", weaknesses="依据不足", **_DIMENSIONS))
    db.commit()
    result = script.verify_rule_fallback_only(db, [student.id])
    db.close()

    assert result["case_scores"] == 1
    assert result["evaluation_modes"] == {"rule_fallback": 1}


def test_an_ai_score_is_refused_by_the_provenance_check(db_factory, script):
    """If a model ever answered, the dataset must not be recorded as rule output."""
    from app.models import CaseSession, Score, Student

    db = db_factory()
    student = Student(name="演示", student_no="T2", class_name="演示班", current_stage="阶段1")
    db.add(student)
    db.flush()
    session = CaseSession(student_id=student.id, case_id=1, status="completed")
    db.add(session)
    db.flush()
    db.add(Score(session_id=session.id, total_score=81.0, evaluation_mode="ai", degraded=False,
                 provider="deepseek", model="deepseek-flash", feedback="模型评价", strengths="要点完整", weaknesses="依据不足", **_DIMENSIONS))
    db.commit()
    try:
        with pytest.raises(SystemExit) as excinfo:
            script.verify_rule_fallback_only(db, [student.id])
    finally:
        db.close()
    assert "not rule fallbacks" in str(excinfo.value)
