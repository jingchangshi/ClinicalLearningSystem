"""scripts/grant/publish_safety_scan.py is the pre-push boundary of a PUBLIC repository.

The tests pin the properties that make it worth running: it blocks what must never enter a
new public commit (an un-released exam form, an answer key, a linkage table, a real
signature block, a key), it does not block what is already public or recorded as a
synthetic fixture, and it *fails closed* (exit 2) when it cannot tell what would be
published instead of reporting a pass.

Sensitive-looking fixtures in this file are assembled from parts on purpose: the scan reads
every file in the repository, including this one, so a literal in here would be a finding
about the test suite itself.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "grant" / "publish_safety_scan.py"

spec = importlib.util.spec_from_file_location("publish_safety_scan", SCRIPT)
assert spec is not None and spec.loader is not None
scan = importlib.util.module_from_spec(spec)
sys.modules["publish_safety_scan"] = scan          # dataclasses need the module registered
spec.loader.exec_module(scan)

CLEAN = "backend/app/thing.py"
CLEAN_TEXT = "def add(a, b):\n    return a + b\n"

# Fixtures, assembled so this file carries no literal the scan would flag in the real repo.
FAKE_SECRET_VALUE = "s3cr3t" + "-value-never-real"
FAKE_PHONE = "136" + "12345678"
STUDENT_NO = "2023" + "010112"
SIGNED_BLOCK = "学生" + "签名：" + "张" + "三" + "    日期：20" + "26-10-19\n"
NAMED_HOLDER = "主持人：" + "李" + "四" + "，负责本项目的教学工作。\n"
EXPOSURE_NOTE = "已公开的开发样例：仅供平台演示，不得用于真实研究"

EXAM_FORM = json.dumps({
    "code": "CASE-X99-V1",
    "title": "新保密题本",
    "stages": [{"title": f"S{i} 阶段", "clinical_information": f"第{i}阶段资料", "question": "问题"}
               for i in range(1, 6)],
    "answer_key": {"S1": "标准答案一", "S2": "标准答案二"},
    "rubric": {"维度": [{"anchor": "评分锚点"}]},
}, ensure_ascii=False)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _repo(tmp_path: Path, files: dict[str, str], name: str = "repo") -> Path:
    """A throwaway git repository with ``files`` committed, so nothing is 'changed'."""
    root = tmp_path / name
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _write(root, files)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-I", str(SCRIPT), "--repo-root", str(root), *args],
                          capture_output=True, text=True)


def _rules(result: subprocess.CompletedProcess) -> list[str]:
    return [line.split()[1] for line in result.stdout.splitlines() if line.startswith("[")]


# ---------------------------------------------------------------------------------------
# clean / pass cases
# ---------------------------------------------------------------------------------------
def test_clean_staged_commit_passes(tmp_path):
    root = _repo(tmp_path, {CLEAN: CLEAN_TEXT})
    _write(root, {"backend/app/new.py": "x = 1\n"})
    _git(root, "add", "-A")
    result = _run(root, "--scope", "staged")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "BLOCK=0" in result.stdout
    assert "content-inspected" in result.stdout          # a pass reports its coverage


def test_real_repo_tree_has_no_block_once_binaries_are_accepted():
    """Text content in this repository is clean; the tracked binaries need the operator decision.

    The repository legitimately tracks screenshots, DOCX and a ZIP, which no text rule can read.
    The scan refuses to call that a pass on its own, so the assertion is made with the explicit
    ``--accept-uninspected-binary`` decision - and the same run without it must still BLOCK.
    """
    accepted = subprocess.run([sys.executable, "-I", str(SCRIPT), "--scope", "tree",
                               "--accept-uninspected-binary"], capture_output=True, text=True)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    raw = subprocess.run([sys.executable, "-I", str(SCRIPT), "--scope", "tree"],
                         capture_output=True, text=True)
    assert raw.returncode == 1 and "B01" in _rules(raw)


# ---------------------------------------------------------------------------------------
# the categories that must fail closed
# ---------------------------------------------------------------------------------------
def test_staged_credential_and_env_path_block(tmp_path):
    root = _repo(tmp_path, {CLEAN: CLEAN_TEXT})
    _write(root, {".env": f"JWT_SECRET={FAKE_SECRET_VALUE}\n"})
    _git(root, "add", "-A")
    result = _run(root, "--scope", "staged")
    assert result.returncode == 1, result.stdout
    assert {"C01", "P01"} <= set(_rules(result))


def test_unreleased_exam_form_blocks(tmp_path):
    root = _repo(tmp_path, {CLEAN: CLEAN_TEXT})
    _write(root, {"docs/private/new_form.json": EXAM_FORM})
    _git(root, "add", "-A")
    result = _run(root, "--scope", "staged")
    assert result.returncode == 1, result.stdout
    assert {"E01", "E03"} <= set(_rules(result))


def test_training_case_payload_is_not_treated_as_an_exam_form(tmp_path):
    """A training case carries standard_diagnosis + rubric but no 5-stage assessment shape."""
    training = json.dumps({"title": "训练病例", "disease_category": "SLE",
                           "standard_diagnosis": "系统性红斑狼疮", "rubric": {"a": 1}}, ensure_ascii=False)
    root = _repo(tmp_path, {CLEAN: CLEAN_TEXT})
    _write(root, {"docs/teaching_grant_2026/workpackages/A_cases/A04_CASE-T99_payload.json": training})
    _git(root, "add", "-A")
    result = _run(root, "--scope", "staged")
    assert result.returncode == 0, result.stdout
    assert "E01" not in _rules(result)


def test_identity_map_linkage_table_blocks(tmp_path):
    root = _repo(tmp_path, {CLEAN: CLEAN_TEXT})
    _write(root, {"docs/research/linkage_table.csv": f"study_id,学号\nS0001,{STUDENT_NO}\n"})
    _git(root, "add", "-A")
    result = _run(root, "--scope", "staged")
    assert result.returncode == 1, result.stdout
    assert "C08" in _rules(result)


def test_filled_signature_block_blocks_and_placeholder_does_not(tmp_path):
    filled = _repo(tmp_path, {"docs/teaching_grant_2026/evidence/E5_protocol/E5_03_ethics_privacy.md":
                              SIGNED_BLOCK})
    result = _run(filled, "--scope", "tree")
    assert result.returncode == 1, result.stdout
    assert "C10" in _rules(result)

    placeholder = _repo(tmp_path, {"docs/teaching_grant_2026/evidence/E5_protocol/E5_03_ethics_privacy.md":
                                   "学生签名：【待填：学生本人签署】\n"}, name="repo2")
    assert _run(placeholder, "--scope", "tree").returncode == 0


def test_private_application_named_applicant_blocks(tmp_path):
    root = _repo(tmp_path, {"docs/teaching_grant_2026/evidence/E5_protocol/E5_04_application_text.md":
                            NAMED_HOLDER})
    result = _run(root, "--scope", "tree")
    assert result.returncode == 1, result.stdout
    assert "C09" in _rules(result)


def test_binary_is_blocked_until_explicitly_accepted(tmp_path):
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    blob = root / "docs/evidence/screenshot.png"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01")
    _git(root, "add", "-A")
    blocked = _run(root, "--scope", "staged")
    assert blocked.returncode == 1 and "B01" in _rules(blocked)
    accepted = _run(root, "--scope", "staged", "--accept-uninspected-binary")
    assert accepted.returncode == 0 and "B01" in _rules(accepted)


def test_never_publish_path_blocks_even_when_already_committed(tmp_path):
    root = _repo(tmp_path, {".env": "COOKIE_SECURE=true\n"})
    result = _run(root, "--scope", "tree")
    assert result.returncode == 1, result.stdout
    assert "P01" in _rules(result)


# ---------------------------------------------------------------------------------------
# already-public content is reported, not re-blocked
# ---------------------------------------------------------------------------------------
def test_already_committed_personal_pattern_still_blocks(tmp_path):
    """A real identifier is not acceptable in a public repository even if it got in earlier."""
    root = _repo(tmp_path, {"docs/notes/demo.md": "示例联系电话 " + FAKE_PHONE + "\n"})
    result = _run(root, "--scope", "tree")
    assert result.returncode == 1, result.stdout
    assert "C06" in _rules(result)


def test_a_recorded_synthetic_fixture_is_reported_not_blocked(tmp_path):
    """The recorded fixture list is the only way past the identifier rules."""
    root = _repo(tmp_path, {"backend/tests/test_deidentify.py": "PHONE = '" + FAKE_PHONE + "'\n"})
    result = _run(root, "--scope", "tree")
    assert result.returncode == 0, result.stdout
    assert "[INFO] C06" in result.stdout


def test_exposed_dev_sample_is_recorded_and_needs_a_label_when_touched(tmp_path):
    path = "docs/teaching_grant_2026/workpackages/A_cases/A01_assessment_payload_DRAFT.json"
    labelled = json.loads(EXAM_FORM)
    labelled["exposure_note"] = EXPOSURE_NOTE
    root = _repo(tmp_path, {path: json.dumps(labelled, ensure_ascii=False)})
    result = _run(root, "--scope", "tree")
    assert result.returncode == 0, result.stdout
    assert "E00" in _rules(result) and "E04" not in _rules(result)

    # the same recorded path, now edited without its exposure label: the commit is the boundary
    _write(root, {path: EXAM_FORM})
    blocked = _run(root, "--scope", "tree")
    assert blocked.returncode == 1, blocked.stdout
    assert "E04" in _rules(blocked)


# ---------------------------------------------------------------------------------------
# scopes and fail-closed behaviour
# ---------------------------------------------------------------------------------------
def test_range_scope_scans_the_range_and_it_still_blocks_as_inventory(tmp_path):
    root = _repo(tmp_path, {CLEAN: CLEAN_TEXT})
    _write(root, {"docs/private/new_form.json": EXAM_FORM})
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "add form")
    assert _run(root, "--scope", "range", "--range", "HEAD~1..HEAD").returncode == 1
    assert _run(root, "--scope", "tree").returncode == 1        # the path is now in HEAD too
    # a range that changes nothing proves nothing, so it fails closed
    assert _run(root, "--scope", "range", "--range", "HEAD..HEAD").returncode == 2


def test_missing_repository_and_empty_scope_fail_closed(tmp_path):
    empty = tmp_path / "not_a_repo"
    empty.mkdir()
    assert _run(empty, "--scope", "tree").returncode == 2
    root = _repo(tmp_path, {CLEAN: CLEAN_TEXT})
    assert _run(root, "--scope", "staged").returncode == 2      # nothing staged
    assert _run(root, "--scope", "range", "--range", "HEAD").returncode == 2


def test_untracked_not_ignored_files_are_included_in_tree_scope(tmp_path):
    root = _repo(tmp_path, {CLEAN: CLEAN_TEXT})
    _write(root, {"docs/private/new_form.json": EXAM_FORM})
    result = _run(root, "--scope", "tree")            # not staged, not committed
    assert result.returncode == 1, result.stdout
    assert "E01" in _rules(result)


def test_output_states_its_limits(tmp_path):
    root = _repo(tmp_path, {CLEAN: CLEAN_TEXT})
    result = _run(root, "--scope", "tree")
    assert "never 'no leakage risk'" in result.stdout
    assert "cannot undo exposure" in result.stdout


@pytest.mark.parametrize("category", sorted(scan.CATEGORIES))
def test_every_category_is_documented(category):
    assert scan.CATEGORIES[category].strip()


def test_recorded_exposures_still_exist():
    """A stale allowlist entry would silently stop protecting a path."""
    for path in scan.EXPOSED_DEV_SAMPLES:
        assert (REPO / path).is_file(), f"recorded exposure no longer exists: {path}"
