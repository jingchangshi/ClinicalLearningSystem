#!/usr/bin/env python3.11
"""Check the six mandatory sections of the 2026 grant application text.

The document is `docs/teaching_grant_2026/evidence/E5_protocol/E5_04_application_text.md`.
Each of the six required sections carries a declaration line of the form

    > 字数：587 / 上限 600

immediately after its heading. This script

1. locates the six sections by their headings (exact name, or the name contained
   in a numbered heading such as ``## 一、项目研究基础``);
2. counts every non-whitespace character of the section body, excluding the
   heading, the declaration line and Markdown horizontal rules (``---``);
3. compares the count against the official limit, and against the number the
   declaration line claims, so a stale declaration is a failure rather than a
   silent lie;
4. prints a PASS/FAIL table plus a total, and exits non-zero if any section is
   missing, over its limit, or declares a number that does not match.

Counting every non-whitespace character (punctuation, digits and Latin letters
included) is deliberately stricter than counting only CJK characters: a document
that passes here also passes a "汉字 only" count.

Standard library only. It never imports the application and never touches a
database; it reads one Markdown file.

Usage
-----
    python3.11 scripts/grant/check_application_text.py
    python3.11 scripts/grant/check_application_text.py --json
    python3.11 scripts/grant/check_application_text.py --doc path/to/file.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# (section name as used in the official template, character limit)
SECTIONS: tuple[tuple[str, int], ...] = (
    ("项目研究基础", 600),
    ("拟解决的重点问题", 600),
    ("项目工作思路与举措", 1000),
    ("项目特色与创新", 300),
    ("具体实施计划及预期成果", 600),
    ("政策支持与经费保障", 800),
)

DEFAULT_DOC = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "teaching_grant_2026"
    / "evidence"
    / "E5_protocol"
    / "E5_04_application_text.md"
)

DECL_RE = re.compile(r"^>\s*字数：\s*(\d+)\s*/\s*上限\s*(\d+)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# Leading enumerations a heading may carry: 一、 / 1. / 1、 / （一） / (1)
NUMBERING_RE = re.compile(
    r"^(?:[一二三四五六七八九十]+[、.]|\d+[、.]|（[一二三四五六七八九十]+）|\(\d+\))\s*"
)


def display_width(text: str) -> int:
    """Terminal width, counting East-Asian wide characters as two columns."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def pad(text: str, width: int) -> str:
    """Left-align `text` in a field `width` columns wide (CJK-aware)."""
    return text + " " * max(0, width - display_width(text))


def pad_left(text: str, width: int) -> str:
    """Right-align `text` in a field `width` columns wide (CJK-aware)."""
    return " " * max(0, width - display_width(text)) + text


def strip_numbering(heading: str) -> str:
    """`一、项目研究基础` -> `项目研究基础`."""
    return NUMBERING_RE.sub("", heading).strip()


def count_chars(body_lines: list[str]) -> int:
    """Non-whitespace characters in the section body.

    Blank lines, the ``> 字数：...`` declaration and Markdown horizontal rules
    are structural, not prose, and are dropped before counting.
    """
    kept: list[str] = []
    for raw in body_lines:
        line = raw.strip()
        if not line:
            continue
        if line == "---":
            continue
        if DECL_RE.match(line):
            continue
        kept.append(line)
    text = "".join(kept)
    return sum(1 for ch in text if not ch.isspace())


def split_sections(text: str) -> list[tuple[int, str, list[str]]]:
    """Return (line_index, heading_text, body_lines) for every heading.

    A body runs until the next heading of the same or a higher level.
    """
    lines = text.splitlines()
    headings: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            headings.append((idx, len(match.group(1)), match.group(2)))

    sections: list[tuple[int, str, list[str]]] = []
    for pos, (idx, level, heading) in enumerate(headings):
        end = len(lines)
        for later_idx, later_level, _ in headings[pos + 1 :]:
            if later_level <= level:
                end = later_idx
                break
        sections.append((idx, heading, lines[idx + 1 : end]))
    return sections


def check(doc: Path) -> dict:
    if not doc.is_file():
        raise FileNotFoundError(f"document not found: {doc}")

    text = doc.read_text(encoding="utf-8")
    found = split_sections(text)

    results: list[dict] = []
    for name, limit in SECTIONS:
        match = None
        for _, heading, body in found:
            plain = strip_numbering(heading)
            if plain == name or name in plain:
                match = (heading, body)
                break

        if match is None:
            results.append(
                {
                    "section": name,
                    "limit": limit,
                    "count": None,
                    "declared": None,
                    "declared_limit": None,
                    "remaining": None,
                    "status": "MISSING",
                    "detail": "未找到该栏目标题",
                }
            )
            continue

        heading, body = match
        count = count_chars(body)

        declared = declared_limit = None
        for raw in body:
            decl = DECL_RE.match(raw.strip())
            if decl:
                declared = int(decl.group(1))
                declared_limit = int(decl.group(2))
                break

        problems: list[str] = []
        if declared is None:
            problems.append("缺少「字数」声明行")
        else:
            if declared != count:
                problems.append(f"声明 {declared} 与实际 {count} 不符")
            if declared_limit != limit:
                problems.append(f"声明上限 {declared_limit} 与模板上限 {limit} 不符")

        over = count > limit
        if over:
            problems.append(f"超出上限 {count - limit} 字")

        results.append(
            {
                "section": name,
                "heading": heading,
                "limit": limit,
                "count": count,
                "declared": declared,
                "declared_limit": declared_limit,
                "remaining": limit - count,
                "status": "FAIL" if problems else "PASS",
                "detail": "；".join(problems),
            }
        )

    total_count = sum(r["count"] for r in results if r["count"] is not None)
    total_limit = sum(r["limit"] for r in results)
    ok = all(r["status"] == "PASS" for r in results)
    missing = [r["section"] for r in results if r["status"] == "MISSING"]

    return {
        "document": str(doc),
        "ok": ok,
        "sections": results,
        "total": {
            "count": total_count,
            "limit": total_limit,
            "remaining": total_limit - total_count,
        },
        "missing": missing,
    }


def render(report: dict) -> str:
    header = (
        pad("栏目", 24)
        + pad_left("字数", 8)
        + pad_left("上限", 8)
        + pad_left("余量", 8)
        + "  结果"
    )
    rule = "-" * (display_width(header) + 2)
    out = [header, rule]

    for row in report["sections"]:
        count = "—" if row["count"] is None else str(row["count"])
        remaining = "—" if row["remaining"] is None else str(row["remaining"])
        line = (
            pad(row["section"], 24)
            + pad_left(count, 8)
            + pad_left(str(row["limit"]), 8)
            + pad_left(remaining, 8)
            + "  "
            + row["status"]
        )
        if row["detail"]:
            line += "  " + row["detail"]
        out.append(line)

    total = report["total"]
    out.append(rule)
    out.append(
        pad("合计", 24)
        + pad_left(str(total["count"]), 8)
        + pad_left(str(total["limit"]), 8)
        + pad_left(str(total["remaining"]), 8)
        + "  "
        + ("PASS" if report["ok"] else "FAIL")
    )

    if report["missing"]:
        out.append("")
        out.append("缺失栏目：" + "、".join(report["missing"]))

    out.append("")
    out.append(
        "计数口径：栏目正文的非空白字符（含标点、数字、英文），"
        "不含标题、「字数」声明行与 Markdown 分隔线。"
    )
    out.append("结论：" + ("全部栏目在限内且声明一致。" if report["ok"] else "存在未通过项。"))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="检查申报书六个栏目的字数是否在官方上限内。"
    )
    parser.add_argument(
        "--doc",
        type=Path,
        default=DEFAULT_DOC,
        help=f"待检查的 Markdown 文件（默认：{DEFAULT_DOC}）",
    )
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    try:
        report = check(args.doc)
    except FileNotFoundError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
