"""Tests for scripts/grant/validate_assessment_payloads.py (technical form-payload checks).

These tests prove the validator passes the real A01/A02 drafts *and* fails on broken
ones. They say nothing about medical correctness: both forms stay PENDING_REAL_REVIEW.
"""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "grant" / "validate_assessment_payloads.py"
CASE_DIR = REPO_ROOT / "docs" / "teaching_grant_2026" / "workpackages" / "A_cases"
A01 = CASE_DIR / "A01_assessment_payload_DRAFT.json"
A02 = CASE_DIR / "A02_assessment_payload_DRAFT.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_assessment_payloads", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_module()


def _write(tmp_path: Path, name: str, payload) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _failed_checks(path: Path) -> list[str]:
    report = validator.run([path])
    return [row["check"] for row in report.failed]


def _failed_weights(path: Path) -> bool:
    """True when the run failed the check that the payload carries the API's weights key."""
    return any("rubric.weights" in check for check in _failed_checks(path))


@pytest.fixture
def a02_payload() -> dict:
    return json.loads(A02.read_text(encoding="utf-8"))


def test_real_drafts_pass_validation():
    report = validator.run([A01, A02])
    assert report.failed == [], report.failed
    assert len(report.rows) >= 20


def test_cli_exit_codes(tmp_path):
    ok = subprocess.run([sys.executable, "-I", str(SCRIPT)], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    missing = subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--file", str(tmp_path / "nope.json")],
        capture_output=True, text=True,
    )
    assert missing.returncode == 1, "a missing payload must fail, not pass silently"


def test_missing_file_and_empty_list_fail(tmp_path):
    assert validator.run([tmp_path / "absent.json"]).failed
    assert validator.run([]).failed


def test_invalid_json_fails(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert "valid JSON" in _failed_checks(path)


def test_four_stages_fail(tmp_path, a02_payload):
    broken = copy.deepcopy(a02_payload)
    broken["stages"].pop()
    assert "exactly 5 stages" in _failed_checks(_write(tmp_path, "A02_x.json", broken))


def test_empty_stage_field_and_extra_stage_key_fail(tmp_path, a02_payload):
    broken = copy.deepcopy(a02_payload)
    broken["stages"][2]["question"] = "  "
    broken["stages"][3]["reference_answer"] = "hidden"
    assert "stage fields complete, no extra keys" in _failed_checks(_write(tmp_path, "A02_x.json", broken))


def test_wrong_weights_fail(tmp_path, a02_payload):
    broken = copy.deepcopy(a02_payload)
    broken["rubric"]["dimensions"]["medical_knowledge"] = 20  # training-scale weight
    broken["rubric"]["dimensions"]["differential_diagnosis"] = 15
    assert "six dimensions, weights 10/20/25/15/20/10" in _failed_checks(_write(tmp_path, "A02_x.json", broken))


def test_missing_anchor_fails(tmp_path, a02_payload):
    broken = copy.deepcopy(a02_payload)
    del broken["rubric"]["anchors"]["clinical_decision"]["mid"]
    assert "rubric anchors present (6 dims x high/mid/low)" in _failed_checks(_write(tmp_path, "A02_x.json", broken))
    no_anchors = copy.deepcopy(a02_payload)
    del no_anchors["rubric"]["anchors"]
    assert "rubric anchors present" in _failed_checks(_write(tmp_path, "A02_y.json", no_anchors))


def test_missing_or_mismatched_api_weights_fail(tmp_path, a02_payload):
    """`weights` is what the assessment API reads; a payload carrying only `dimensions`
    would transcribe into a form that silently uses the study defaults instead."""
    broken = copy.deepcopy(a02_payload)
    del broken["rubric"]["weights"]
    assert _failed_weights(_write(tmp_path, "A02_x.json", broken))
    mismatch = copy.deepcopy(a02_payload)
    mismatch["rubric"]["weights"]["clinical_decision"] = 15
    assert _failed_weights(_write(tmp_path, "A02_y.json", mismatch))


def test_anchor_weight_mismatch_fails(tmp_path, a02_payload):
    broken = copy.deepcopy(a02_payload)
    broken["rubric"]["anchors"]["evidence_integration"]["weight"] = 20
    assert "rubric anchors present (6 dims x high/mid/low)" in _failed_checks(_write(tmp_path, "A02_x.json", broken))


def test_approval_claim_in_rubric_status_fails(tmp_path, a02_payload):
    broken = copy.deepcopy(a02_payload)
    broken["rubric"]["status"] = "APPROVED_FOR_ASSESSMENT"
    assert "rubric.status == PENDING_REAL_REVIEW" in _failed_checks(_write(tmp_path, "A02_x.json", broken))


@pytest.mark.parametrize(
    "leak",
    [
        "患者符合干燥综合征的诊断。",          # declared leak term
        "这提示诊断为原发性干燥综合征。",       # stated diagnosis
        "本病例不满足分类标准。",                # interpretation
        "参考答案：先做唇腺活检。",              # answer text
    ],
)
def test_answer_in_student_visible_field_fails(tmp_path, a02_payload, leak):
    broken = copy.deepcopy(a02_payload)
    broken["stages"][3]["clinical_information"] += leak
    assert "no answer-key content in student-visible fields" in _failed_checks(_write(tmp_path, "A02_x.json", broken))


def test_leak_in_title_and_question_fails(tmp_path, a02_payload):
    titled = copy.deepcopy(a02_payload)
    titled["title"] = "疑似原发性干燥综合征"
    assert "no answer-key content in student-visible fields" in _failed_checks(_write(tmp_path, "A02_t.json", titled))
    asked = copy.deepcopy(a02_payload)
    asked["stages"][4]["question"] = "请说明为什么不能确诊。"
    assert "no answer-key content in student-visible fields" in _failed_checks(_write(tmp_path, "A02_q.json", asked))


def test_answer_key_may_name_the_diagnosis_but_students_never_see_it():
    """The key legitimately names the disease; only student-visible fields are policed."""
    payload = json.loads(A02.read_text(encoding="utf-8"))
    assert "干燥综合征" in json.dumps(payload["answer_key"], ensure_ascii=False)
    for _field, text in validator._student_visible(payload):
        assert "干燥综合征" not in text


def test_missing_answer_key_or_leak_declaration_fails(tmp_path, a02_payload):
    no_key = copy.deepcopy(a02_payload)
    no_key["answer_key"] = {}
    assert "answer_key non-empty" in _failed_checks(_write(tmp_path, "A02_a.json", no_key))
    no_terms = copy.deepcopy(a02_payload)
    del no_terms["answer_key"]["leak_terms_forbidden_in_student_fields"]
    assert "answer_key declares leak terms (>=3)" in _failed_checks(_write(tmp_path, "A02_b.json", no_terms))


def test_pair_checks_detect_duplicate_codes(tmp_path):
    a01 = json.loads(A01.read_text(encoding="utf-8"))
    a02 = json.loads(A02.read_text(encoding="utf-8"))
    a02["code"] = a01["code"]
    p1 = _write(tmp_path, "A01_dup.json", a01)
    p2 = _write(tmp_path, "A02_dup.json", a02)
    assert "distinct form codes" in [r["check"] for r in validator.run([p1, p2]).failed]


def test_payload_matches_backend_form_contract(a02_payload):
    """The drafts must fit POST /api/assessments/forms (code,title,stages,answer_key,rubric)."""
    for path in (A01, A02):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert set(payload) == {"code", "title", "stages", "answer_key", "rubric"}
        assert all(set(stage) == {"title", "clinical_information", "question"} for stage in payload["stages"])
