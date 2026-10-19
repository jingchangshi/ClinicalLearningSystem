#!/usr/bin/env python3
"""Publish-safety scan: what would this commit put into the *public* repository?

``jingchangshi/ClinicalLearningSystem`` is a PUBLIC repository and its history already
contains the A01/A02 assessment drafts, their anchors and sample answers (see
``workpackages/A_cases/LEAKAGE_AUDIT_DRAFT.md`` L-1).  History cannot be rewritten, so the
only control left is the boundary: nothing sensitive may enter a *new* commit.  This script
is that boundary.  Run it before every push.

What it scans
-------------
Exactly one of three scopes, reported in the output so a green run is never mistaken for
broader coverage:

``--scope staged``   the blobs a ``git commit`` would carry right now (``git show :PATH``).
                     This is the pre-commit / pre-push gate.
``--scope range``    the blobs added by a revision range, e.g. ``origin/main..HEAD``.
``--scope tree``     every tracked file plus every untracked-not-ignored file, at its
                     working-tree content (default; an inventory run).

Rules and severities
--------------------
``BLOCK``  must not be published.  Exit status 1.  Every content rule fails closed: a
           secret, a real identifier, a linkage table, a signature block, a named applicant
           and an un-released form all BLOCK whether or not a commit is what introduced
           them, because none of them has a legitimate place in a public repository.
``WARN``   a human must look; the run still exits 0.  Used only where a finding is about
           something recorded (an exposed development draft missing its label, or content
           that drifted from the recorded exposure).
``INFO``   inventory only: the files recorded here as already-exposed development samples
           or as synthetic test fixtures, plus binaries that are already tracked.

The two ways past a rule are recorded decisions, not flags: ``EXPOSED_DEV_SAMPLES`` names
exam-bearing paths whose exposure is already public, and ``FIXTURE_PATHS`` names files whose
identifier-looking content is synthetic.  Both carry a recorded reason; a new entry is a
human decision.  ``--accept-uninspected-binary`` is the one exception, and it only applies to
the binary rule below.

The rules are grouped by what they protect (``CATEGORIES``): an un-released official exam
form; a standard answer or a complete confidential scoring anchor; real student data; an
identity map; personal information in ethics material; private application personal
details; a server key.

Fail-closed behaviour
---------------------
* a scope that cannot be determined (not a git repo, git missing, no files in scope,
  unreadable blob) is exit status **2**, never a pass;
* a file this scan cannot read as text (image, DOCX, archive) cannot be content-checked: a
  binary being added now is a ``BLOCK`` until an operator passes
  ``--accept-uninspected-binary``; a binary already tracked in HEAD is reported ``INFO`` (its
  exposure happened and its content still needs one human look);
* every run prints how many targets were inspected and which ones were not.

Honest limits (printed on every run, and true)
----------------------------------------------
This is a static, textual scan.  It cannot detect: content that was already pushed (it does
not and cannot rewrite history); content that is not in git at all; text inside images,
DOCX/PDF or archives; a re-worded exam form that no longer shares markers; who is allowed to
read a file on the file system; whether a photographed form was shared verbally.  A passing
run means "no *detected* sensitive content in *this* scope", never "no leakage risk".

Usage::

    python3 -I scripts/grant/publish_safety_scan.py --scope staged
    python3 -I scripts/grant/publish_safety_scan.py --scope range origin/main..HEAD --json
    python3 -I scripts/grant/publish_safety_scan.py --scope tree --show-allowlist

Exit status: 0 no BLOCK, 1 BLOCK findings, 2 fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

CATEGORIES = {
    "unreleased_exam_form": "未公开正式考核题本",
    "standard_answer_or_anchor": "标准答案或完整保密评分锚点",
    "real_student_data": "真实学生资料",
    "identity_map": "身份映射",
    "ethics_personal_info": "伦理材料中的个人信息",
    "private_application_details": "私密申报书完整个人资料",
    "server_key": "服务器密钥",
    "exposed_dev_sample": "已公开的开发样例（仅记录，不阻止）",
    "uninspectable": "无法检查内容（需人工确认）",
}

# ------------------------------------------------------------------------------------------
# The exposure record: exam-bearing material that is ALREADY in public history.
#
# These paths were published before this round; deleting them now would not undo the
# exposure (LEAKAGE_AUDIT_DRAFT.md L-1), so they are allowed to stay *only* as clearly
# labelled development/demo samples.  ``recorded_sha256`` is the blob as of the 2026-10-19
# audit: a mismatch is reported (WARN) so a human re-confirms that no new confidential
# material was added under an already-exposed path.
#
# Adding an entry here is an operator decision about exposure, not a code change.
# ------------------------------------------------------------------------------------------
EXPOSED_DEV_SAMPLES = {
    "docs/teaching_grant_2026/workpackages/A_cases/A01_assessment_UA.md":
        "dc231883d930c726473bab34667eb73c0a245b802a07beace4cf7b1d68fb80dd",
    "docs/teaching_grant_2026/workpackages/A_cases/A01_assessment_sicca.md":
        "e20ef38ab6b7372d4961411b9ec500adf7d8e6762f2f225b3fa946ec82f762fc",
    "docs/teaching_grant_2026/workpackages/A_cases/A01_assessment_payload_DRAFT.json":
        "bd2cc74475a5240338f1c253c39e56e9ab633a3e83bfb1c360eb25387c6cf0a5",
    "docs/teaching_grant_2026/workpackages/A_cases/A02_assessment_payload_DRAFT.json":
        "45b536050b4865b3f7ff2a67a0e47c1b71e4511bfff3af138765c839f5f1883c",
    "docs/teaching_grant_2026/workpackages/A_cases/review_forms/ANCHOR_CONSISTENCY_TABLE.md":
        "497db2ef5a314c65f9ea07b90d7794bf552ad593db73066713880344163f8516",
    "docs/teaching_grant_2026/workpackages/A_cases/review_forms/CASE_REVIEW_FORM_A01.md":
        "a331c90fb0a3bb19bab29124a945608413fd1beca95f9fb6dff382a5abca629b",
    "docs/teaching_grant_2026/workpackages/A_cases/review_forms/CASE_REVIEW_FORM_A02.md":
        "b175f86112549e906246867543789b7a78f9fb26e50aecb1a5f07f396b0e3524",
    "docs/teaching_grant_2026/workpackages/A_cases/review_forms/DIFFICULTY_MATCH_A01_A02.md":
        "e38fa066bb44fc2f81e7911876513b7f8a864deb6656236fe2a372f3a5b5dd5f",
    "docs/teaching_grant_2026/workpackages/B_rubric/B02_sample_answers.csv":
        "f2d3fc80cdf7eaaef20666d7b1ac071fd1c5e97d78aa10a244f35d424cb283e5",
    "docs/teaching_grant_2026/workpackages/B_rubric/B02_sample_answers.md":
        "ff3378c7c91d689e6d09c8413ca9b8c1249d690d4d7a945e15547833fa55f591",
    # A04 is a process/quality-control document, not a case card: it names the two forms and the
    # state of their anchors, but carries no patient material and no answer key.  It is
    # exam-adjacent and already public, so it is recorded here rather than left to trip the
    # "exam-bearing path without a recorded decision" rule on every future run.
    "docs/teaching_grant_2026/workpackages/A_cases/A04_assessment_quality_control.md":
        "b66d07961bed2008129059b8dd891b379bf6e42cce5b0f65c82c7c2313ef5fb8",
}

# Files that legitimately contain *fictional* identifiers, fake secrets or de-identification
# patterns.  Content findings in these paths are reported as INFO with this recorded reason.
FIXTURE_PATHS = {
    "backend/tests/test_deidentify.py": "synthetic fixtures: fictional 身份证/手机号 used to test de-identification",
    "backend/tests/test_case_authoring_deidentification.py":
        "synthetic fixtures: placeholder phone numbers testing the authoring de-identifier",
    "backend/app/core/deidentify.py": "the redaction patterns themselves (regex source, not data)",
    "backend/tests/test_verify_deploy_script.py":
        "synthetic fixtures: fake JWT secrets written into temporary .env files by the test",
    "frontend/tests/e2e/training.spec.ts":
        "synthetic fixture: a placeholder phone number typed into the case-authoring form to "
        "assert the de-identification warning fires",
}

# A path that matches one of these must never be published, whatever its content.
SENSITIVE_PATH_RULES: list[tuple[str, str, str]] = [
    ("P01", "server_key", r"(^|/)\.env(\.(?!example$)[^/]*)?$|(^|/)\.env\.(local|prod|production|secret)$"
                          r"|\.(pem|key|p12|pfx|jks|keystore)$|(^|/)id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$"
                          r"|(^|/)\.ssh/|(^|/)\.config/clinpath/|(^|/)credentials\.json$"
                          r"|(^|/)service[-_]account[^/]*\.json$"),
    ("P02", "identity_map", r"identity[_-]?map|id[_-]?map|连接表|linkage[_-]?table|student[_-]?roster"
                            r"|花名册|受试者名单|学员名单|college[_-]?roster"),
    ("P03", "real_student_data", r"real[_-]?student|真实学生|consent[_-]?form|知情同意书|同意书原件"),
    ("P04", "private_application_details",
     r"申报书_官方模板填写版|汇总表_官方模板填写版|主持人教学简历|application[_-]?private"
     r"|私密申报|official[_-]?application[_-]?filled"),
    ("P05", "unreleased_exam_form",
     r"confidential[_-]?exam|exam[_-]?forms?[_-]?private|secure[_-]?import/|保密题本|official[_-]?exam[_-]?form"),
]

# An assessment form's machine shape: >=5 stages, each with student-visible
# clinical_information *and* a question.  A training payload has no ``stages``.
EXAM_MIN_STAGES = 5

# Candidate exam / answer-key paths.  A markdown card or a JSON payload has no machine shape,
# so for these the path is the signal - but only for documents and data, never for source
# code that merely mentions ``answer_key`` or ``rubric`` as a schema field.
EXAM_PATH_HINTS = (
    "assessment_payload", "assessment_form", "_assessment_", "assessment_ua", "assessment_sicca",
    "answer_key", "标准答案", "评分锚点", "评分要点", "考核题本", "case-a0", "case_a0", "form_a0",
)
DOC_OR_DATA_SUFFIXES = (".md", ".json", ".csv", ".tsv", ".txt", ".yaml", ".yml")
LABELABLE_SUFFIXES = (".md", ".json", ".txt", ".yaml", ".yml")
IDENTITY_DATA_SUFFIXES = (".csv", ".tsv", ".json", ".jsonl")
ANSWER_CONTENT_MARKERS = (
    "answer_key", "standard_diagnosis", "标准诊断", "标准答案", "评分锚点", "评分要点",
    "scoring_anchor", "rubric", "锚点",
)

# Placeholder values that must not trip the secret rules: an example file, a test fixture, a
# template (``${...}`` / ``{name}``), or a value whose own name says it is throwaway.  A real
# credential is not written inside braces, so a brace reads as interpolation, not a secret.
PLACEHOLDER_VALUE = re.compile(
    r"(change[-_]?me|your[-_]|your_|example|placeholder|dummy|fake|sample|synthetic|throwaway"
    r"|disposable|not[-_]production|^e2e|dev[-_]only|dev[-_]clinpath|\{|<|\$\{"
    r"|\bos\.(getenv|environ)\b|^test|^canonical-key$|^legacy-key$)",
    re.IGNORECASE)


@dataclass
class Target:
    path: str
    content: str | None      # None when the blob could not be inspected as text
    changed: bool            # does this commit / this worktree state introduce or change it?
    reason_uninspectable: str | None = None

    @property
    def sha256(self) -> str:
        if self.content is None:
            return ""
        return hashlib.sha256(self.content.encode("utf-8", "surrogateescape")).hexdigest()


@dataclass
class Finding:
    severity: str
    rule: str
    category: str
    path: str
    line: int | None = None
    detail: str = ""


@dataclass
class Report:
    scope: str
    inspection: str
    targets: list[Target] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


class ScanError(Exception):
    """Fail closed: the scan could not establish what would be published."""


# ------------------------------------------------------------------------------------------
# git plumbing
# ------------------------------------------------------------------------------------------
def _git(root: Path, *args: str, check: bool = True) -> str:
    try:
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    except OSError as exc:                                   # git not installed
        raise ScanError(f"cannot run git: {exc}") from exc
    if check and proc.returncode != 0:
        raise ScanError(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def _split_paths(raw: str) -> list[str]:
    return [p for p in raw.split("\0") if p]


def _read_blob(root: Path, rev: str, path: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(root), "show", f"{rev}:{path}"], capture_output=True)
    if proc.returncode != 0:
        raise ScanError(f"cannot read {rev}:{path}: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def _decode(raw: bytes) -> tuple[str | None, str | None]:
    if b"\0" in raw[:8000]:
        return None, "binary content (image/DOCX/archive): text rules cannot inspect it"
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "not valid UTF-8 text: text rules cannot inspect it"


def collect_targets(root: Path, scope: str, rev_range: str | None) -> tuple[list[Target], str]:
    if not (root / ".git").exists():
        raise ScanError(f"not a git repository: {root}")
    if scope == "staged":
        paths = _split_paths(_git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"))
        if not paths:
            raise ScanError("scope staged: nothing is staged, so this run proves nothing "
                            "(stage the commit or use --scope tree)")
        targets = []
        for path in paths:
            content, why = _decode(_read_blob(root, "", path))
            targets.append(Target(path, content, True, why))
        return targets, "staged: the exact blobs `git commit` would carry"
    if scope == "range":
        if not rev_range or ".." not in rev_range:
            raise ScanError("scope range needs --range A..B")
        head = rev_range.split("..", 1)[1] or "HEAD"
        paths = _split_paths(_git(root, "diff", "--name-only", "--diff-filter=ACMR", "-z", rev_range))
        if not paths:
            raise ScanError(f"scope range: {rev_range} changes no files, so this run proves nothing")
        targets = []
        for path in paths:
            content, why = _decode(_read_blob(root, head, path))
            targets.append(Target(path, content, True, why))
        return targets, f"range {rev_range}: the blobs added by {head}"
    tracked = _split_paths(_git(root, "ls-files", "-z"))
    if not tracked:
        raise ScanError("scope tree: no tracked files, so this run proves nothing")
    # Untracked-but-not-ignored files are included too: a file that is about to be added is
    # exactly what this scan exists for, and leaving it out would make a green run a lie.
    untracked = _split_paths(_git(root, "ls-files", "-o", "--exclude-standard", "-z"))
    dirty = set(_split_paths(_git(root, "diff", "--name-only", "-z", "HEAD"))) | set(untracked)
    targets = []
    for path in tracked + untracked:
        blob = root / path
        try:
            raw = blob.read_bytes()
        except OSError as exc:
            raise ScanError(f"cannot read file {path}: {exc}") from exc
        content, why = _decode(raw)
        targets.append(Target(path, content, path in dirty, why))
    return (targets, f"tree: {len(tracked)} tracked + {len(untracked)} untracked-not-ignored file(s), "
                     f"at their working-tree content (changed = differs from HEAD or untracked)")


# ------------------------------------------------------------------------------------------
# rules
# ------------------------------------------------------------------------------------------
SECRET_RULES: list[tuple[str, str]] = [
    ("C01", r"(JWT_SECRET|JWT_KEY|SECRET_KEY|API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|LLM_API_KEY"
            r"|ACCESS_TOKEN|DB_PASSWORD|DATABASE_PASSWORD|SEED_DEMO_STUDENT_PASSWORD)\s*[:=]\s*[\"']?([^\s\"'#,;)}]{12,})"),
    ("C02", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("C03", r"\b(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z\-_]{35})\b"),
]

PERSONAL_RULES: list[tuple[str, str, str]] = [
    ("C05", "real_student_data", r"\b\d{17}[\dXx]\b"),                       # 身份证
    ("C06", "real_student_data", r"\b1[3-9]\d{9}\b"),                        # 手机号
    ("C07", "real_student_data",
     r"(学号|student_no|student_number)\s*[：:=]\s*[A-Za-z]?\d{6,}"),
]

# A record that pairs a study code with a student identifier is an identity map.
IDENTITY_KEY = re.compile(r"(学号|student_no|student_number|姓名|真实姓名|real_name|full_name|username)")
STUDY_KEY = re.compile(r"(study_id|study_code|research_id|subject_id|研究编号)")
DIGITS = re.compile(r"\d{4,}")

ETHICS_PERSONAL = re.compile(
    r"(学生签名|受试者签名|研究者签名|见证人签名|申请人签名)\s*[：:]\s*(?!$|【|＿|_|的|\||</)[^\s|]{2,}")
SIGNATURE_BLOCK = re.compile(r"(签名|签字)\s*[：:]\s*[^\s|【＿_]{2,4}\s*(日期|年|20\d\d)")

PRIVATE_APP_PATH_HINTS = ("application_text", "e5_04", "申报书", "汇总表", "简历")
APPLICANT_ROLE = re.compile(r"(申请人|主持人|项目负责人|负责人)\s*[：:]\s*(?!【待填|【|＿|_)[一-鿿]{2,4}\b")

EXPOSURE_LABEL = re.compile(
    r"已公开|公开历史|公开暴露|EXPOSED|PUBLIC[\s_-]EXPOS|演示|DEMO|开发样例|测试样例|样例数据"
    r"|不得用于真实研究|not a secure exam|PENDING_REAL_REVIEW", re.IGNORECASE)


def _is_allowlisted_exposed(path: str) -> bool:
    return path in EXPOSED_DEV_SAMPLES


def _looks_like_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_VALUE.search(value.strip()))


def _exam_form_shape(content: str) -> bool:
    """Machine-readable assessment form: >=5 stages each with clinical_information + question."""
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return False
    stages = data.get("stages") if isinstance(data, dict) else None
    if not isinstance(stages, list) or len(stages) < EXAM_MIN_STAGES:
        return False
    return all(isinstance(s, dict) and "clinical_information" in s and "question" in s for s in stages)


def _line_record_has_identity_map(content: str) -> bool:
    """A table/lines file pairing a study code with an identifier *and* carrying values.

    A header that merely documents both column names is not a linkage table, and a code
    without an identity (or the reverse) identifies nobody, so a value with digits is
    required as well.
    """
    lines = content.splitlines()[:4000]
    header = None
    for index, line in enumerate(lines):
        both = STUDY_KEY.search(line) and IDENTITY_KEY.search(line)
        if both and DIGITS.search(line):
            return True
        if both and header is None:
            header = index
    return header is not None and any(DIGITS.search(line) for line in lines[header + 1:])


def _json_records_have_identity_map(content: str) -> bool:
    """Any record holding both a study code and an identifier, with a value in it."""
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        return False
    if isinstance(data, dict):
        records = [r for value in data.values() if isinstance(value, list) for r in value]
        records.append(data)
    elif isinstance(data, list):
        records = data
    else:
        return False
    for record in records:
        if not isinstance(record, dict):
            continue
        keys = " ".join(str(k) for k in record)
        values = " ".join(str(v) for v in record.values())
        if STUDY_KEY.search(keys) and IDENTITY_KEY.search(keys) and re.search(r"[A-Za-z0-9一-鿿]{2,}", values):
            return True
    return False


def _has_identity_map(content: str, suffix: str) -> bool:
    if suffix == ".json":
        return _json_records_have_identity_map(content)
    return _line_record_has_identity_map(content)


def evaluate(target: Target) -> list[Finding]:
    path_low = target.path.lower()
    suffix = Path(path_low).suffix
    findings: list[Finding] = []
    allowlisted = _is_allowlisted_exposed(target.path)
    fixture_reason = FIXTURE_PATHS.get(target.path)

    for rule, category, pattern in SENSITIVE_PATH_RULES:
        if re.search(pattern, target.path, re.IGNORECASE):
            findings.append(Finding("BLOCK", rule, category, target.path,
                                    detail=f"path matches a never-publish pattern for {CATEGORIES[category]}"))

    if target.content is None:
        if target.changed:
            findings.append(Finding(
                "BLOCK", "B01", "uninspectable", target.path,
                detail=f"{target.reason_uninspectable}; a human decision (--accept-uninspected-binary) "
                       f"is required before this file is published"))
        else:
            findings.append(Finding(
                "INFO", "B01", "uninspectable", target.path,
                detail=f"{target.reason_uninspectable}; already tracked in HEAD, so this commit adds no "
                       f"new exposure - its content still needs a human check once"))
        return findings

    content = target.content
    lines = content.splitlines()

    for rule, pattern in SECRET_RULES:
        for lineno, line in enumerate(lines, start=1):
            m = re.search(pattern, line)
            if not m:
                continue
            if rule == "C01" and _looks_like_placeholder(m.group(2)):
                continue
            if fixture_reason:
                findings.append(Finding("INFO", rule, "server_key", target.path, lineno,
                                        detail=f"credential-looking value in a recorded fixture: {fixture_reason}"))
            else:
                findings.append(Finding("BLOCK", rule, "server_key", target.path, lineno,
                                        detail="a credential-looking value; a key belongs in a mode-600 file under "
                                               "~/.config/clinpath/, never in this repository"))

    for rule, category, pattern in PERSONAL_RULES:
        for lineno, line in enumerate(lines, start=1):
            if re.search(pattern, line):
                severity = "INFO" if fixture_reason else "BLOCK"
                detail = (fixture_reason if fixture_reason else
                          "an identifier a real student record would contain; real data belongs in the "
                          "controlled environment, not in this repository")
                findings.append(Finding(severity, rule, category, target.path, lineno, detail=detail))

    if suffix in IDENTITY_DATA_SUFFIXES and _has_identity_map(content, suffix):
        findings.append(Finding("BLOCK", "C08", "identity_map", target.path,
                                detail="a record pairing a study code with a name/student number: the L1 "
                                       "linkage table must live only in the controlled environment"))

    if any(hint in path_low for hint in PRIVATE_APP_PATH_HINTS):
        for lineno, line in enumerate(lines, start=1):
            match = APPLICANT_ROLE.search(line)
            if match and "【待填" not in line:
                findings.append(Finding("BLOCK", "C09", "private_application_details", target.path, lineno,
                                        detail="a person named as applicant/holder: the public application text "
                                               "uses the 【待填：…】 placeholder instead"))

    for lineno, line in enumerate(lines, start=1):
        if ETHICS_PERSONAL.search(line) or SIGNATURE_BLOCK.search(line):
            findings.append(Finding("BLOCK", "C10", "ethics_personal_info", target.path, lineno,
                                    detail="a filled-in signature block: consent forms carrying real identities "
                                           "stay on paper outside the repository"))

    exam_signal = ((suffix in DOC_OR_DATA_SUFFIXES and any(h in path_low for h in EXAM_PATH_HINTS))
                   or _exam_form_shape(content))
    markers = sorted({m for m in ANSWER_CONTENT_MARKERS if m.lower() in content.lower()})
    if allowlisted:
        findings.append(Finding("INFO", "E00", "exposed_dev_sample", target.path,
                                detail="already public before this round; may stay only as a clearly "
                                       f"labelled development/demo sample (markers: {markers or 'none'})"))
    elif exam_signal:
        findings.append(Finding("BLOCK", "E01", "unreleased_exam_form", target.path,
                                detail=f"an assessment-form-shaped file at a path with no recorded exposure "
                                       f"decision (markers: {markers or 'none'}). An un-released form belongs "
                                       f"in the controlled environment; an already-public development draft "
                                       f"belongs in EXPOSED_DEV_SAMPLES with a recorded decision"))

    if exam_signal and markers and not allowlisted:
        findings.append(Finding("BLOCK", "E03", "standard_answer_or_anchor", target.path,
                                detail=f"answer/anchoring markers in an exam-bearing file: {markers}"))

    if allowlisted and suffix in LABELABLE_SUFFIXES and not EXPOSURE_LABEL.search(content):
        findings.append(Finding("BLOCK" if target.changed else "WARN", "E04", "exposed_dev_sample", target.path,
                                detail="an exposed dev draft carries no exposure/demo label; it must be labelled "
                                       "as a development/demo sample so it is never mistaken for a secure exam item"))

    if allowlisted:
        recorded = EXPOSED_DEV_SAMPLES[target.path]
        if recorded and recorded != target.sha256:
            findings.append(Finding("WARN", "E05", "exposed_dev_sample", target.path,
                                    detail="content changed since the exposure record; a human must confirm no new "
                                           "confidential material entered this already-exposed path"))
    return findings


# ------------------------------------------------------------------------------------------
# reporting
# ------------------------------------------------------------------------------------------
LIMITS = [
    "static text scan only: it cannot detect a re-worded form that shares no markers",
    "it never inspects images, DOCX/PDF or archives' interiors",
    "it cannot undo exposure: content already pushed to the public remote stays exposed",
    "it does not read files outside git (the private controlled environment is out of scope)",
    "it cannot observe whether a form was photographed or shared verbally",
    "a pass means 'no detected sensitive content in this scope', never 'no leakage risk'",
]


def _counts(findings: list[Finding]) -> dict[str, int]:
    return {s: sum(1 for f in findings if f.severity == s) for s in ("BLOCK", "WARN", "INFO")}


def render(report: Report, show_allowlist: bool = False) -> str:
    counts = _counts(report.findings)
    inspected = sum(1 for t in report.targets if t.content is not None)
    uninspectable = len(report.targets) - inspected
    out = [
        f"publish-safety scan --scope {report.scope}",
        f"scope      : {report.inspection}",
        f"targets    : {len(report.targets)} ({inspected} content-inspected, {uninspectable} not inspectable)",
        f"findings   : BLOCK={counts['BLOCK']} WARN={counts['WARN']} INFO={counts['INFO']}",
        "",
    ]
    for f in sorted(report.findings, key=lambda x: ({"BLOCK": 0, "WARN": 1, "INFO": 2}[x.severity], x.path, x.line or 0)):
        loc = f"{f.path}:{f.line}" if f.line else f.path
        out.append(f"[{f.severity}] {f.rule} {CATEGORIES[f.category]} <- {loc}")
        if f.detail:
            out.append(f"         {f.detail}")
    if report.findings:
        out.append("")
    out += ["not inspected by this scan (limits):"] + [f"  - {line}" for line in LIMITS]
    if show_allowlist:
        out += ["", "recorded exposure of already-public exam bearing paths:"]
        for path, recorded in sorted(EXPOSED_DEV_SAMPLES.items()):
            out.append(f"  {path}  recorded_sha256={recorded or '(not yet recorded)'}")
    return "\n".join(out)


def as_json(report: Report) -> str:
    counts = _counts(report.findings)
    return json.dumps({
        "scope": report.scope,
        "inspection": report.inspection,
        "targets": [{"path": t.path, "changed": t.changed, "inspected": t.content is not None,
                     "sha256": t.sha256} for t in report.targets],
        "counts": counts,
        "findings": [{"severity": f.severity, "rule": f.rule, "category": f.category,
                      "category_zh": CATEGORIES[f.category], "path": f.path, "line": f.line,
                      "detail": f.detail} for f in report.findings],
        "limits": LIMITS,
        "exposed_dev_samples": EXPOSED_DEV_SAMPLES,
    }, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--scope", choices=("staged", "range", "tree"), default="tree")
    parser.add_argument("--range", dest="rev_range", default=None, help="A..B, with --scope range")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--show-allowlist", action="store_true")
    parser.add_argument("--accept-uninspected-binary", action="store_true",
                        help="downgrade binary files to WARN after an explicit human decision")
    args = parser.parse_args(argv)
    try:
        targets, inspection = collect_targets(args.repo_root, args.scope, args.rev_range)
    except ScanError as exc:
        print(f"ERROR (fail closed): {exc}", file=sys.stderr)
        return 2
    report = Report(args.scope, inspection)
    report.targets = targets
    for target in targets:
        report.findings.extend(evaluate(target))
    if args.accept_uninspected_binary:
        for f in report.findings:
            if f.rule == "B01":
                f.severity = "WARN"
    print(as_json(report) if args.json else render(report, args.show_allowlist))
    return 1 if any(f.severity == "BLOCK" for f in report.findings) else 0


if __name__ == "__main__":
    sys.exit(main())
