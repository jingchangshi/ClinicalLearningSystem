#!/usr/bin/env python3.11
"""Fill the official 附件2 / 附件3 DOCX from the six-section source text.

This is the §7.3 / §7.5 pipeline. It is **label-driven**: the official templates
are not on this machine (see
``docs/teaching_grant_2026/FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md``), so
the script locates each field by the label the official form uses -- ``项目研究基础``,
``项目名称``, ... -- in a table cell or in a paragraph, and writes the value next to
it. Labels and values live in an editable JSON field map so the operator can
correct a label without touching code once the real template is in hand.

Hard rules this script enforces, because a silently half-filled official form is
worse than no form at all:

* **Refuses to run without the official input files** (exit 2).
* **Never fabricates a template.** It only ever writes into a copy of a real
  official file, and it refuses (exit 6) to treat one of our own generated drafts
  as official -- detected by this repository's own "非官方模板" banner.
* **Reports every expected field it cannot locate** (exit 3) instead of skipping
  it. Nothing is written unless ``--write-partial`` is passed.
* **Refuses to overwrite** a target that already carries content unless
  ``--overwrite`` is passed; a conflict is reported, not silently replaced.
* **Enforces the official character limits** per section (exit 4).

Outputs (private, gitignored)::

    docs/teaching_grant_2026/APPLICATION_PACKAGE/official_out/
        浙江省2026年教改项目申报书_官方模板填写版.docx
        浙江省2026年教改项目申报汇总表_官方模板填写版.docx

Usage::

    python3.11 scripts/grant/fill_official_forms.py --dry-run
    python3.11 scripts/grant/fill_official_forms.py --json
    python3.11 scripts/grant/fill_official_forms.py --field-map my_map.json

Exit codes: 0 filled, 1 usage error, 2 official input missing, 3 a field label was
not found, 4 a section exceeds its limit, 5 python-docx unavailable, 6 the input is
not an official template, 7 a target already has content (conflict).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
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

DEFAULT_ATTACHMENT2 = OFFICIAL_DIR / "附件2_教学改革项目申报书.docx"
DEFAULT_ATTACHMENT3 = OFFICIAL_DIR / "附件3_申报汇总表.docx"
OUT_ATTACHMENT2 = OUT_DIR / "浙江省2026年教改项目申报书_官方模板填写版.docx"
OUT_ATTACHMENT3 = OUT_DIR / "浙江省2026年教改项目申报汇总表_官方模板填写版.docx"

# Our own generated drafts carry this banner; seeing it means the file is not the
# official template and must never be filled as if it were.
NOT_OFFICIAL_BANNER = "非官方模板"

TITLE = "基于人工智能辅助临床推理训练的医学生个性化学习与形成性评价教学改革研究"

# Field map. `labels` are matched against the official form's own wording, so a
# template that writes 课题名称 instead of 项目名称 only needs a label added here.
DEFAULT_FIELD_MAP: dict = {
    "attachment2": {
        "sections": [
            {"key": name, "limit": limit, "labels": [name, name[2:] if name.startswith("项目") else name]}
            for name, limit in apptext.SECTIONS
        ],
        "fields": [
            {"key": "项目名称", "value": TITLE, "labels": ["项目名称", "课题名称", "项目全称"]},
            {"key": "项目类别", "value": "【待填：一般项目；选题方向对照附件 1 选题指南填写，原件未到本机】",
             "labels": ["项目类别", "项目类别及选题方向", "选题方向"]},
            {"key": "项目周期", "value": "【待填：以官方通知规定的项目周期为准】",
             "labels": ["项目周期", "研究周期", "完成时间"]},
            {"key": "申报单位", "value": "【待填：学校/学院全称】",
             "labels": ["申报单位", "申请单位", "所在单位", "承担单位"]},
            {"key": "主持人", "value": "【待填：姓名】", "labels": ["主持人", "项目负责人", "负责人姓名"]},
            {"key": "联系方式", "value": "【待填：电话与电子邮箱】",
             "labels": ["联系方式", "联系电话", "电话及邮箱"]},
            {"key": "申请经费", "value": "【待填：金额，依单位与官方规定】",
             "labels": ["申请经费", "经费预算", "申请金额"]},
        ],
    },
    "attachment3": {
        "sections": [],
        "fields": [
            {"key": "项目名称", "value": TITLE, "labels": ["项目名称", "课题名称"]},
            {"key": "项目主持人", "value": "【待填：姓名】", "labels": ["项目主持人", "主持人", "负责人"]},
            {"key": "所在单位", "value": "【待填：学校/学院全称】", "labels": ["所在单位", "申报单位", "承担单位"]},
            {"key": "联系电话", "value": "【待填：电话与电子邮箱】", "labels": ["联系电话", "联系方式"]},
            {"key": "项目类别", "value": "【待填：一般项目；选题方向与方向编号须抄录附件 1】",
             "labels": ["项目类别", "选题方向", "类别及方向"]},
            {"key": "项目周期", "value": "【待填：以官方通知为准】", "labels": ["项目周期", "研究周期"]},
            {"key": "申请经费", "value": "【待填：金额】", "labels": ["申请经费", "申请金额", "经费"]},
            {"key": "团队人数", "value": "【待填：人数与成员，见 APPLICATION_PACKAGE/20_team_roles.md】",
             "labels": ["团队人数", "项目组成员", "参加人员", "成员"]},
            {"key": "学校推荐意见", "value": "【待填：由单位填写并签章】",
             "labels": ["学校推荐意见", "推荐意见", "单位意见"]},
        ],
    },
}

# Trailing filler an empty official field is made of, e.g. "项目名称：______".
FILLER_RE = re.compile(r"[\s　_＿—－\-－…·.、：:]*$")


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


# ---------------------------------------------------------------------- docx access


def _require_docx():
    try:
        import docx  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover - depends on the environment
        print("错误：未安装 python-docx。请用 "
              "`uv run --python 3.11 --with python-docx python scripts/grant/fill_official_forms.py` 运行。",
              file=sys.stderr)
        raise SystemExit(5)


def iter_tables(doc):
    """Every table, including tables nested inside cells, in document order."""
    seen = []

    def walk(tables):
        for table in tables:
            seen.append(table)
            for row in table.rows:
                for cell in row.cells:
                    walk(cell.tables)

    walk(doc.tables)
    return seen


def iter_paragraphs(doc):
    """Every paragraph, including those inside table cells, in document order."""
    for paragraph in doc.paragraphs:
        yield paragraph
    for table in iter_tables(doc):
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    yield paragraph


def document_text(doc) -> str:
    parts = [p.text for p in iter_paragraphs(doc)]
    return "\n".join(parts)


# ------------------------------------------------------------------- field locating


def locate_in_tables(doc, labels: list[str]):
    """First cell matching a label, with the cell that should hold the value.

    Value target = the next cell in the same row; if the label cell is last in its
    row, the cell directly below it (the official forms use both layouts).
    """
    wanted = [(label, norm(label)) for label in labels]
    candidates = []
    for table in iter_tables(doc):
        for row_index, row in enumerate(table.rows):
            cells = row.cells
            for col_index, cell in enumerate(cells):
                text = norm(cell.text)
                if not text:
                    continue
                for label, target in wanted:
                    if text == target:
                        candidates.append((0, len(text), label, table, row_index, col_index))
                    elif target in text and len(text) <= len(target) + 12:
                        candidates.append((1, len(text), label, table, row_index, col_index))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    _rank, _length, label, table, row_index, col_index = candidates[0]
    row = table.rows[row_index]
    if col_index + 1 < len(row.cells):
        target = row.cells[col_index + 1]
        where = f"表{_table_index(doc, table)}第{row_index + 1}行第{col_index + 2}列"
    elif row_index + 1 < len(table.rows):
        target = table.rows[row_index + 1].cells[col_index]
        where = f"表{_table_index(doc, table)}第{row_index + 2}行第{col_index + 1}列"
    else:
        return None
    return {"kind": "table-cell", "label": label, "target": target, "where": where,
            "table_index": _table_index(doc, table), "row": row_index, "col": col_index}


def _table_index(doc, table) -> int:
    # python-docx builds a fresh proxy each time `doc.tables` is read, so compare
    # the underlying XML elements rather than the wrappers.
    for index, candidate in enumerate(iter_tables(doc), start=1):
        if candidate._tbl is table._tbl:
            return index
    return 0


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
            elif target in text and len(text) <= len(target) + 12:
                candidates.append((1, len(text), index, label, paragraph))
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


def locate(doc, labels: list[str]):
    """Tables first -- official application forms put their fields in tables."""
    return locate_in_tables(doc, labels) or locate_in_paragraphs(doc, labels)


# --------------------------------------------------------------------------- filling


def _write_cell(cell, lines: list[str]) -> None:
    cell.text = ""
    first = cell.paragraphs[0]
    for offset, line in enumerate(lines):
        paragraph = first if offset == 0 else cell.add_paragraph()
        paragraph.add_run(line)


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
    for line in lines[1:]:
        run.add_break()
        run.add_text(line)


def _write_paragraph(paragraph, lines: list[str]) -> None:
    for run in list(paragraph.runs):
        run._element.getparent().remove(run._element)
    paragraph.add_run(lines[0])
    for line in lines[1:]:
        paragraph.add_run().add_break()
        paragraph.add_run(line)


def apply_write(hit: dict, lines: list[str]) -> None:
    if hit["kind"] == "table-cell":
        _write_cell(hit["target"], lines)
    elif hit["kind"] == "paragraph-next":
        _write_paragraph(hit["target"], lines)
    else:
        _append_to_paragraph(hit["target"], lines)


def current_content(hit: dict) -> str:
    return hit["target"].text.strip()


# ------------------------------------------------------------------------------ plan


def plan(doc, spec: dict, texts: dict[str, list[str]], overwrite: bool) -> tuple[list[dict], list[dict], list[dict]]:
    """Return (writes, missing, conflicts) for the sections then the fields."""
    writes: list[dict] = []
    missing: list[dict] = []
    conflicts: list[dict] = []

    for entry in spec.get("sections", []):
        key = entry["key"]
        lines = texts.get(key)
        if not lines:
            missing.append({"group": "section", "key": key, "reason": "E5_04 中找不到该栏正文"})
            continue
        hit = locate(doc, entry["labels"])
        if hit is None:
            missing.append({"group": "section", "key": key,
                            "reason": f"官方模板中找不到标签：{'、'.join(entry['labels'])}"})
            continue
        existing = current_content(hit)
        if existing and not overwrite and norm(existing) not in {norm(key)}:
            conflicts.append({"group": "section", "key": key, "where": hit["where"],
                              "existing": existing[:80]})
            continue
        writes.append({"group": "section", "key": key, "hit": hit, "lines": lines,
                       "limit": entry.get("limit")})

    for entry in spec.get("fields", []):
        key = entry["key"]
        hit = locate(doc, entry["labels"])
        if hit is None:
            missing.append({"group": "field", "key": key,
                            "reason": f"官方模板中找不到标签：{'、'.join(entry['labels'])}"})
            continue
        existing = current_content(hit)
        if existing and not overwrite:
            conflicts.append({"group": "field", "key": key, "where": hit["where"],
                              "existing": existing[:80]})
            continue
        writes.append({"group": "field", "key": key, "hit": hit, "lines": [entry["value"]]})

    return writes, missing, conflicts


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


# ------------------------------------------------------------------------------ main


def load_field_map(path: Path | None) -> dict:
    if path is None:
        return DEFAULT_FIELD_MAP
    return json.loads(path.read_text(encoding="utf-8"))


def _open(path: Path, docx_module):
    return docx_module.Document(str(path))


def process(attachment: str, input_path: Path, output_path: Path, spec: dict,
            texts: dict[str, list[str]], overwrite: bool, dry_run: bool,
            write_partial: bool, docx_module) -> dict:
    """Locate, report, and (only when complete, or --write-partial) write."""
    if not input_path.is_file():
        return {"attachment": attachment, "input": str(input_path), "status": "INPUT_MISSING"}

    doc = _open(input_path, docx_module)
    if NOT_OFFICIAL_BANNER in document_text(doc):
        return {"attachment": attachment, "input": str(input_path), "status": "NOT_OFFICIAL"}

    writes, missing, conflicts = plan(doc, spec, texts, overwrite)
    too_long = over_limit(writes)

    if too_long:
        status = "OVER_LIMIT"
    elif conflicts:
        status = "CONFLICT"
    elif missing:
        status = "FIELDS_MISSING"
    else:
        status = "OK"

    result = {
        "attachment": attachment,
        "input": str(input_path),
        "output": str(output_path),
        "writes": [{"group": w["group"], "key": w["key"], "where": w["hit"]["where"],
                    "label": w["hit"]["label"]} for w in writes],
        "missing": missing,
        "conflicts": conflicts,
        "over_limit": too_long,
        "status": status,
        "written": False,
    }

    if dry_run or (status != "OK" and not write_partial):
        return result

    for write in writes:
        apply_write(write["hit"], write["lines"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    result["written"] = True
    return result


def render(results: list[dict], write_partial: bool) -> str:
    out = ["官方模板填写（§7.3 / §7.5）", "=" * 78]
    for result in results:
        out.append(f"\n附件：{result['attachment']}")
        out.append(f"  输入：{result['input']}")
        status = result["status"]
        if status == "INPUT_MISSING":
            out.append("  FAIL 官方原件不存在 —— 拒绝运行，且不会生成任何替代模板")
            continue
        if status == "NOT_OFFICIAL":
            out.append(f"  FAIL 输入文件含「{NOT_OFFICIAL_BANNER}」横幅，是本仓库自绘草稿，"
                       "不是官方模板，拒绝填写")
            continue
        out.append(f"  输出：{result['output']}")
        for write in result["writes"]:
            out.append(f"  PASS 已匹配 {write['group']}「{write['key']}」← 标签「{write['label']}」"
                       f" @ {write['where']}")
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
               "标签取自 JSON 字段映射，官方原件到手后如栏目名不同，改 --field-map 即可。")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把 E5_04 六栏正文与已知字段填进官方附件 2/附件 3 的副本。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--attachment2", type=Path, default=DEFAULT_ATTACHMENT2)
    parser.add_argument("--attachment3", type=Path, default=DEFAULT_ATTACHMENT3)
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

    inputs = {"attachment2": args.attachment2, "attachment3": args.attachment3}
    absent = [(name, path) for name, path in inputs.items() if not path.is_file()]
    if absent:
        # Refuse before anything else: no official file means no output, and no
        # substitute template is ever generated (task brief §7.6).
        print("错误：找不到官方原件，拒绝运行，也不会生成任何替代模板。", file=sys.stderr)
        for name, path in absent:
            print(f"  缺少 {name}：{path}", file=sys.stderr)
        print("请把申请人提供的官方原件放到（不入库）：", file=sys.stderr)
        print(f"  {OFFICIAL_DIR}/附件2_教学改革项目申报书.docx", file=sys.stderr)
        print(f"  {OFFICIAL_DIR}/附件3_申报汇总表.docx", file=sys.stderr)
        print("说明见 docs/teaching_grant_2026/FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md",
              file=sys.stderr)
        return 2

    _require_docx()
    import docx as docx_module

    texts = section_texts(args.six)
    if not texts:
        print(f"错误：{args.six} 中解析不到任何栏目", file=sys.stderr)
        return 1

    outputs = {
        "attachment2": args.out_dir / OUT_ATTACHMENT2.name,
        "attachment3": args.out_dir / OUT_ATTACHMENT3.name,
    }

    results = []
    for attachment in ("attachment2", "attachment3"):
        results.append(process(attachment, inputs[attachment], outputs[attachment],
                               field_map.get(attachment, {}), texts, args.overwrite,
                               args.dry_run, args.write_partial, docx_module))

    if args.json:
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    else:
        print(render(results, args.write_partial))

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
        print("结论：PASS，两个官方模板副本均已填写完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
