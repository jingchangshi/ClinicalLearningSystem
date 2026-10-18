"""The teacher review packet must stay blank, pending, and in sync with its generator."""
import csv
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "grant" / "build_case_review_forms.py"
FORMS_DIR = REPO_ROOT / "docs" / "teaching_grant_2026" / "workpackages" / "A_cases" / "review_forms"

spec = importlib.util.spec_from_file_location("build_case_review_forms", SCRIPT)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

CASE_FORMS = [f"CASE_REVIEW_FORM_{c}.md" for c in ("T01", "T02", "T03", "T04", "A01", "A02")]
FORBIDDEN_STATUS = ("REAL_HUMAN_REVIEW_CONDUCTED", "REVIEWED_BY_REAL_TEACHER", "APPROVED_FOR_TEACHING",
                    "APPROVED_FOR_ASSESSMENT", "已通过审核", "审核通过")
DATE_RE = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def _read(name: str) -> str:
    return (FORMS_DIR / name).read_text(encoding="utf-8")


def test_committed_forms_match_generator():
    result = subprocess.run([sys.executable, "-I", str(SCRIPT), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_all_six_case_forms_plus_support_documents_exist():
    for name in CASE_FORMS + ["RUBRIC_REVIEW_FORM.md", "DIFFICULTY_MATCH_A01_A02.md", "DISPUTE_LIST.md",
                              "ANCHOR_CONSISTENCY_TABLE.md", "REVISION_REREVIEW_LOG.md", "README.md",
                              "REVIEW_ITEMS_MASTER_BLANK.csv"]:
        assert (FORMS_DIR / name).is_file(), name


def test_every_form_is_pending_and_never_claims_approval():
    for path in FORMS_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "PENDING_REAL_REVIEW" in text, path.name
        assert "REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED" in text, path.name
        for phrase in FORBIDDEN_STATUS:
            if path.name == "README.md" and phrase == "REAL_HUMAN_REVIEW_CONDUCTED":
                continue  # the legend names the value a teacher sets *after* a real review
            assert phrase not in text, f"{path.name} contains {phrase!r}"


def test_signature_and_date_blocks_are_blank():
    for name in CASE_FORMS:
        text = _read(name)
        assert text.count("REAL_TEACHER_1") >= 2 and text.count("REAL_TEACHER_2") >= 2
        assert "| 审核日期（YYYY-MM-DD） | ____-__-__ |" in text
        assert "| 签字 | |" in text
        assert "| 姓名 / 工号 | |" in text
        assert not DATE_RE.search(text), f"{name} contains a concrete date"
    for name in ("RUBRIC_REVIEW_FORM.md", "DIFFICULTY_MATCH_A01_A02.md", "DISPUTE_LIST.md", "ANCHOR_CONSISTENCY_TABLE.md"):
        text = _read(name)
        assert "| 签字 | |" in text and "| 姓名 / 工号 | |" in text
        assert not DATE_RE.search(text), f"{name} contains a concrete date"


def test_revision_log_dates_only_in_ai_section_and_ai_rows_are_not_approved():
    text = _read("REVISION_REREVIEW_LOG.md")
    ai_part, teacher_part = text.split("## 2. 教师意见汇总与复审登记", 1)
    assert not DATE_RE.search(teacher_part.split("## 3. 规则", 1)[0]), "teacher registry must have no filled dates"
    ai_rows = [line for line in ai_part.splitlines() if line.startswith("| ") and DATE_RE.search(line)]
    assert len(ai_rows) >= 8
    for row in ai_rows:
        assert "AI technical/medical DRAFT re-check" in row or "技术变更" in row
        assert "是" not in row.split("|")[-2].strip()[:1], row  # "是否教师批准" column never starts with 是


def test_rubric_form_keeps_research_and_training_weights_separate():
    text = _read("RUBRIC_REVIEW_FORM.md")
    for zh, research, training in (("医学知识", 10, 20), ("关键信息提取", 20, 20), ("鉴别诊断", 25, 20),
                                   ("证据整合", 15, 15), ("临床决策", 20, 15), ("循证安全", 10, 10)):
        row = next(line for line in text.splitlines() if line.startswith(f"| {zh}（"))
        assert f"| {research}（待教师确认） | {training} |" in row, row
    assert "待教师确认" in text and "训练" in text and "不变" in text


def test_master_csv_is_fully_pending_with_blank_reviewers():
    rows = list(csv.DictReader((FORMS_DIR / "REVIEW_ITEMS_MASTER_BLANK.csv").open(encoding="utf-8")))
    assert len(rows) > 100
    cases = {r["case_id"] for r in rows}
    assert {"CASE-T01", "CASE-T02", "CASE-T03", "CASE-T04", "CASE-A01", "CASE-A02", "RUBRIC"} <= cases
    for r in rows:
        assert r["status"] == "PENDING_REAL_REVIEW"
        assert r["review_origin"] == "REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED"
        for field in ("teacher1_response", "teacher2_response", "reviewer_name_1", "reviewer_name_2",
                      "review_date_1", "review_date_2"):
            assert r[field] == "", (r["item_id"], field)
    ids = [r["item_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate item ids"


def test_exam_forms_include_leakage_and_payload_checks_training_forms_do_not():
    for name in ("CASE_REVIEW_FORM_A01.md", "CASE_REVIEW_FORM_A02.md"):
        text = _read(name)
        assert "| E-01 |" in text and "学生可见" in text
    for name in ("CASE_REVIEW_FORM_T01.md", "CASE_REVIEW_FORM_T02.md", "CASE_REVIEW_FORM_T03.md", "CASE_REVIEW_FORM_T04.md"):
        assert "| E-01 |" not in _read(name)


def test_a02_form_is_the_sicca_case_not_aosd():
    text = _read("CASE_REVIEW_FORM_A02.md")
    assert "干燥" in text and "A01_assessment_sicca.md" in text
    for stale in ("Yamaguchi", "HLH-2004", "MAS 风险", "A01_assessment_multisystem"):
        assert stale not in text
