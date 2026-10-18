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

Beyond the character counts it also runs the R7.4 mechanical content checks on the
six sections (``content_checks``): exact project title, the four status words,
no completed-study / efficacy / ethics-approval claims, no in-class random grouping,
no retired AOSD case or unconditional "minimum p = 2/35", D1/T0 not feeding the
competency profile, D4/D5 recommendations tied to D2/D3 evidence, and conspicuous
``【待填：…】`` markers for every applicant-only fact.

Exit codes: 0 pass, 1 any failed check, 2 the document (or any required section)
is missing -- a missing key document is never a pass.

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

PROJECT_TITLE = "基于人工智能辅助临床推理训练的医学生个性化学习与形成性评价教学改革研究"
TITLE_STEM = "基于人工智能辅助临床推理训练"
STATUS_WORDS = ("已实现", "已通过技术测试", "待真实教师审核", "计划开展")
LEGACY_PLACEHOLDER = "〔待用户填写"
PLACEHOLDER = "【待填"

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

    section_text = "\n".join(
        "\n".join(body) for _, heading, body in found
        if any(strip_numbering(heading) == n or n in strip_numbering(heading) for n, _ in SECTIONS)
    )
    content = content_checks(text, section_text)

    total_count = sum(r["count"] for r in results if r["count"] is not None)
    total_limit = sum(r["limit"] for r in results)
    ok = all(r["status"] == "PASS" for r in results) and all(c["ok"] for c in content)
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
        "content": content,
    }



# (pattern, why). A match is ignored when a negation sits just before it, so the
# honest sentence "尚未取得伦理批件" never trips the "claims ethics approval" rule.
FORBIDDEN_IN_SECTIONS: tuple[tuple[str, str], ...] = (
    (r"(已完成|已开展|已实施|已纳入|已招募|已收集|已获得)[^。；，]{0,10}(学生|受试|49|批次|真实数据|研究数据|教学研究)",
     "把尚未开始的真实研究写成已完成"),
    (r"(显著(提升|提高|改善|优于)|疗效|效果显著|证明[^。]{0,8}有效)", "效果性表述"),
    (r"[Pp]\s*[<＜≤=＝]\s*0?\.\d", "出现具体 P 值"),
    (r"(已(获|取得|通过|获得)[^。；，]{0,6}伦理|伦理[^。；，]{0,6}(已获批|已批准|已通过|已取得批件))", "声称已取得伦理批准"),
    (r"批件号\s*[:：]?\s*[A-Za-z0-9\-—_/]{3,}", "出现批件号"),
    (r"(班内|批内)\s*(随机|分组|分层)|拆分(为|成)?[^。；]{0,6}两(组|种)", "出现班内/批内随机分组"),
    (r"AOSD|成人\s*Still|Still\s*病", "旧 AOSD 题本出现在现行正文"),
    (r"最小[^。；]{0,8}双侧\s*[Pp][^。；]{0,6}2\s*/\s*35", "无条件宣称最小双侧 P 为 2/35"),
    (r"(合成|虚拟|SYNTHETIC|模拟)[^。；]{0,24}(疗效|效果|显著|提升|有效)", "合成数据被写成效果"),
    (r"〔待用户填写", "仍使用旧式占位符，请改为【待填：…】"),
)
NEGATIONS = ("未", "尚未", "没有", "无", "不", "非", "否", "禁止", "不得", "前", "拟", "计划", "待")


def _negated(text: str, start: int) -> bool:
    window = text[max(0, start - 8) : start]
    return any(n in window for n in NEGATIONS)


def content_checks(doc_text: str, section_text: str) -> list[dict]:
    """R7.4 mechanical checks. Each result is {name, ok, detail}."""
    results: list[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        results.append({"name": name, "ok": ok, "detail": detail})

    # 1. exact title, everywhere it is (partly) quoted
    bad_lines = [
        ln.strip()[:60]
        for ln in doc_text.splitlines()
        if TITLE_STEM in ln and PROJECT_TITLE not in ln
    ]
    add("项目名称全文一致", PROJECT_TITLE in doc_text and not bad_lines,
        "未出现正式名称" if PROJECT_TITLE not in doc_text else "；".join(bad_lines))

    # 2. four status words in the six sections
    missing_words = [w for w in STATUS_WORDS if w not in section_text]
    add("四种状态用词齐全", not missing_words, "缺：" + "、".join(missing_words))

    # 3. forbidden claims (negation aware)
    for pattern, why in FORBIDDEN_IN_SECTIONS:
        hits = []
        for m in re.finditer(pattern, section_text):
            if pattern.startswith("〔") or not _negated(section_text, m.start()):
                hits.append(m.group(0)[:30])
        add(f"禁止项：{why}", not hits, "；".join(hits[:3]))

    # 4. required honest statements
    required = (
        ("D1/T0 不进入能力画像", r"T0[^。]{0,12}不[^。]{0,10}(能力画像|画像)"),
        ("D4/D5 推荐来自 D2/D3 形成性证据", r"D4[^。]{0,16}D2[^。]{0,6}D3[^。]{0,16}(证据|表现)"),
        ("整批 35 种分配 / 3+4", r"3批[^。]{0,16}4批[^。]{0,24}35种"),
        ("随机不可行时改准实验", r"准实验"),
        ("真实研究未启动、无效果数据", r"(未启动|尚未启动)[^。]{0,16}无[^。]{0,8}效果数据"),
        ("伦理状态真实（尚无批件）", r"(尚无批件|尚未取得|尚未提交)"),
        ("70/49/21 人群待申请人确认", r"21人[^。]{0,24}【待填"),
        ("荣誉须附待填标记", r"最佳带教老师[^。]{0,40}【待填"),
        ("单位承诺为待填", r"单位承诺[:：]\s*【待填"),
        ("探索性定位", r"探索性"),
    )
    for name, pattern in required:
        add(f"必含：{name}", re.search(pattern, section_text) is not None)

    add("存在醒目的【待填】标记", PLACEHOLDER in section_text)
    return results


def update_declarations(doc: Path) -> None:
    """Rewrite each section's declaration line with the real count and limit."""
    if not doc.is_file():
        raise FileNotFoundError(f"document not found: {doc}")
    lines = doc.read_text(encoding="utf-8").splitlines()
    for idx, _heading, body in split_sections("\n".join(lines)):
        name = next((n for n, _ in SECTIONS if n in strip_numbering(_heading)), None)
        if name is None:
            continue
        limit = dict(SECTIONS)[name]
        count = count_chars(body)
        for offset, raw in enumerate(body):
            if DECL_RE.match(raw.strip()):
                lines[idx + 1 + offset] = f"> 字数：{count} / 上限 {limit}"
                break
    doc.write_text("\n".join(lines) + "\n", encoding="utf-8")


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

    out.append("")
    out.append("内容机械检查（R7.4）：")
    for c in report.get("content", []):
        out.append(f"  {'PASS' if c['ok'] else 'FAIL'}  {c['name']}" + (f"  → {c['detail']}" if c["detail"] and not c["ok"] else ""))

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
    parser.add_argument(
        "--update-declarations",
        action="store_true",
        help="把每节「字数：N / 上限 M」声明改写为实际计数（只改声明行，不改正文）",
    )
    args = parser.parse_args(argv)

    if args.update_declarations:
        try:
            update_declarations(args.doc)
        except FileNotFoundError as exc:
            print(f"错误：{exc}", file=sys.stderr)
            return 2

    try:
        report = check(args.doc)
    except FileNotFoundError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))

    if report["missing"]:
        return 2
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
