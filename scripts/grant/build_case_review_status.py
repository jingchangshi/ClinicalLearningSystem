#!/usr/bin/env python3
"""Generate FINAL_DELIVERY/CASE_REVIEW_STATUS.md from the cases work package draft.

The draft (workpackages/A_cases/CASE_REVIEW_STATUS_DRAFT.md) is the single source;
the final file is a verbatim copy with a generated-file header, so the two can never
contradict each other. Re-run after the draft changes. Exit 2 if the draft is missing.
"""
import sys
from pathlib import Path

G = Path(__file__).resolve().parents[2] / "docs" / "teaching_grant_2026"
SRC = G / "workpackages" / "A_cases" / "CASE_REVIEW_STATUS_DRAFT.md"
DST = G / "FINAL_DELIVERY" / "CASE_REVIEW_STATUS.md"

if not SRC.is_file():
    print(f"错误：缺少 {SRC}", file=sys.stderr)
    raise SystemExit(2)
body = SRC.read_text(encoding="utf-8")
body = body.replace("# CASE_REVIEW_STATUS（草案）", "# CASE_REVIEW_STATUS", 1)
header = (
    "> **GENERATED** by `scripts/grant/build_case_review_status.py` from "
    "`workpackages/A_cases/CASE_REVIEW_STATUS_DRAFT.md`（唯一来源）。请改来源文件，不要改本文件。\n"
    "> 泄漏风险 L-1/L-2/L-3 的决策事项另见 `HUMAN_ACTION_CHECKLIST.md`（H18—H20）；待核实引用见 H21。\n\n"
)
first, rest = body.split("\n", 1)
DST.write_text(first + "\n\n" + header + rest.lstrip("\n"), encoding="utf-8")
print("写入", DST)
