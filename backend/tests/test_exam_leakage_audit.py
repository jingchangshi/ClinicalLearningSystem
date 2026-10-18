"""scripts/grant/audit_exam_leakage.py must find planted leaks, stay quiet on the real catalogue, and fail closed."""
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "grant" / "audit_exam_leakage.py"
CASE_REL = Path("docs/teaching_grant_2026/workpackages/A_cases")

spec = importlib.util.spec_from_file_location("audit_exam_leakage", SCRIPT)
audit = importlib.util.module_from_spec(spec)
sys.modules["audit_exam_leakage"] = audit  # dataclasses need the module registered
spec.loader.exec_module(audit)


def _mini_repo(tmp_path: Path, extra_case: dict | None = None) -> Path:
    """Copy only what the audit reads, so tests can plant content without touching the real repo."""
    root = tmp_path / "repo"
    (root / CASE_REL).mkdir(parents=True)
    for name in ("A01_assessment_payload_DRAFT.json", "A02_assessment_payload_DRAFT.json"):
        shutil.copy(REPO_ROOT / CASE_REL / name, root / CASE_REL / name)
    for card in (REPO_ROOT / CASE_REL).glob("A01_training_*.md"):
        shutil.copy(card, root / CASE_REL / card.name)
    (root / "backend/app").mkdir(parents=True)
    seed = (REPO_ROOT / "backend/app/seed_data.py").read_text(encoding="utf-8")
    if extra_case is not None:
        planted = repr(extra_case)
        seed = seed.replace("    return [\n        {\n            \"title\": \"SLE基础病例\"",
                            f"    return [\n        {planted},\n        {{\n            \"title\": \"SLE基础病例\"", 1)
        assert planted in seed, "planting failed: seed layout changed"
    (root / "backend/app/seed_data.py").write_text(seed, encoding="utf-8")
    return root


def _run(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(SCRIPT), "--repo-root", str(root), *extra],
                          capture_output=True, text=True)


def test_real_catalogue_has_no_high_or_medium_leak():
    result = subprocess.run([sys.executable, "-I", str(SCRIPT), "--fail-on", "MEDIUM"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HIGH=0 MEDIUM=0" in result.stdout


def test_planted_sicca_training_case_is_flagged_high(tmp_path):
    leak = {
        "title": "干燥综合征教学病例",
        "disease_category": "干燥综合征",
        "chief_complaint": "女性，42岁，双眼干涩、夜间口干8个月。",
        "history": "Schirmer试验右眼3 mm/5 min，抗SSA阴性，需唇腺活检。",
        "standard_diagnosis": "原发性干燥综合征",
    }
    root = _mini_repo(tmp_path, leak)
    result = _run(root, "--json")
    assert result.returncode == 1, result.stdout
    data = json.loads(result.stdout)
    hits = [f for f in data["findings"] if f["category"] == "case" and f["title"] == "干燥综合征教学病例"]
    assert hits and hits[0]["severity"] == "HIGH" and hits[0]["exam"] == "CASE-A02"


def test_near_copy_of_exam_stage_is_flagged_by_similarity(tmp_path):
    payload = json.loads((REPO_ROOT / CASE_REL / "A01_assessment_payload_DRAFT.json").read_text(encoding="utf-8"))
    copied = {"title": "多关节痛示范", "history": payload["stages"][0]["clinical_information"],
              "lab_results": payload["stages"][1]["clinical_information"]}
    root = _mini_repo(tmp_path, copied)
    data = json.loads(_run(root, "--json").stdout)
    hit = next(f for f in data["findings"] if f["title"] == "多关节痛示范" and f["exam"] == "CASE-A01")
    assert hit["similarity"] >= audit.SIMILARITY_FLAG and hit["severity"] == "HIGH"


def test_single_answer_term_is_medium_and_fail_on_threshold_works(tmp_path):
    mention = {"title": "泛化文本", "content": "未分化关节炎需要随访。"}
    root = _mini_repo(tmp_path, mention)
    data = json.loads(_run(root, "--json").stdout)
    hit = next(f for f in data["findings"] if f["title"] == "泛化文本")
    assert hit["severity"] == "MEDIUM"
    assert _run(root, "--fail-on", "HIGH").returncode == 0
    assert _run(root, "--fail-on", "MEDIUM").returncode == 1


def test_missing_inputs_fail_closed(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _run(empty).returncode == 2
    root = _mini_repo(tmp_path)
    (root / CASE_REL / "A02_assessment_payload_DRAFT.json").unlink()
    assert _run(root).returncode == 2
    root2 = _mini_repo(tmp_path / "second")
    assert _run(root2, "--extra-json", str(tmp_path / "nope.json")).returncode == 2


def test_extra_json_catalogue_export_is_scanned(tmp_path):
    root = _mini_repo(tmp_path)
    export = tmp_path / "catalogue.json"
    export.write_text(json.dumps([{"title": "导出病例", "history": "口干眼干，Schirmer试验异常，考虑干燥综合征"}],
                                 ensure_ascii=False), encoding="utf-8")
    data = json.loads(_run(root, "--json", "--extra-json", str(export)).stdout)
    assert any(f["category"] == "extra" and f["severity"] == "HIGH" for f in data["findings"])


def test_exposure_model_numbers():
    model = audit.exposure_model()
    assert model["students"] == 49
    assert model["students_with_any_within_batch_informant_at_D6"] == 49  # crossover => every D6 form was sat on D1 by classmates
    assert model["students_with_prior_cohort_informants_at_D1"] == 42
    rows = model["per_batch"]
    assert [r["prior_students_who_sat_both_forms"] for r in rows] == [0, 7, 14, 21, 28, 35, 42]
    assert rows[0]["within_batch_informants_for_X_at_D6"] == 3 and rows[0]["within_batch_informants_for_Y_at_D6"] == 4
    assert rows[-1]["informants_for_Y_at_D6_total"] == 46
    # no crossover (everyone same order) removes the within-batch exposure for the model
    assert audit.exposure_model(x_size=7)["students_with_any_within_batch_informant_at_D6"] == 0
