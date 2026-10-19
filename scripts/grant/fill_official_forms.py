#!/usr/bin/env python3.11
"""Fill the official 申报书 (DOCX) and 申报汇总表 (XLSX or DOCX) templates.

This is the §7.3 / §7.5 pipeline. It is **label-driven**: the script locates each
field by the label the official form itself uses -- ``项目研究基础``,
``项目名称``, ``项目组主要成员``, ... -- and writes the value next to it. Labels
and values live in an editable JSON field map so the operator can correct a label
without touching code.

Attachment identity is decided by **name AND content**, never by an attachment
number. The numbering differs between republished copies (the 通知's own
attachment list numbers the 申报汇总表 as 附件3, while the distributed
spreadsheet is labelled 附件4 and there is an ``附件3=申报书匿名版`` in some
copies). So:

* the application form (申报书) is a DOCX that reads like the form -- not the
  匿名版 (an anonymised review copy must never be filled as the submission);
* the summary table (汇总表) is the file titled 申报汇总表 -- XLSX in the real
  package, DOCX tolerated -- and never the 结题验收汇总表.

Hard rules this script enforces, because a silently half-filled official form is
worse than no form at all:

* **Refuses to run without the official input files** (exit 2), listing every
  location it searched and every way to point it at the files.
* **Never fabricates a template.** It only ever writes into a copy of a real
  official file, and it refuses (exit 6) to treat one of our own generated drafts
  as official -- detected by this repository's own "非官方模板" banner.
* **Reports every expected field it cannot locate** (exit 3) instead of skipping
  it. Nothing is written unless ``--write-partial`` is passed.
* **Never invents a person.** 主持人/成员/单位/职称/出生年月/联系电话/签字/盖章
  are written as conspicuous ``【待填：…】`` markers.
* **Refuses to overwrite** a target that already carries different content unless
  ``--overwrite`` is passed; a conflict is reported, not silently replaced.
  Content that already equals the value being written is idempotent, not a
  conflict.
* **Enforces the official character limits** per section (exit 4).

Accepted inputs, tried in this order (the brief tells the applicant any of them is
fine, so all of them work):

1. ``--attachment2`` / ``--attachment3`` -- an explicit path each.
2. **The ZIP as dropped** -- ``official/ClinPath_2026_Official_Source_Templates.zip``
   or ``~/.config/clinpath/official/`` -- the two forms are located inside by
   name and content and **only those two members** are extracted, into a
   temporary directory outside the repository. The ZIP's other contents are never
   written anywhere, and members are read individually under flattened names so a
   crafted member path cannot escape that directory.
3. Already-extracted files in ``--official-dir`` (default ``official/``) or
   ``~/.config/clinpath/official/``, recognised by the same name/content rules.

Outputs (private, gitignored)::

    docs/teaching_grant_2026/APPLICATION_PACKAGE/official_out/
        浙江省2026年教改项目申报书_官方模板填写版.docx
        浙江省2026年教改项目申报汇总表_官方模板填写版.xlsx   (if the summary is XLSX)
        浙江省2026年教改项目申报汇总表_官方模板填写版.docx   (if the summary is DOCX)

The output suffix follows the input suffix: the real official summary table is an
Excel file, and rewriting it into Word would be manufacturing a layout the province
did not issue. The 通知 asks for the summary table as "Excel 版和加盖公章 PDF 版".

Usage::

    python3.11 scripts/grant/fill_official_forms.py --dry-run
    python3.11 scripts/grant/fill_official_forms.py --zip /path/to/official.zip
    python3.11 scripts/grant/fill_official_forms.py --json
    python3.11 scripts/grant/fill_official_forms.py --field-map my_map.json

Exit codes: 0 filled, 1 usage error, 2 official input missing, 3 a field label was
not found, 4 a section exceeds its limit, 5 python-docx/openpyxl unavailable, 6 the
input is not an official template, 7 a target already has different content.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

# One source of truth for the six sections, their limits and how E5_04 is parsed.
sys.path.insert(0, str(HERE))
import check_application_text as apptext  # noqa: E402

GRANT = REPO_ROOT / "docs" / "teaching_grant_2026"
PACKAGE = GRANT / "APPLICATION_PACKAGE"
OFFICIAL_DIR = PACKAGE / "official"
OUT_DIR = PACKAGE / "official_out"
SIX = GRANT / "evidence" / "E5_protocol" / "E5_04_application_text.md"

# The applicant's ZIP, and the directory the two forms are extracted into. Both are
# searched, in this order, because the brief tells the applicant either is fine.
ZIP_NAME = "ClinPath_2026_Official_Source_Templates.zip"
OFFICIAL_DIRS = (OFFICIAL_DIR, Path.home() / ".config" / "clinpath" / "official")
ZIP_CANDIDATES = tuple(directory / ZIP_NAME for directory in OFFICIAL_DIRS)

OUT_ATTACHMENT2 = OUT_DIR / "浙江省2026年教改项目申报书_官方模板填写版.docx"
OUT_ATTACHMENT3_DOCX = OUT_DIR / "浙江省2026年教改项目申报汇总表_官方模板填写版.docx"
OUT_ATTACHMENT3_XLSX = OUT_DIR / "浙江省2026年教改项目申报汇总表_官方模板填写版.xlsx"
# Kept for callers that predate the XLSX path; the summary output suffix follows
# the input suffix (see `output_path`).
OUT_ATTACHMENT3 = OUT_ATTACHMENT3_DOCX

# How a member/file is recognised. Scored, not exact-matched: the official names
# carry prefixes, punctuation and full-width colons that vary, and the attachment
# NUMBERS differ between republished copies. Tokens are labels of the document
# itself; negative weights reject documents that look similar but are not the
# form we must fill.
MEMBER_HINTS: dict[str, tuple[tuple[str, int], ...]] = {
    # 申报书 -- the submission form, not the anonymised review copy (匿名版).
    "attachment2": (("申报书", 5), ("申请书", 4), ("附件2", 3), ("附件二", 3),
                    ("匿名", -20), ("汇总表", -20), ("汇总", -20)),
    # 申报汇总表 -- Excel in the real package; never the 结题验收汇总表.
    "attachment3": (("汇总表", 5), ("汇总", 3), ("附件4", 3), ("附件四", 3),
                    ("申报书", -20), ("申请书", -20), ("结题验收", -20), ("匿名", -20)),
}

# Content confirmation: the file's own text must look like the document it claims
# to be, which is what makes attachment-number-free identification safe.
CONTENT_HINTS: dict[str, tuple[tuple[str, int], ...]] = {
    "attachment2": (("申报书", 4), ("填表说明", 3), ("立项依据", 3), ("项目研究基础", 2),
                    ("匿名", -20), ("汇总表", -20), ("结题验收", -20)),
    "attachment3": (("汇总表", 4), ("项目组主要成员", 3), ("第一完成单位", 2),
                    ("结题验收", -20), ("填写说明", -10), ("项目研究基础", -20)),
}

DOCX_SUFFIXES = (".docx",)
XLSX_SUFFIXES = (".xlsx",)
# The application form is always a Word document; the summary table may be either
# format (the real official one is Excel).
KIND_SUFFIXES: dict[str, tuple[str, ...]] = {
    "attachment2": DOCX_SUFFIXES,
    "attachment3": XLSX_SUFFIXES + DOCX_SUFFIXES,
}
# Only these suffixes can be opened by the fillers; anything else is reported.
UNREADABLE_SUFFIXES = (".doc", ".wps", ".pdf")
# A zip bomb guard: the two forms are text documents, so this is generous.
MAX_MEMBER_BYTES = 50 * 1024 * 1024

# Our own generated drafts carry this banner; seeing it means the file is not the
# official template and must never be filled as if it were.
NOT_OFFICIAL_BANNER = "非官方模板"

TITLE = "基于人工智能辅助临床推理训练的医学生个性化学习与形成性评价教学改革研究"

# Fields the Agent must never fill in: real people, real dates, real titles,
# signatures and seals. Written as conspicuous markers instead.
PENDING_HOST = "【待填：主持人姓名】"
PENDING_MEMBERS = "【待填：成员名单（不含主持人，原则上不超过8人）】"
PENDING_UNIT = "【待填：单位全称，并加盖公章】"
PENDING_CONTACT = "【待填：主持人电话与电子邮箱】"
PENDING_BIRTH = "【待填：出生年月】"
PENDING_TITLE = "【待填：专业技术职务/职称】"

# 项目方向: the 选题指南's 一级标题编号. "十、构建面向未来的高等教育新形态" holds
# "2.人工智能赋能教育教学改革研究与实践" and "3.基于 AI 的个性化学习支持、学业智能
# 诊断、学习风险预警体系建设", which is where this project sits. "九、深化教育教学评价
# 改革" ("2.人工智能赋能专业评价、学生评价的改革与实践") is the alternative. The
# applicant must confirm the choice; see OFFICIAL_APPLICATION_VALIDATION.md.
PROJECT_DIRECTION = "十"
PROJECT_DIRECTION_ALTERNATIVE = "九"
PROJECT_DIRECTION_STATUS = "待申请人确认"

# Field map. `labels` are matched against the official form's own wording, so a
# template that writes 课题名称 instead of 项目名称 only needs a label added here.
# `scope` is "table" or "paragraph" when a label occurs in both places and only one
# is the intended target (the cover's 联系电话 vs the 主持人情况 table's).
DEFAULT_FIELD_MAP: dict = {
    "attachment2": {
        "sections": [
            {"key": "项目研究基础", "limit": 600, "block": True,
             "labels": ["项目研究基础"]},
            {"key": "拟解决的重点问题", "limit": 600, "block": True,
             "labels": ["项目拟解决的重点问题", "拟解决的重点问题"]},
            {"key": "项目工作思路与举措", "limit": 1000, "block": True,
             "labels": ["项目工作思路与举措"]},
            {"key": "项目特色与创新", "limit": 300, "block": True,
             "labels": ["本项目特色与创新之处", "项目特色与创新"]},
            {"key": "具体实施计划及预期成果", "limit": 600, "block": True,
             "labels": ["具体实施计划（含进展安排）及预期成果",
                        "具体实施计划及预期成果", "具体实施计划"]},
            {"key": "政策支持与经费保障", "limit": 800, "block": True,
             "labels": ["政策支持与经费保障"]},
        ],
        "fields": [
            # The cover. Paragraph scope: 联系电话/主持人 also occur in the tables.
            {"key": "项目名称", "value": TITLE, "scope": "paragraph",
             "labels": ["项目名称", "课题名称", "项目全称"]},
            {"key": "主持人", "value": PENDING_HOST, "scope": "paragraph",
             "labels": ["主持人", "项目负责人", "负责人姓名"]},
            {"key": "项目成员", "value": PENDING_MEMBERS, "scope": "paragraph",
             "labels": ["项目成员", "团队成员", "项目组主要成员"]},
            {"key": "牵头单位", "value": PENDING_UNIT, "scope": "paragraph",
             "labels": ["牵头单位", "申报单位", "申请单位", "承担单位"]},
            {"key": "联系电话（封面）", "value": PENDING_CONTACT, "scope": "paragraph",
             "labels": ["联系电话", "联系方式"]},
            # 项目层次 / 项目类别 / 项目方向: header row, values on the row below.
            # 项目类别 is pre-filled "01" (本科) by the template and is not touched.
            {"key": "项目层次", "value": "02", "scope": "table",
             "labels": ["项目层次"]},
            {"key": "项目方向", "value": PROJECT_DIRECTION, "scope": "table",
             "labels": ["项目方向"]},
            # 主持人情况 table: identify fields, never invented.
            {"key": "主持人姓名", "value": PENDING_HOST, "scope": "table",
             "labels": ["姓名"]},
            {"key": "主持人性别", "value": "【待填：性别】", "scope": "table",
             "labels": ["性别"]},
            {"key": "主持人出生年月", "value": PENDING_BIRTH, "scope": "table",
             "labels": ["出生年月"]},
            {"key": "主持人学历学位", "value": "【待填：学历/学位】", "scope": "table",
             "labels": ["学历/学位"]},
            {"key": "主持人专业技术职务", "value": PENDING_TITLE, "scope": "table",
             "labels": ["专业技术职务"]},
            {"key": "主持人联系电话", "value": PENDING_CONTACT, "scope": "table",
             "labels": ["联系电话"]},
            {"key": "主持人工作单位及职务", "value": "【待填：工作单位及职务】",
             "scope": "table", "labels": ["工作单位及职务"]},
        ],
    },
    # The summary table is a row/column grid; values go into the first project row.
    "attachment3": {
        "sections": [],
        "fields": [
            {"key": "项目层次", "value": "02", "labels": ["项目层次"]},
            {"key": "项目方向", "value": PROJECT_DIRECTION, "labels": ["项目方向"]},
            {"key": "项目名称", "value": TITLE, "labels": ["项目名称", "课题名称"]},
            {"key": "第一完成单位", "value": PENDING_UNIT, "labels": ["第一完成单位"]},
            {"key": "主持人", "value": PENDING_HOST, "labels": ["主持人"]},
            {"key": "出生年月", "value": PENDING_BIRTH, "labels": ["出生年月"]},
            {"key": "职称", "value": PENDING_TITLE, "labels": ["职称"]},
            {"key": "管理职务", "value": "【待填：管理职务，无则填“无”】",
             "labels": ["管理职务"]},
            {"key": "项目组主要成员", "value": "【待填：成员名单，不超过8位】",
             "labels": ["项目组主要成员"]},
            {"key": "主持人是否为中层干部及以上", "value": "【待填：是/否】",
             "labels": ["主持人是否为中层干部及以上"]},
            {"key": "备注", "value": "", "labels": ["备注"]},
        ],
    },
}

# Trailing filler an empty official field is made of, e.g. "项目名称：______".
# Colons and 、 are separators, not filler: stripping them would turn
# "项目名称：" into "项目名称" and concatenate the value onto the label.
FILLER_RE = re.compile(r"[\s　_＿—－\-－…·.]*$")
# Headers that end in a structural suffix rather than the label itself.
HEADER_SUFFIX_RE = re.compile(r"[（(][^（）()]*[）)]\s*$")


# --------------------------------------------------------------------------- text


def section_texts(doc: Path = SIX) -> dict[str, list[str]]:
    """The six sections of E5_04, as the exact lines the counter counts."""
    text = doc.read_text(encoding="utf-8")
    out: dict[str, list[str]] = {}
    for _idx, heading, body in apptext.split_sections(text):
        plain = apptext.strip_numbering(heading)
        name = next((n for n, _ in apptext.SECTIONS if plain == n or n in plain), None)
        if name is None:
            continue
        lines = []
        for raw in body:
            line = raw.strip()
            if not line or line == "---" or apptext.DECL_RE.match(line):
                continue
            lines.append(line)
        out[name] = lines
    return out


def norm(value: str) -> str:
    """Normalize a label for matching: drop numbering, spacing and filler."""
    value = apptext.NUMBERING_RE.sub("", value.strip())
    value = re.sub(r"[\s　_＿…·.]+", "", value)
    return value.strip("：:（）()【】[]")


# ---------------------------------------------------------------------- dependencies


def _require_docx():
    try:
        import docx  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover - depends on the environment
        print("错误：未安装 python-docx。请用 "
              "`uv run --python 3.11 --with python-docx --with openpyxl "
              "python scripts/grant/fill_official_forms.py` 运行。",
              file=sys.stderr)
        raise SystemExit(5)


def _require_openpyxl():
    """Same lazy-import contract as python-docx: exit 5, same message shape."""
    try:
        import openpyxl  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover - depends on the environment
        print("错误：未安装 openpyxl。请用 "
              "`uv run --python 3.11 --with openpyxl --with python-docx "
              "python scripts/grant/fill_official_forms.py` 运行。",
              file=sys.stderr)
        raise SystemExit(5)


# ---------------------------------------------------------------------- docx access


def iter_tables(doc):
    """Every table, including tables nested inside cells, in document order."""
    seen = []

    def walk(tables):
        for table in tables:
            seen.append(table)
            for row in table.rows:
                for cell in _distinct_cells(row):
                    walk(cell.tables)

    walk(doc.tables)
    return seen


def _distinct_cells(row):
    """The row's cells, merged spans collapsed to one proxy each.

    python-docx repeats a merged cell once per grid column; writing through two of
    those proxies writes the same cell twice, so callers need the distinct set.
    """
    seen, out = set(), []
    for cell in row.cells:
        key = id(cell._tc)
        if key in seen:
            continue
        seen.add(key)
        out.append(cell)
    return out


def iter_paragraphs(doc):
    """Every paragraph, including those inside table cells, in document order."""
    for paragraph in doc.paragraphs:
        yield paragraph
    for table in iter_tables(doc):
        for row in table.rows:
            for cell in _distinct_cells(row):
                for paragraph in cell.paragraphs:
                    yield paragraph


def document_text(doc) -> str:
    parts = [p.text for p in iter_paragraphs(doc)]
    return "\n".join(parts)


# ------------------------------------------------------------------- field locating


def _right_cell(row, column: int):
    """The next DISTINCT cell to the right, or None."""
    cells = row.cells
    if column >= len(cells):
        return None
    current = cells[column]
    for index in range(column + 1, len(cells)):
        if cells[index]._tc is not current._tc:
            return cells[index]
    return None


def _below_cell(table, row_index: int, column: int):
    if row_index + 1 >= len(table.rows):
        return None
    cells = table.rows[row_index + 1].cells
    return cells[column] if column < len(cells) else None


def _table_index(doc, table) -> int:
    # python-docx builds a fresh proxy each time `doc.tables` is read, so compare
    # the underlying XML elements rather than the wrappers.
    for index, candidate in enumerate(iter_tables(doc), start=1):
        if candidate._tbl is table._tbl:
            return index
    return 0


def locate_in_tables(doc, labels: list[str]):
    """First cell matching a label, with the cell that should hold the value.

    Value target: the cell to the right if it is empty, otherwise the cell directly
    below if that is empty. The official forms use both layouts -- a header row
    (项目层次 / 项目类别 / 项目方向) puts the values on the row below, and a
    label/value row puts the value to the right. Preferring the *empty* candidate
    keeps a header row's neighbouring header from being overwritten.
    """
    wanted = [(label, norm(label)) for label in labels]
    candidates = []
    for table in iter_tables(doc):
        for row_index, row in enumerate(table.rows):
            for column, cell in enumerate(row.cells):
                # A merged cell repeats per grid column; only its first proxy counts.
                if column and row.cells[column - 1]._tc is cell._tc:
                    continue
                text = norm(cell.text)
                if not text:
                    continue
                for label, target in wanted:
                    if text == target:
                        candidates.append((0, len(text), label, table, row_index, column))
                    elif text.startswith(target) and len(text) <= len(target) + 12:
                        candidates.append((1, len(text), label, table, row_index, column))
                    elif target in text and len(text) <= len(target) + 12:
                        candidates.append((2, len(text), label, table, row_index, column))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    _rank, _length, label, table, row_index, column = candidates[0]
    row = table.rows[row_index]

    right = _right_cell(row, column)
    below = _below_cell(table, row_index, column)
    if right is not None and not right.text.strip():
        target, where = right, f"表{_table_index(doc, table)}第{row_index + 1}行右侧单元"
    elif below is not None and not below.text.strip():
        target, where = below, f"表{_table_index(doc, table)}第{row_index + 2}行同列单元"
    elif right is not None:
        target, where = right, f"表{_table_index(doc, table)}第{row_index + 1}行右侧单元"
    elif below is not None:
        target, where = below, f"表{_table_index(doc, table)}第{row_index + 2}行同列单元"
    else:
        return None
    return {"kind": "table-cell", "label": label, "target": target, "where": where,
            "table_index": _table_index(doc, table), "row": row_index, "col": column}


def locate_in_paragraphs(doc, labels: list[str]):
    """First paragraph matching a label.

    Two layouts: the label's own paragraph carries the value after it (``项目名称：``
    or ``项目名称：____``), or the label's paragraph is followed by an empty
    paragraph that is meant to receive the value.
    """
    wanted = [(label, norm(label)) for label in labels]
    paragraphs = list(iter_paragraphs(doc))
    candidates = []
    for index, paragraph in enumerate(paragraphs):
        text = norm(paragraph.text)
        if not text:
            continue
        for label, target in wanted:
            if text == target:
                candidates.append((0, len(text), index, label, paragraph))
            elif text.startswith(target) and len(text) <= len(target) + 6:
                candidates.append((1, len(text), index, label, paragraph))
            elif target in text and len(text) <= len(target) + 12:
                candidates.append((2, len(text), index, label, paragraph))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    _rank, _length, index, label, paragraph = candidates[0]
    # A label that already carries a colon or a blank rule wants the value on the
    # same line -- "项目名称：____" must not push the value into the next paragraph.
    if re.search(r"[：:_＿—－….]\s*$", paragraph.text.strip()):
        return {"kind": "paragraph-append", "label": label, "target": paragraph,
                "where": f"段落{index + 1}（标签同行填写）"}
    if index + 1 < len(paragraphs) and not paragraphs[index + 1].text.strip():
        return {"kind": "paragraph-next", "label": label, "target": paragraphs[index + 1],
                "where": f"段落{index + 2}（标签下一空段）"}
    return {"kind": "paragraph-append", "label": label, "target": paragraph,
            "where": f"段落{index + 1}（标签段内续写）"}


def locate(doc, labels: list[str], scope: str | None = None):
    """Tables first -- official application forms put their fields in tables.

    ``scope`` forces one of the two searches when a label occurs in both a cover
    paragraph and a table (``联系电话`` does).
    """
    if scope != "paragraph":
        hit = locate_in_tables(doc, labels)
        if hit is not None:
            return hit
    if scope != "table":
        return locate_in_paragraphs(doc, labels)
    return None


# --------------------------------------------------------------- section bodies


def _label_remainder_ok(text: str, target: str) -> bool:
    """True when `text` is the section label plus at most its official hint."""
    if text == target:
        return True
    if not text.startswith(target):
        return False
    return "不超过" in text or len(text) <= len(target) + 40


CANONICAL_SECTION_NAMES = tuple(name for name, _ in apptext.SECTIONS)
PROMPT_HINT_RE = re.compile(r"不超过\s*\d+\s*字")


def _looks_like_section_prompt(text: str) -> bool:
    normalized = norm(text)
    if not normalized:
        return False
    if PROMPT_HINT_RE.search(normalized):
        return True
    return any(normalized.startswith(norm(name)) for name in CANONICAL_SECTION_NAMES)


def locate_section_block(doc, labels: list[str]):
    """Find a section prompt and the paragraphs that are meant to hold its body.

    The real official 申报书 puts each section prompt as the first paragraph of a
    single merged cell, with paragraphs after it for the answer; the last section
    (二、政策支持与经费保障) instead puts the prompt on its own row and leaves the
    whole next row for the body. Both layouts are recognised here.

    The prompt is recognised by being the cell's FIRST paragraph, so the same hit
    is found before filling (following paragraphs empty) and after (following
    paragraphs hold the answer) -- which is what lets the validator read the count
    back out of the produced file.

    Returns a hit of kind ``cell-block`` whose ``paragraphs`` are the body slots,
    or None so the caller can fall back to the label/value layouts.
    """
    wanted = [(label, norm(label)) for label in labels]
    for table_index, table in enumerate(iter_tables(doc), start=1):
        for row_index, row in enumerate(table.rows):
            cells = _distinct_cells(row)
            for cell in cells:
                paragraphs = cell.paragraphs
                if not paragraphs:
                    continue
                text = norm(paragraphs[0].text)
                if not text:
                    continue
                match = next((label for label, target in wanted
                              if _label_remainder_ok(text, target)), None)
                if match is None:
                    continue
                trailing = list(paragraphs[1:])
                if trailing:
                    return {"kind": "cell-block", "label": match, "cell": cell,
                            "paragraphs": trailing,
                            "where": f"表{table_index}第{row_index + 1}行提示语之后的段落"}
                # Prompt alone on its row -> the whole next row is the body.
                if len(cells) == 1 and row_index + 1 < len(table.rows):
                    following = _distinct_cells(table.rows[row_index + 1])
                    if len(following) != 1:
                        continue
                    candidate = following[0].paragraphs
                    if candidate and _looks_like_section_prompt(candidate[0].text):
                        continue  # that is the next section's prompt, not a body
                    return {"kind": "cell-block", "label": match,
                            "cell": following[0],
                            "paragraphs": list(candidate),
                            "where": f"表{table_index}第{row_index + 2}行整行"}
    return None


# --------------------------------------------------------------------------- filling


def _inherit_run_format(paragraph, run) -> None:
    """Give a new run the paragraph mark's formatting (font, size, underline).

    The official template formats its answer paragraphs through ``w:pPr/w:rPr``;
    a run without its own ``rPr`` would fall back to the document default and lose
    the 仿宋_GB2312 / 黑体 setting the form relies on.
    """
    from docx.oxml.ns import qn

    p_pr = paragraph._p.pPr
    mark_rpr = p_pr.find(qn("w:rPr")) if p_pr is not None else None
    if mark_rpr is not None:
        run._element.insert(0, copy.deepcopy(mark_rpr))


def _set_paragraph_text(paragraph, text: str) -> None:
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)
    run = paragraph.add_run(text)
    _inherit_run_format(paragraph, run)


def _append_empty_paragraph(cell):
    """Clone the cell's last paragraph (keeping its pPr) as a new empty one."""
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph

    last = cell.paragraphs[-1]
    new_p = copy.deepcopy(last._p)
    for child in list(new_p):
        if child.tag in {qn("w:r"), qn("w:hyperlink"), qn("w:fldSimple"),
                         qn("w:bookmarkStart"), qn("w:bookmarkEnd")}:
            new_p.remove(child)
    last._p.addnext(new_p)
    return Paragraph(new_p, cell)


def _write_cell(cell, lines: list[str]) -> None:
    _set_paragraph_text(cell.paragraphs[0], lines[0])
    for extra in list(cell.paragraphs[1:]):
        extra._p.getparent().remove(extra._p)
    for line in lines[1:]:
        _set_paragraph_text(_append_empty_paragraph(cell), line)


def _write_block(hit: dict, lines: list[str]) -> None:
    paragraphs = list(hit["paragraphs"])
    while len(paragraphs) < len(lines):
        paragraphs.append(_append_empty_paragraph(hit["cell"]))
    for position, line in enumerate(lines):
        _set_paragraph_text(paragraphs[position], line)
    for leftover in paragraphs[len(lines):]:
        if leftover.text.strip():
            _set_paragraph_text(leftover, "")
    hit["paragraphs"] = paragraphs


def _drop_trailing_filler(paragraph) -> None:
    """Remove the runs that make up an empty field's rule, keeping the label runs."""
    while paragraph.runs:
        last = paragraph.runs[-1]
        kept = FILLER_RE.sub("", last.text)
        if kept:
            last.text = kept
            break
        last._element.getparent().remove(last._element)


def _append_to_paragraph(paragraph, lines: list[str]) -> None:
    _drop_trailing_filler(paragraph)
    run = paragraph.add_run(lines[0])
    _inherit_run_format(paragraph, run)
    for line in lines[1:]:
        run.add_break()
        run.add_text(line)


def _write_paragraph(paragraph, lines: list[str]) -> None:
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)
    run = paragraph.add_run(lines[0])
    _inherit_run_format(paragraph, run)
    for line in lines[1:]:
        paragraph.add_run().add_break()
        paragraph.add_run(line)


def apply_write(hit: dict, lines: list[str]) -> None:
    if hit["kind"] == "cell-block":
        _write_block(hit, lines)
    elif hit["kind"] == "table-cell":
        _write_cell(hit["target"], lines)
    elif hit["kind"] == "paragraph-next":
        _write_paragraph(hit["target"], lines)
    else:
        _append_to_paragraph(hit["target"], lines)


def _label_pattern(label: str) -> re.Pattern:
    """The label, tolerant of the spaces official cover lines put between chars."""
    return re.compile(r"\s*".join(re.escape(char) for char in label))


# A label may carry a parenthetical ("牵头单位（盖章）：") and separators; neither is
# part of its value.
SEPARATOR_RE = re.compile(r"^(?:[（(][^（）()]*[）)])?[\s　_＿—－\-…·.、：:]*")


def hit_body_text(hit: dict) -> str:
    """The text occupying a hit's answer area (never the prompt itself)."""
    if hit["kind"] == "cell-block":
        return "\n".join(p.text for p in hit["paragraphs"])
    if hit["kind"] == "paragraph-append":
        text = hit["target"].text
        match = _label_pattern(hit["label"]).match(text.lstrip())
        if match is None:
            return text
        return SEPARATOR_RE.sub("", text.lstrip()[match.end():])
    return hit["target"].text


def current_content(hit: dict) -> str:
    return hit_body_text(hit).strip()


# ------------------------------------------------------------------------ input files


def score_name(name: str, hints: tuple[tuple[str, int], ...]) -> int:
    """How strongly a file/member name looks like the wanted attachment."""
    base = Path(name).name
    if base.startswith("~$") or "__MACOSX" in name:
        return 0
    return sum(weight for token, weight in hints if token in base)


def score_content(text: str, hints: tuple[tuple[str, int], ...]) -> int:
    if not text:
        return 0
    return sum(weight for token, weight in hints if token in text)


def candidate_score(kind: str, name: str, text: str = "") -> int:
    """Name score plus a content confirmation; negative means 'not this form'."""
    return (score_name(name, MEMBER_HINTS[kind])
            + score_content(text, CONTENT_HINTS[kind]))


def best_match(names, hints, suffixes=DOCX_SUFFIXES, content=None):
    """Highest-scoring name with an acceptable suffix; ties go to the shorter name.

    ``content`` optionally maps a name to its document text, so a file whose name
    is ambiguous is judged by what it actually contains.
    """
    scored = []
    for name in names:
        if not Path(name).name.lower().endswith(suffixes):
            continue
        points = score_name(name, hints)
        if content is not None:
            points += score_content(content(name), hints)
        if points > 0:
            scored.append((-points, len(Path(name).name), name))
    if not scored:
        return None
    scored.sort()
    return scored[0][2]


def zip_candidates(explicit: Path | None) -> list[Path]:
    """The explicit ZIP first, then the default locations (never only one of them)."""
    ordered: list[Path] = []
    for candidate in ([explicit] if explicit is not None else []) + list(ZIP_CANDIDATES):
        if candidate not in ordered:
            ordered.append(candidate)
    return ordered


def _text_from_zip_member(archive: zipfile.ZipFile, name: str) -> str:
    """Best-effort text of a DOCX/XLSX member, without extracting it to disk."""
    try:
        data = archive.read(name)
    except (KeyError, OSError, zipfile.BadZipFile):
        return ""
    return _text_from_bytes(data)


def _text_from_bytes(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            parts = []
            for member in ("word/document.xml", "xl/sharedStrings.xml",
                           "xl/worksheets/sheet1.xml"):
                if member in bundle.namelist():
                    parts.append(bundle.read(member).decode("utf-8", "ignore"))
            return re.sub(r"<[^>]+>", " ", "\n".join(parts))
    except (zipfile.BadZipFile, OSError):
        return ""


def file_text(path: Path) -> str:
    try:
        return _text_from_bytes(path.read_bytes())
    except OSError:
        return ""


def extract_from_zip(archive_path: Path, stack) -> tuple[dict[str, Path], list[str]]:
    """Pull ONLY the 申报书 and 汇总表 out of the ZIP, into a temp dir outside the repo.

    Members are read individually and written under a flattened, sanitised name, so
    a crafted member path cannot escape the temp directory. The ZIP's other
    contents (the notice, 附件1) are never written anywhere.
    """
    notes: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        names = [info.filename for info in members]
        notes.append(f"ZIP 内含 {len(names)} 个文件")
        for label, token in (("通知", "通知"), ("附件1", "附件1"), ("选题指南", "选题指南")):
            if any(token in Path(n).name for n in names):
                notes.append(f"检测到{label}（本脚本不使用，未解压）")
        found: dict[str, Path] = {}
        for kind, hints in MEMBER_HINTS.items():
            chosen = best_match(names, hints, KIND_SUFFIXES[kind],
                                content=lambda n: _text_from_zip_member(archive, n))
            if chosen is None:
                unreadable = best_match(names, hints, UNREADABLE_SUFFIXES)
                if unreadable is not None:
                    notes.append(f"{kind}：{Path(unreadable).name} 不是 .docx/.xlsx，"
                                 "python-docx/openpyxl 无法填写，请先另存为可填写格式")
                else:
                    notes.append(f"{kind}：ZIP 内没有匹配的文件")
                continue
            info = next(item for item in members if item.filename == chosen)
            if info.file_size > MAX_MEMBER_BYTES:
                notes.append(f"{kind}：{Path(chosen).name} 超过 {MAX_MEMBER_BYTES} 字节，拒绝解压")
                continue
            if found.get("_temp") is None:
                directory = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="clinpath-official-")))
                found["_temp"] = directory
            target = found["_temp"] / Path(chosen).name
            target.write_bytes(archive.read(info))
            found[kind] = target
            notes.append(f"{kind}：解压 {Path(chosen).name}（仅此两个文件写入临时目录）")
    return found, notes


def _accepted_files(directory: Path) -> list[Path]:
    out: list[Path] = []
    for suffix in (".docx", ".xlsx"):
        out.extend(sorted(directory.glob(f"*{suffix}")))
    return out


def resolve_inputs(args, stack) -> tuple[dict[str, Path], list[str], list[str]]:
    """Return (resolved input paths, notes, every location that was searched)."""
    searched: list[str] = []
    notes: list[str] = []
    resolved: dict[str, Path] = {}

    # 1. Explicit per-file paths win outright.
    for kind, explicit in (("attachment2", args.attachment2), ("attachment3", args.attachment3)):
        if explicit is not None:
            searched.append(f"--{kind} {explicit}")
            if explicit.is_file():
                resolved[kind] = explicit
                notes.append(f"{kind}：使用命令行指定 {explicit}")

    # 2. The ZIP, which the brief tells the applicant to drop as-is.
    if len(resolved) < 2:
        for archive_path in zip_candidates(args.zip):
            searched.append(str(archive_path))
            if not archive_path.is_file():
                continue
            try:
                extracted, zip_notes = extract_from_zip(archive_path, stack)
            except (zipfile.BadZipFile, OSError) as exc:
                notes.append(f"ZIP 无法读取：{archive_path}：{exc}")
                continue
            notes.append(f"来源：ZIP {archive_path}")
            notes.extend(zip_notes)
            for kind in ("attachment2", "attachment3"):
                if kind not in resolved and kind in extracted:
                    resolved[kind] = extracted[kind]
            break

    # 3. Already-extracted files in the official directories (either name).
    if len(resolved) < 2:
        for directory in (args.official_dir, *OFFICIAL_DIRS[1:]):
            if directory is None:
                continue
            searched.append(f"{directory}/*.docx|*.xlsx")
            if not directory.is_dir():
                continue
            names = [str(path) for path in _accepted_files(directory)]
            for kind, hints in MEMBER_HINTS.items():
                if kind in resolved:
                    continue
                chosen = best_match(names, hints, KIND_SUFFIXES[kind],
                                    content=lambda name: file_text(Path(name)))
                if chosen is not None:
                    resolved[kind] = Path(chosen)
                    notes.append(f"{kind}：使用已解压的 {chosen}")

    return resolved, notes, searched


# ------------------------------------------------------------------------- plan (docx)


def find_section_hit(doc, entry: dict):
    """Section body hit: the official block layout first, then label/value cells."""
    if entry.get("block", True):
        hit = locate_section_block(doc, entry["labels"])
        if hit is not None:
            return hit
    return locate(doc, entry["labels"], entry.get("scope"))


def plan(doc, spec: dict, texts: dict[str, list[str]], overwrite: bool) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Return (writes, missing, conflicts, already) for the sections then the fields."""
    writes: list[dict] = []
    missing: list[dict] = []
    conflicts: list[dict] = []
    already: list[dict] = []

    for entry in spec.get("sections", []):
        key = entry["key"]
        lines = texts.get(key)
        if not lines:
            missing.append({"group": "section", "key": key, "reason": "E5_04 中找不到该栏正文"})
            continue
        hit = find_section_hit(doc, entry)
        if hit is None:
            missing.append({"group": "section", "key": key,
                            "reason": f"官方模板中找不到标签：{'、'.join(entry['labels'])}"})
            continue
        existing = current_content(hit)
        if existing:
            if norm(existing) == norm("".join(lines)):
                already.append({"group": "section", "key": key, "where": hit["where"]})
                continue
            if not overwrite:
                conflicts.append({"group": "section", "key": key, "where": hit["where"],
                                  "existing": existing[:80]})
                continue
        writes.append({"group": "section", "key": key, "hit": hit, "lines": lines,
                       "limit": entry.get("limit")})

    for entry in spec.get("fields", []):
        key = entry["key"]
        hit = locate(doc, entry["labels"], entry.get("scope"))
        if hit is None:
            missing.append({"group": "field", "key": key,
                            "reason": f"官方模板中找不到标签：{'、'.join(entry['labels'])}"})
            continue
        existing = current_content(hit)
        if existing:
            if norm(existing) == norm(entry["value"]):
                already.append({"group": "field", "key": key, "where": hit["where"]})
                continue
            if not overwrite:
                conflicts.append({"group": "field", "key": key, "where": hit["where"],
                                  "existing": existing[:80]})
                continue
        writes.append({"group": "field", "key": key, "hit": hit, "lines": [entry["value"]]})

    return writes, missing, conflicts, already


def over_limit(writes: list[dict]) -> list[dict]:
    out = []
    for write in writes:
        limit = write.get("limit")
        if limit is None:
            continue
        count = sum(1 for ch in "".join(write["lines"]) if not ch.isspace())
        if count > limit:
            out.append({"key": write["key"], "count": count, "limit": limit})
    return out


# ------------------------------------------------------------------------- plan (xlsx)


def _cell_text(value) -> str:
    return "" if value is None else str(value).strip()


def _summary_sheet(workbook):
    """The sheet that carries the 汇总表 header row (序号 + 项目名称 + 主持人)."""
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 20)):
            values = {norm(_cell_text(cell.value)) for cell in row if _cell_text(cell.value)}
            if "序号" in values and "项目名称" in values and "主持人" in values:
                return sheet, row[0].row
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 20)):
            values = {_cell_text(cell.value) for cell in row}
            if any("汇总表" in value for value in values):
                return sheet, row[0].row
    return None, None


def _header_columns(sheet, header_row: int) -> dict[str, int]:
    """normalized header text -> column index (1-based)."""
    columns: dict[str, int] = {}
    for cell in sheet[header_row]:
        text = norm(_cell_text(cell.value))
        if text:
            columns.setdefault(text, cell.column)
    return columns


def _column_for(columns: dict[str, int], labels: list[str]) -> int | None:
    for label in labels:
        wanted = norm(label)
        if wanted in columns:
            return columns[wanted]
        for text, column in columns.items():
            if text.startswith(wanted):
                return column
    return None


def plan_xlsx(sheet, header_row: int, spec: dict, overwrite: bool):
    columns = _header_columns(sheet, header_row)
    data_row = header_row + 1
    writes, missing, conflicts, already = [], [], [], []

    for entry in spec.get("fields", []):
        key = entry["key"]
        column = _column_for(columns, entry["labels"])
        if column is None:
            missing.append({"group": "field", "key": key,
                            "reason": f"汇总表表头中找不到列：{'、'.join(entry['labels'])}"})
            continue
        cell = sheet.cell(row=data_row, column=column)
        existing = _cell_text(cell.value)
        desired = entry["value"]
        # The template's own examples ("例：1981.01") are filler, not content.
        if existing.startswith("例："):
            existing = ""
        if existing:
            if norm(existing) == norm(desired):
                already.append({"group": "field", "key": key,
                                "where": f"{cell.coordinate}"})
                continue
            if not overwrite:
                conflicts.append({"group": "field", "key": key,
                                  "where": f"{cell.coordinate}", "existing": existing[:80]})
                continue
        writes.append({"group": "field", "key": key, "cell": cell,
                       "lines": [desired], "where": cell.coordinate})
    return writes, missing, conflicts, already, data_row


# ------------------------------------------------------------------------------ main


def load_field_map(path: Path | None) -> dict:
    if path is None:
        return DEFAULT_FIELD_MAP
    return json.loads(path.read_text(encoding="utf-8"))


def _open(path: Path, docx_module):
    return docx_module.Document(str(path))


def output_path(kind: str, input_path: Path, out_dir: Path) -> Path:
    if kind == "attachment2":
        return out_dir / OUT_ATTACHMENT2.name
    suffix = input_path.suffix.lower()
    name = (OUT_ATTACHMENT3_XLSX if suffix in XLSX_SUFFIXES else OUT_ATTACHMENT3_DOCX).name
    return out_dir / name


def process(attachment: str, input_path: Path, output_path: Path, spec: dict,
            texts: dict[str, list[str]], overwrite: bool, dry_run: bool,
            write_partial: bool, docx_module) -> dict:
    """Locate, report, and (only when complete, or --write-partial) write."""
    if not input_path.is_file():
        return {"attachment": attachment, "input": str(input_path), "status": "INPUT_MISSING"}

    doc = _open(input_path, docx_module)
    if NOT_OFFICIAL_BANNER in document_text(doc):
        return {"attachment": attachment, "input": str(input_path), "status": "NOT_OFFICIAL"}

    writes, missing, conflicts, already = plan(doc, spec, texts, overwrite)
    too_long = over_limit(writes)

    status = _status(too_long, conflicts, missing)
    result = _result(attachment, input_path, output_path, writes, missing, conflicts,
                     already, too_long, status)

    if dry_run or (status != "OK" and not write_partial):
        return result

    for write in writes:
        apply_write(write["hit"], write["lines"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    result["written"] = True
    return result


def process_xlsx(attachment: str, input_path: Path, output_path: Path, spec: dict,
                 overwrite: bool, dry_run: bool, write_partial: bool,
                 openpyxl_module) -> dict:
    """Same contract as `process`, for the Excel summary table."""
    if not input_path.is_file():
        return {"attachment": attachment, "input": str(input_path), "status": "INPUT_MISSING"}

    workbook = openpyxl_module.load_workbook(str(input_path))
    banner = any(NOT_OFFICIAL_BANNER in _cell_text(cell.value)
                 for sheet in workbook.worksheets for row in sheet.iter_rows() for cell in row)
    if banner:
        return {"attachment": attachment, "input": str(input_path), "status": "NOT_OFFICIAL"}

    sheet, header_row = _summary_sheet(workbook)
    if sheet is None:
        return {"attachment": attachment, "input": str(input_path),
                "status": "NOT_OFFICIAL",
                "reason": "找不到汇总表表头（序号/项目名称/主持人）"}

    assert header_row is not None
    writes, missing, conflicts, already, data_row = plan_xlsx(sheet, header_row, spec, overwrite)
    status = _status([], conflicts, missing)
    result = _result(attachment, input_path, output_path, writes, missing, conflicts,
                     already, [], status)
    result["sheet"] = sheet.title
    result["data_row"] = data_row

    if dry_run or (status != "OK" and not write_partial):
        return result

    for write in writes:
        write["cell"].value = write["lines"][0]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(str(output_path))
    result["written"] = True
    return result


def _status(too_long: list, conflicts: list, missing: list) -> str:
    if too_long:
        return "OVER_LIMIT"
    if conflicts:
        return "CONFLICT"
    if missing:
        return "FIELDS_MISSING"
    return "OK"


def _result(attachment, input_path, output_path, writes, missing, conflicts,
            already, too_long, status) -> dict:
    return {
        "attachment": attachment,
        "input": str(input_path),
        "output": str(output_path),
        "writes": [{"group": w["group"], "key": w["key"],
                    "where": w.get("where") or w["hit"]["where"],
                    "label": w.get("hit", {}).get("label", w["key"])} for w in writes],
        "missing": missing,
        "conflicts": conflicts,
        "already": already,
        "over_limit": too_long,
        "status": status,
        "written": False,
    }


def render(results: list[dict], write_partial: bool, notes: list[str] | None = None) -> str:
    out = ["官方模板填写（§7.3 / §7.5）", "=" * 78]
    if notes:
        out.append("输入解析：")
        out.extend(f"  - {note}" for note in notes)
        out.append("")
    for result in results:
        out.append(f"\n附件：{result['attachment']}")
        out.append(f"  输入：{result['input']}")
        status = result["status"]
        if status == "INPUT_MISSING":
            out.append("  FAIL 官方原件不存在 —— 拒绝运行，且不会生成任何替代模板")
            continue
        if status == "NOT_OFFICIAL":
            reason = result.get("reason", f"输入文件含「{NOT_OFFICIAL_BANNER}」横幅或不像该官方表单")
            out.append(f"  FAIL {reason}；不是官方模板，拒绝填写")
            continue
        out.append(f"  输出：{result['output']}")
        if result.get("sheet"):
            out.append(f"  工作表：{result['sheet']}（数据行 {result.get('data_row')}）")
        for write in result["writes"]:
            out.append(f"  PASS 已匹配 {write['group']}「{write['key']}」"
                       f" @ {write['where']}")
        for item in result.get("already", []):
            out.append(f"  PASS 已是目标值（未重写）{item['group']}「{item['key']}」"
                       f" @ {item['where']}")
        for item in result["missing"]:
            out.append(f"  FAIL 未找到 {item['group']}「{item['key']}」：{item['reason']}")
        for item in result["conflicts"]:
            out.append(f"  FAIL 目标已有内容（未覆盖）{item['group']}「{item['key']}」"
                       f" @ {item['where']}：{item['existing']}")
        for item in result["over_limit"]:
            out.append(f"  FAIL 超出上限：{item['key']} {item['count']} > {item['limit']}")
        if result.get("written"):
            out.append("  PASS 已写入输出文件")
        else:
            out.append("  SKIPPED 未写入输出文件" + ("" if write_partial else "（存在未完成项；"
                       "如需强制写出部分结果，请加 --write-partial）"))
    out.append("")
    out.append("提示：本脚本只把 E5_04 的六栏正文与已知字段写入**真实官方模板的副本**；"
               "标签取自 JSON 字段映射，官方原件栏目名不同时改 --field-map 即可。"
               "主持人、成员、单位、职称、出生年月、联系电话、签字与盖章一律写为【待填】，不虚构。")
    return "\n".join(out)


def _print_missing(searched: list[str], absent: list[str], notes: list[str] | None = None) -> None:
    print("错误：找不到官方原件，拒绝运行，也不会生成任何替代模板。", file=sys.stderr)
    print(f"  缺少：{'、'.join(absent)}", file=sys.stderr)
    if notes:
        # Whatever we did find (a ZIP whose members are .doc, say) is the most
        # useful thing to say: it tells the applicant exactly what to fix.
        print("  已找到的内容：", file=sys.stderr)
        for note in notes:
            print(f"    - {note}", file=sys.stderr)
    print("已查找的位置（任一处即可）：", file=sys.stderr)
    for location in searched:
        print(f"  - {location}", file=sys.stderr)
    print("也可以直接用参数指定：", file=sys.stderr)
    print("  --zip 官方原件ZIP            # 脚本自行解压其中的 申报书/汇总表（按名称与内容识别）", file=sys.stderr)
    print("  --official-dir 目录          # 已解压好的 申报书（.docx）与汇总表（.xlsx/.docx）所在目录", file=sys.stderr)
    print("  --attachment2 文件 --attachment3 文件", file=sys.stderr)
    print("说明见 docs/teaching_grant_2026/FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md",
          file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把 E5_04 六栏正文与已知字段填进官方 申报书/汇总表 的副本。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--attachment2", type=Path, default=None,
                        help="申报书原件（默认在官方目录中按名称与内容识别）")
    parser.add_argument("--attachment3", type=Path, default=None,
                        help="申报汇总表原件（.xlsx 或 .docx；按名称与内容识别）")
    parser.add_argument("--zip", type=Path, default=None,
                        help=f"官方原件 ZIP（默认查找 {' 与 '.join(str(p) for p in ZIP_CANDIDATES)}）")
    parser.add_argument("--official-dir", type=Path, default=OFFICIAL_DIR,
                        help=f"已解压的官方文件所在目录（默认 {OFFICIAL_DIR}）")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--six", type=Path, default=SIX, help="六栏正文来源（默认 E5_04）")
    parser.add_argument("--field-map", type=Path, default=None, help="覆盖默认字段映射的 JSON")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖目标中已有内容")
    parser.add_argument("--write-partial", action="store_true", help="存在缺失/冲突时仍写出已匹配部分")
    parser.add_argument("--dry-run", action="store_true", help="只定位与报告，不写文件")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.six.is_file():
        print(f"错误：找不到六栏正文 {args.six}", file=sys.stderr)
        return 1
    try:
        field_map = load_field_map(args.field_map)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"错误：字段映射无法读取：{exc}", file=sys.stderr)
        return 1

    with contextlib.ExitStack() as stack:
        inputs, notes, searched = resolve_inputs(args, stack)
        absent = [kind for kind in ("attachment2", "attachment3") if kind not in inputs]
        if absent:
            # Refuse before anything else: no official file means no output, and no
            # substitute template is ever generated (task brief §7.6).
            _print_missing(searched, absent, notes)
            return 2

        _require_docx()
        import docx as docx_module

        texts = section_texts(args.six)
        if not texts:
            print(f"错误：{args.six} 中解析不到任何栏目", file=sys.stderr)
            return 1

        results = []
        for attachment in ("attachment2", "attachment3"):
            input_path = inputs[attachment]
            output = output_path(attachment, input_path, args.out_dir)
            spec = field_map.get(attachment, {})
            if input_path.suffix.lower() in XLSX_SUFFIXES:
                _require_openpyxl()
                import openpyxl as openpyxl_module
                results.append(process_xlsx(attachment, input_path, output, spec,
                                            args.overwrite, args.dry_run,
                                            args.write_partial, openpyxl_module))
            else:
                results.append(process(attachment, input_path, output, spec, texts,
                                       args.overwrite, args.dry_run, args.write_partial,
                                       docx_module))

    if args.json:
        print(json.dumps({"results": results, "notes": notes}, ensure_ascii=False, indent=2))
    else:
        print(render(results, args.write_partial, notes))

    statuses = {r["status"] for r in results}
    if "INPUT_MISSING" in statuses:
        return 2
    if "NOT_OFFICIAL" in statuses:
        return 6
    if "OVER_LIMIT" in statuses:
        return 4
    if "CONFLICT" in statuses:
        return 7
    if "FIELDS_MISSING" in statuses:
        return 3
    if not args.json:
        print("结论：PASS，官方模板副本已填写完成（真人信息仍为【待填】）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
