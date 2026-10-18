#!/usr/bin/env python3
"""Technical validator for the independent-assessment form payloads (CASE-A01 / CASE-A02).

This is a *technical* check. It cannot and does not establish medical correctness:
every payload stays PENDING_REAL_REVIEW until two real rheumatology teachers sign.

Checks per payload file:
  * valid JSON with the keys the ``POST /api/assessments/forms`` body needs
    (code, title, stages, answer_key, rubric) and nothing structurally odd,
  * exactly 5 stages, each with non-empty title / clinical_information / question
    and no other keys (so no hidden field can ride along into a stage),
  * ``rubric.status`` is PENDING_REAL_REVIEW (never an approval claim),
  * the six research dimensions with weights 10/20/25/15/20/10 summing to 100,
  * a high / mid / low anchor for every dimension, weight matching ``dimensions``,
  * a non-empty ``answer_key`` that declares ``leak_terms_forbidden_in_student_fields``,
  * no answer-key content in anything a student sees (form title and every stage's
    title / clinical_information / question): declared leak terms, and generic
    interpretation phrases such as a stated diagnosis or "does not meet criteria".

Pair-level checks (when both A01 and A02 are present): distinct codes and the same
five-stage structure.

Missing files, unreadable JSON and an empty file list are failures (non-zero exit),
never silent passes.

Usage:
    python3 -I scripts/grant/validate_assessment_payloads.py
    python3 -I scripts/grant/validate_assessment_payloads.py --json
    python3 -I scripts/grant/validate_assessment_payloads.py --file path/to/payload.json ...
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = REPO_ROOT / "docs" / "teaching_grant_2026" / "workpackages" / "A_cases"
DEFAULT_FILES = (
    CASE_DIR / "A01_assessment_payload_DRAFT.json",
    CASE_DIR / "A02_assessment_payload_DRAFT.json",
)

TOP_KEYS = ("code", "title", "stages", "answer_key", "rubric")
STAGE_KEYS = ("title", "clinical_information", "question")
# Research scale awaiting teacher confirmation (training weights 20/20/20/15/15/10 are separate).
RESEARCH_WEIGHTS = {
    "medical_knowledge": 10,
    "key_information": 20,
    "differential_diagnosis": 25,
    "evidence_integration": 15,
    "clinical_decision": 20,
    "evidence_based_medicine": 10,
}
ANCHOR_BANDS = ("high", "mid", "low")
CODE_RE = re.compile(r"^CASE-A0[12]-[A-Z0-9-]+$")

# Interpretation / answer phrases that must not appear in student-facing text.
GENERIC_LEAK_PATTERNS = (
    r"参考答案", r"标准答案", r"评分锚点", r"满分", r"rubric", r"answer_key",
    r"PENDING_REAL_REVIEW", r"DRAFT",
    r"诊断为", r"确诊为", r"考虑为", r"提示诊断", r"符合.{0,12}(诊断|分类)", r"不符合", r"不满足",
)


class Report:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, file: str, check: str, ok: bool, detail: str = "") -> None:
        self.rows.append({"file": file, "check": check, "ok": bool(ok), "detail": detail})

    @property
    def failed(self) -> list[dict]:
        return [r for r in self.rows if not r["ok"]]


def _is_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _student_visible(payload: dict) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    if isinstance(payload.get("title"), str):
        fields.append(("title", payload["title"]))
    for i, stage in enumerate(payload.get("stages") or [], start=1):
        if isinstance(stage, dict):
            for key in STAGE_KEYS:
                if isinstance(stage.get(key), str):
                    fields.append((f"stages[{i}].{key}", stage[key]))
    return fields


def check_payload(path: Path, report: Report) -> dict | None:
    name = path.name
    if not path.is_file():
        report.add(name, "file exists", False, f"missing: {path}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report.add(name, "valid JSON", False, str(exc))
        return None
    if not isinstance(payload, dict):
        report.add(name, "valid JSON object", False, type(payload).__name__)
        return None
    report.add(name, "valid JSON", True)

    missing = [k for k in TOP_KEYS if k not in payload]
    report.add(name, "required top-level keys", not missing, "missing: " + ", ".join(missing) if missing else "")
    code = payload.get("code")
    report.add(name, "code format", isinstance(code, str) and bool(CODE_RE.match(code)), str(code))
    report.add(name, "title non-empty", _is_text(payload.get("title")))

    # --- stages ------------------------------------------------------------------
    stages = payload.get("stages")
    stage_ok = isinstance(stages, list) and len(stages) == 5
    report.add(name, "exactly 5 stages", stage_ok, f"got {len(stages) if isinstance(stages, list) else type(stages).__name__}")
    if isinstance(stages, list):
        problems: list[str] = []
        for i, stage in enumerate(stages, start=1):
            if not isinstance(stage, dict):
                problems.append(f"stage {i} not an object")
                continue
            for key in STAGE_KEYS:
                if not _is_text(stage.get(key)):
                    problems.append(f"stage {i} missing/empty {key}")
            extra = sorted(set(stage) - set(STAGE_KEYS))
            if extra:
                problems.append(f"stage {i} has extra keys {extra}")
        report.add(name, "stage fields complete, no extra keys", not problems, "; ".join(problems))

    # --- rubric ------------------------------------------------------------------
    rubric = payload.get("rubric")
    if not isinstance(rubric, dict):
        report.add(name, "rubric object", False)
    else:
        report.add(name, "rubric.status == PENDING_REAL_REVIEW", rubric.get("status") == "PENDING_REAL_REVIEW", str(rubric.get("status")))
        dims = rubric.get("dimensions")
        weights_ok = isinstance(dims, dict) and dims == RESEARCH_WEIGHTS and sum(dims.values()) == 100
        report.add(name, "six dimensions, weights 10/20/25/15/20/10", weights_ok, json.dumps(dims, ensure_ascii=False) if not weights_ok else "")
        anchors = rubric.get("anchors")
        if not isinstance(anchors, dict):
            report.add(name, "rubric anchors present", False, "rubric.anchors missing")
        else:
            problems = []
            for key, weight in RESEARCH_WEIGHTS.items():
                anchor = anchors.get(key)
                if not isinstance(anchor, dict):
                    problems.append(f"{key}: no anchor")
                    continue
                if anchor.get("weight") != weight:
                    problems.append(f"{key}: anchor weight {anchor.get('weight')!r} != {weight}")
                for band in ANCHOR_BANDS:
                    if not _is_text(anchor.get(band)) or len(anchor[band].strip()) < 20:
                        problems.append(f"{key}: anchor band '{band}' empty or too short")
            unknown = sorted(set(anchors) - set(RESEARCH_WEIGHTS))
            if unknown:
                problems.append(f"unknown anchor dimensions {unknown}")
            report.add(name, "rubric anchors present (6 dims x high/mid/low)", not problems, "; ".join(problems))

    # --- answer key --------------------------------------------------------------
    key = payload.get("answer_key")
    leak_terms: list[str] = []
    if not isinstance(key, dict) or not key:
        report.add(name, "answer_key non-empty", False)
    else:
        report.add(name, "answer_key non-empty", True)
        declared = key.get("leak_terms_forbidden_in_student_fields")
        ok = isinstance(declared, list) and len(declared) >= 3 and all(_is_text(t) for t in declared)
        report.add(name, "answer_key declares leak terms (>=3)", ok)
        if ok:
            leak_terms = [str(t) for t in declared]
        report.add(name, "answer_key.meta marks PENDING_REAL_REVIEW",
                   isinstance(key.get("meta"), dict) and key["meta"].get("review_status") == "PENDING_REAL_REVIEW")

    # --- leakage into student-visible fields --------------------------------------
    hits: list[str] = []
    for field, text in _student_visible(payload):
        for term in leak_terms:
            if term.lower() in text.lower():
                hits.append(f"{field}: declared leak term {term!r}")
        for pattern in GENERIC_LEAK_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                hits.append(f"{field}: generic leak pattern {pattern!r}")
    report.add(name, "no answer-key content in student-visible fields", not hits, "; ".join(hits))
    return payload


def check_pair(payloads: dict[str, dict], report: Report) -> None:
    a01 = next((p for n, p in payloads.items() if n.startswith("A01")), None)
    a02 = next((p for n, p in payloads.items() if n.startswith("A02")), None)
    if a01 is None or a02 is None:
        return
    report.add("A01+A02", "distinct form codes", a01.get("code") != a02.get("code"), f"{a01.get('code')} / {a02.get('code')}")
    s1, s2 = a01.get("stages") or [], a02.get("stages") or []
    report.add("A01+A02", "parallel five-stage structure", len(s1) == len(s2) == 5)


def run(files: list[Path]) -> Report:
    report = Report()
    if not files:
        report.add("(none)", "at least one payload file given", False, "empty file list")
        return report
    loaded: dict[str, dict] = {}
    for path in files:
        payload = check_payload(path, report)
        if payload is not None:
            loaded[path.name] = payload
    check_pair(loaded, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", action="append", type=Path, help="payload JSON (repeatable); default A01+A02 drafts")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)
    files = list(args.file) if args.file else list(DEFAULT_FILES)
    report = run(files)
    failed = report.failed
    if args.json:
        print(json.dumps({"ok": not failed, "total": len(report.rows), "failed": len(failed), "rows": report.rows}, ensure_ascii=False, indent=2))
    else:
        for r in report.rows:
            print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['file']:<34} {r['check']}" + (f"  [{r['detail']}]" if r["detail"] and not r["ok"] else ""))
        print(f"\n{len(report.rows) - len(failed)}/{len(report.rows)} checks passed; overall {'PASS' if not failed else 'FAIL'}")
        print("NOTE: technical validation only; both forms remain PENDING_REAL_REVIEW (no teacher approval implied).")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
