#!/usr/bin/env python3
"""Global consistency check: no *current* document may still offer 方案 B.

The applicant's teaching organisation forbids splitting a 7-student batch into two
arms, so the study is locked to whole-batch cluster allocation (方案 A). 方案 B may
survive only inside historical revision notes, and there it must be marked 已否决.

This script is deliberately a *text* check: the failure mode it guards against is
a document that quietly keeps recommending the rejected design, or keeps quoting
its numbers, after the decision was made. A human reading one file would miss it.

Files scanned = the current, in-force documents. Files exempt = the historical
revision notes (v1/v2), which are allowed to describe what was once proposed.

Usage::

    python3 scripts/grant/check_protocol_consistency.py [--json]

Exit codes: 0 clean, 1 violations found.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRANT = REPO_ROOT / "docs" / "teaching_grant_2026"

# Documents that are in force. 方案 B must not be recommended or left open here.
CURRENT_DOCUMENTS = [
    "STATUS.md",
    "EVIDENCE_INDEX.md",
    "TEACHER_REVIEW_PACKET.md",
    "evidence/E5_protocol/E5_01_research_protocol.md",
    "evidence/E5_protocol/E5_02_SAP_statistical_analysis_plan.md",
    "evidence/E5_protocol/E5_03_ethics_privacy.md",
    "evidence/E5_protocol/E5_04_application_text.md",
    "evidence/E5_protocol/E5_04_placeholders.md",
    "evidence/E5_protocol/E5_protocol_data_dictionary.md",
    "evidence/E5_protocol/STATUS_E5.md",
    "evidence/E5_protocol/T2_7day_teaching_plan.md",
    "evidence/E5_protocol/T3_design_comparison.md",
    "evidence/E5_protocol/T3_personalization_validation.md",
    "workpackages/A_cases/A04_assessment_quality_control.md",
]

# Historical records: allowed to describe 方案 B, but must mark it rejected.
HISTORICAL_DOCUMENTS = [
    "evidence/E5_protocol/PROTOCOL_REVISION_NOTES_v1.md",
    "evidence/E5_protocol/PROTOCOL_REVISION_NOTES_v2.md",
    "evidence/E5_protocol/PROTOCOL_REVISION_NOTES_v3.md",
]

# 方案 B artefacts that must not be cited as part of the current plan.
FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"推荐方案\s*B", "recommends 方案 B"),
    (r"方案\s*B\s*为(推荐|优先|首选)", "names 方案 B as the preferred design"),
    (r"方案\s*B\s*必须", "treats 方案 B as required"),
    (r"待(教研室)?确认.{0,20}方案\s*[AB]", "leaves the A/B choice open"),
    (r"(是否|能否)(允许|采用).{0,12}班内(随机|分组)", "leaves within-batch allocation open"),
    (r"班内\s*3\s*[+＋]\s*4", "cites the rejected within-batch 3+4 split"),
    (r"每批\s*7\s*人(内部|内)\s*3", "cites the rejected within-batch split"),
    # 24/25 is only a violation when it describes *arm* sizes; the same numbers
    # legitimately describe the X/Y form-order split under whole-batch allocation.
    (r"(?=.*24\s*(?:vs|比|:|：)\s*25)(?=.*(?:每臂|两臂|组别|干预组|对照组)).*",
     "cites 方案 B's 24 vs 25 arm sizes"),
    (r"35\s*[\^⁷]|6\.4\s*[×x]\s*10", "cites 方案 B's 35^7 permutation space"),
    (r"Monte\s*Carlo\s*置换", "cites 方案 B's Monte Carlo permutation test"),
    (r"分层置换检验", "cites 方案 B's stratified permutation test"),
    (r"残差自由度\s*=?\s*40|df\s*=\s*40", "cites 方案 B's residual df of 40"),
    # Plan A must say batch fixed effects are NOT estimable; flagging the phrase
    # unconditionally would flag that correct statement too, so negations are
    # handled by REJECTION_MARKERS below.
    (r"批次固定效应", "cites 方案 B's batch fixed effects as a model term"),
    # Plan B's figure was d ~ 0.81; plan A's is d ~ 0.87, so match the exact
    # plan-B value rather than a prefix (0.8 would also match 0.87).
    (r"d\s*[≈=]\s*0\.81\b", "cites an individual-level power figure for 方案 B"),
]

# A line may mention a forbidden pattern only if it is explicitly rejecting it.
# A line is not a violation if it is rejecting/negating the thing it mentions.
REJECTION_MARKERS = (
    "已否决", "被否决", "否决", "已删除", "作废", "不再", "不得", "禁止", "曾提出", "历史",
    # Negations that make a mention correct rather than a violation.
    "不可估", "不可识别", "共线", "不能", "无法", "删除", "不是",
)


def _scan(path: Path) -> list[dict]:
    """Scan one document.

    A mention is acceptable when the line itself rejects it, or when it sits in a
    table whose header (or the nearest preceding heading) marks the whole block as
    superseded — e.g. a "v2.0（作废） vs v3.0（现行）" comparison table. Without the
    table-context rule, documenting *what was rejected* would itself be flagged.
    """

    violations: list[dict] = []
    text = path.read_text(encoding="utf-8")
    table_exempt = False
    previous_was_table = False

    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        is_table_row = stripped.startswith("|")

        if is_table_row and not previous_was_table:
            # First row of a new table: its header decides the whole table.
            table_exempt = any(marker in line for marker in REJECTION_MARKERS)
        elif not is_table_row:
            table_exempt = False

        for pattern, why in FORBIDDEN_PATTERNS:
            if not re.search(pattern, line):
                continue
            if any(marker in line for marker in REJECTION_MARKERS):
                continue
            if table_exempt:
                continue
            violations.append(
                {"file": str(path.relative_to(REPO_ROOT)), "line": number, "why": why, "text": stripped[:160]}
            )

        previous_was_table = is_table_row

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    violations: list[dict] = []
    checked: list[str] = []
    missing: list[str] = []

    for relative in CURRENT_DOCUMENTS:
        path = GRANT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        checked.append(relative)
        violations.extend(_scan(path))

    # The historical notes must mark 方案 B as rejected.
    history_problems: list[str] = []
    for relative in HISTORICAL_DOCUMENTS:
        path = GRANT / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if "方案 B" in text or "方案B" in text:
            if not any(marker in text for marker in ("已否决", "已删除", "作废")):
                history_problems.append(f"{relative}: mentions 方案 B without marking it rejected")

    if args.json:
        print(json.dumps(
            {"checked": checked, "missing": missing, "violations": violations, "history": history_problems},
            ensure_ascii=False, indent=2,
        ))
    else:
        print("方案 A 唯一设计一致性检查")
        print("=" * 78)
        print(f"已扫描现行文档：{len(checked)} 份")
        for relative in checked:
            print(f"  - {relative}")
        if missing:
            print("\n未找到（跳过）：")
            for relative in missing:
                print(f"  ! {relative}")
        print()
        if violations:
            print(f"发现 {len(violations)} 处仍引用方案 B：")
            for item in violations:
                print(f"  FAIL {item['file']}:{item['line']}  [{item['why']}]")
                print(f"       {item['text']}")
        else:
            print("PASS 现行文档中未发现将方案 B 作为推荐、主模型或待确认事项的表述")
        if history_problems:
            print("\n历史修订记录问题：")
            for problem in history_problems:
                print(f"  FAIL {problem}")
        elif any((GRANT / h).is_file() for h in HISTORICAL_DOCUMENTS):
            print("PASS 历史修订记录中的方案 B 已标记为已否决")
        print()

    failed = bool(violations or history_problems)
    if not args.json:
        print("结论：" + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
