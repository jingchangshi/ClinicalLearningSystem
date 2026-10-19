#!/usr/bin/env python3.11
"""Run §7.6's checks on a produced official-form DOCX, or on the Excel summary table.

Every check reports ``PASS`` / ``FAIL`` / ``SKIPPED`` with a reason, and a check
that cannot run on this machine says so -- it is never reported as passing.

A ``.xlsx`` argument switches to the summary-table checks (reopen, header row,
per-field read-back, template examples replaced, placeholders); the Word-only
checks are then reported as SKIPPED with that reason.

**Implemented for real with python-docx** (1.2.0 via ``uv --with python-docx``):

1. **文件与重新打开** -- valid zip with the required parts, and python-docx can
   open it and read content back.
2. **字数核验** -- per-section non-whitespace character count read from the filled
   section target, against the official limit and against E5_04's own count.
3. **页边距** -- every section's top/bottom/left/right margin is read and must be
   explicitly set and positive; with ``--template`` they are compared section by
   section against the official original.
4. **表格完整性** -- every table is enumerated; each row's effective cell count
   (``gridSpan`` aware) must equal the table grid's column count.
5. **跨页（结构层面）** -- explicitly inserted page breaks inside tables, and
   whether multi-row tables set ``w:cantSplit``.
6. **中文字体与字号** -- every run carrying CJK text must resolve an explicit
   East-Asian font and size (run -> paragraph style -> character style); the
   distinct font/size pairs are reported.
7. **提交就绪** -- no ``【待填`` placeholder remains. Expected to FAIL until real
   people supply the missing facts; it gates submission, not this pipeline.

**Cannot run on this machine, reported as SKIPPED with the reason and the exact
command a human should run:**

* **PDF/图片渲染目视检查** -- ``libreoffice``, ``soffice``, ``pandoc``,
  ``pdftoppm`` and ``pdftotext`` are all absent here. Actual pagination, where a
  table breaks across pages, and how the Chinese fonts really render can only be
  judged on a rendered page, so this stays SKIPPED and a human must run::

      libreoffice --headless --convert-to pdf --outdir . OUT.docx

  and inspect the resulting PDF page by page.

Usage::

    python3.11 scripts/grant/validate_official_docx.py OUT.docx
    python3.11 scripts/grant/validate_official_docx.py OUT.docx --template official.docx --json

Exit codes: 0 no FAIL, 1 at least one FAIL, 2 the file is missing, 5 python-docx
unavailable. A SKIPPED check never by itself makes the exit code non-zero, but it
is listed separately in the report and never counted as a pass.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fill_official_forms as fill  # noqa: E402  (one label-matching implementation)

CJK_RE = re.compile(r"[　-〿一-鿿＀-￯]")
PLACEHOLDER = "【待填"

RENDERERS = ("soffice", "libreoffice", "pandoc")

# Wording is fixed so the report cannot drift into implying the check ran.
NO_RENDERER_REASON = ("no libreoffice/pandoc on this machine; requires a human render check")


def render_command(path: Path) -> str:
    """The exact command a human runs on a machine that has a renderer."""
    return f'libreoffice --headless --convert-to pdf --outdir . "{path}"'


def _require_docx():
    try:
        import docx  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover - depends on the environment
        print("错误：未安装 python-docx。请用 "
              "`uv run --python 3.11 --with python-docx python scripts/grant/validate_official_docx.py` 运行。",
              file=sys.stderr)
        raise SystemExit(5)


def check(name: str, status: str, detail: str = "", **extra) -> dict:
    assert status in {"PASS", "FAIL", "SKIPPED"}
    return {"name": name, "status": status, "detail": detail, **extra}


# ---------------------------------------------------------------- 1. open / reopen


def check_reopen(path: Path, docx_module) -> tuple[dict, object | None]:
    required = {"[Content_Types].xml", "word/document.xml"}
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, OSError) as exc:
        return check("文件与重新打开", "FAIL", f"不是合法 DOCX zip：{exc}"), None
    missing = sorted(required - names)
    if missing:
        return check("文件与重新打开", "FAIL", f"缺少必需部件：{'、'.join(missing)}"), None
    try:
        document = docx_module.Document(str(path))
    except Exception as exc:  # noqa: BLE001 - any failure here is the finding
        return check("文件与重新打开", "FAIL", f"python-docx 打开失败：{exc}"), None
    paragraphs = sum(1 for _ in fill.iter_paragraphs(document))
    if paragraphs == 0:
        return check("文件与重新打开", "FAIL", "重新打开后 0 个段落"), document
    return check("文件与重新打开", "PASS",
                 f"zip 部件齐全；重新打开后 {paragraphs} 个段落（含表格单元格）"), document


# ------------------------------------------------------------------ 2. character counts


def section_entry(name: str) -> dict:
    """The field-map entry for a section, so the validator reads the same target
    the filler wrote to (one locating implementation, not two)."""
    for entry in fill.DEFAULT_FIELD_MAP["attachment2"]["sections"]:
        if entry["key"] == name:
            return entry
    return {"key": name, "block": True,
            "labels": [name, name[2:] if name.startswith("项目") else name]}


def section_counts(document, texts: dict[str, list[str]]) -> dict:
    rows = []
    for name, limit in fill.apptext.SECTIONS:
        hit = fill.find_section_hit(document, section_entry(name))
        source_count = sum(1 for ch in "".join(texts.get(name, [])) if not ch.isspace())
        if hit is None:
            rows.append({"section": name, "filled": None, "source": source_count,
                         "limit": limit, "status": "FAIL", "detail": "官方模板中找不到该栏目标签"})
            continue
        body = fill.hit_body_text(hit)
        count = sum(1 for ch in body if not ch.isspace())
        problems = []
        if count > limit:
            problems.append(f"超出上限 {count - limit} 字")
        if source_count and count != source_count:
            problems.append(f"与 E5_04 计数 {source_count} 不一致（转录可能丢失或重复）")
        rows.append({"section": name, "filled": count, "source": source_count, "limit": limit,
                     "status": "FAIL" if problems else "PASS", "detail": "；".join(problems),
                     "where": hit["where"]})
    failed = [row for row in rows if row["status"] == "FAIL"]
    detail = "；".join(f"{row['section']} {row['filled']}/{row['limit']}" for row in rows
                      if row["filled"] is not None)
    overall = check("字数核验", "FAIL" if failed else "PASS",
                    "；".join(f"{row['section']}：{row['detail']}" for row in failed) or detail)
    return {"check": overall, "rows": rows}


# ---------------------------------------------------------------------------- 3. margins


def _mm(emu) -> str:
    if emu is None:
        return "未设置"
    return f"{emu / 360000:.1f}mm"


def _measured(document) -> str:
    return "；".join(
        f"第{i}节 上{_mm(s.top_margin)} 下{_mm(s.bottom_margin)} "
        f"左{_mm(s.left_margin)} 右{_mm(s.right_margin)}"
        for i, s in enumerate(document.sections, start=1)
    )


def check_margin_values(document) -> dict:
    """Margins must be explicitly set and positive (does not need the template)."""
    sections = list(document.sections)
    if not sections:
        return check("页边距", "FAIL", "文档没有任何 section")
    problems = []
    for index, section in enumerate(sections, start=1):
        values = {"上": section.top_margin, "下": section.bottom_margin,
                  "左": section.left_margin, "右": section.right_margin}
        absent = [name for name, value in values.items() if value is None]
        nonpositive = [name for name, value in values.items() if value is not None and value <= 0]
        if absent:
            problems.append(f"第{index}节 {','.join(absent)}边距未设置")
        if nonpositive:
            problems.append(f"第{index}节 {','.join(nonpositive)}边距非正")
    if problems:
        return check("页边距", "FAIL", "；".join(problems), measured=_measured(document))
    return check("页边距", "PASS", "各节上下左右边距均已设置且为正", measured=_measured(document))


def check_margins_match(document, template) -> dict:
    """Requires the official template -- only then can "一致" be claimed."""
    differences = []
    sections = list(document.sections)
    source = list(template.sections)
    for index, (mine, theirs) in enumerate(zip(sections, source), start=1):
        for label, a, b in (("上", mine.top_margin, theirs.top_margin),
                            ("下", mine.bottom_margin, theirs.bottom_margin),
                            ("左", mine.left_margin, theirs.left_margin),
                            ("右", mine.right_margin, theirs.right_margin)):
            if a != b:
                differences.append(f"第{index}节{label}边距 {_mm(a)} ≠ 模板 {_mm(b)}")
    if len(sections) != len(source):
        differences.append(f"节数 {len(sections)} ≠ 模板 {len(source)}")
    if differences:
        return check("页边距与官方模板一致", "FAIL", "；".join(differences))
    return check("页边距与官方模板一致", "PASS", f"{len(sections)} 节边距与模板一致")


# --------------------------------------------------------------------- 4. table integrity


def _effective_cells(row) -> int:
    from docx.oxml.ns import qn
    total = 0
    for cell in row._tr.findall(qn("w:tc")):
        span = cell.find(f'{qn("w:tcPr")}/{qn("w:gridSpan")}')
        total += int(span.get(f'{qn("w:val")}')) if span is not None else 1
    return total


def check_tables(document) -> dict:
    from docx.oxml.ns import qn
    tables = list(fill.iter_tables(document))
    if not tables:
        return check("表格完整性", "SKIPPED", "文档中没有表格")
    problems = []
    for index, table in enumerate(tables, start=1):
        grid = table._tbl.find(qn("w:tblGrid"))
        columns = len(grid.findall(qn("w:gridCol"))) if grid is not None else None
        if not table.rows:
            problems.append(f"表{index} 没有任何行")
            continue
        widths = {_effective_cells(row) for row in table.rows}
        if columns is not None and widths != {columns}:
            problems.append(f"表{index} 各行有效单元格数 {sorted(widths)} 与网格列数 {columns} 不一致")
    detail = f"{len(tables)} 个表格，行数 " + "、".join(
        f"表{i}:{len(t.rows)}" for i, t in enumerate(tables, start=1))
    if problems:
        return check("表格完整性", "FAIL", "；".join(problems))
    return check("表格完整性", "PASS", detail)


# ------------------------------------------------------------------------ 5. page breaks


def _unprotected_rows(document) -> set[tuple[int, int]]:
    from docx.oxml.ns import qn

    unprotected: set[tuple[int, int]] = set()
    for table_index, table in enumerate(fill.iter_tables(document), start=1):
        if len(table.rows) < 2:
            continue
        for row_index, row in enumerate(table.rows, start=1):
            properties = row._tr.find(qn("w:trPr"))
            if properties is None or properties.find(qn("w:cantSplit")) is None:
                unprotected.add((table_index, row_index))
    return unprotected


def check_cross_page(document, path: Path, template=None) -> list[dict]:
    from docx.oxml.ns import qn
    results: list[dict] = []

    inside_tables = 0
    for table in fill.iter_tables(document):
        for br in table._tbl.iter(qn("w:br")):
            if br.get(f'{qn("w:type")}') == "page":
                inside_tables += 1
    if inside_tables:
        results.append(check("跨页：表格内不得有显式分页符", "FAIL",
                             f"表格内发现 {inside_tables} 个显式分页符"))
    else:
        results.append(check("跨页：表格内不得有显式分页符", "PASS", "表格内无显式分页符"))

    unprotected = []
    for index, table in enumerate(fill.iter_tables(document), start=1):
        if len(table.rows) < 2:
            continue
        unprotected_rows = []
        for row_index, row in enumerate(table.rows, start=1):
            properties = row._tr.find(qn("w:trPr"))
            if properties is None or properties.find(qn("w:cantSplit")) is None:
                unprotected_rows.append(row_index)
        if unprotected_rows:
            unprotected.append(f"表{index} 第{unprotected_rows[:5]}行")
    if unprotected:
        detail = "以下行未设置 w:cantSplit，可能跨页拆分：" + "；".join(unprotected)
        # A FAIL that already exists in the official original is a property of the
        # form, not damage introduced by filling; say so without softening the FAIL.
        if template is not None and _unprotected_rows(document) == _unprotected_rows(template):
            detail += "（官方原件同样未设置，本填写未改变——版式以原件为准，不改动）"
        results.append(check("跨页：多行表格设置行内不拆分", "FAIL", detail))
    else:
        results.append(check("跨页：多行表格设置行内不拆分", "PASS", "多行表格均设置 w:cantSplit"))

    renderer = next((name for name in RENDERERS if shutil.which(name)), None)
    if renderer is None:
        results.append(check("跨页：PDF 渲染目视检查", "SKIPPED", NO_RENDERER_REASON,
                             human_command=render_command(path)))
        return results

    with tempfile.TemporaryDirectory() as directory:
        try:
            command = {
                "soffice": ["soffice", "--headless", "--convert-to", "pdf", "--outdir", directory, str(path)],
                "libreoffice": ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", directory, str(path)],
                "pandoc": ["pandoc", str(path), "-o", str(Path(directory) / (path.stem + ".pdf"))],
            }[renderer]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
            produced = list(Path(directory).glob("*.pdf"))
            if completed.returncode != 0 or not produced:
                results.append(check("跨页：PDF 渲染目视检查", "FAIL",
                                     f"{renderer} 渲染失败：{(completed.stderr or '').strip()[:200]}"))
            else:
                size = produced[0].stat().st_size
                results.append(check("跨页：PDF 渲染目视检查", "PASS",
                                     f"{renderer} 已渲染 {produced[0].name}（{size} 字节）；"
                                     "版式仍需人工目视确认"))
        except (OSError, KeyError) as exc:
            results.append(check("跨页：PDF 渲染目视检查", "FAIL", f"渲染器调用失败：{exc}"))
    return results


# ---------------------------------------------------------------- 6. Chinese font / size


def _style_chain(run, paragraph):
    """Run style, then paragraph style, then their bases -- what Word resolves."""
    chain = []
    for start in (run.style, paragraph.style):
        style = start
        while style is not None:
            chain.append(style)
            style = style.base_style
    return chain


def _explicit_east_asian(rpr) -> str | None:
    """The explicit w:eastAsia font on an rPr element.

    A theme reference (``w:eastAsiaTheme``) is not an explicit font: it resolves
    differently on every machine, so it does not count. Neither does its absence.
    """
    from docx.oxml.ns import qn

    if rpr is None:
        return None
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        return None
    return fonts.get(qn("w:eastAsia")) or None


def _doc_default_rpr(document):
    from docx.oxml.ns import qn

    defaults = document.styles.element.find(qn("w:docDefaults"))
    if defaults is None:
        return None
    rpr_default = defaults.find(qn("w:rPrDefault"))
    return rpr_default.find(qn("w:rPr")) if rpr_default is not None else None


def _east_asian_font(run, paragraph, defaults=None) -> str | None:
    """Resolve the East-Asian font the way Word does.

    Order: the run's direct formatting -> the paragraph mark -> the run/paragraph
    style chain -> the document defaults. Ignoring direct formatting (as this
    check originally did) reports every run of a real official form as unfonted,
    because these templates format through ``w:rPr`` on the run, not through styles.
    """
    from docx.oxml.ns import qn

    value = _explicit_east_asian(run._element.rPr)
    if value:
        return value
    p_pr = paragraph._p.pPr
    if p_pr is not None:
        value = _explicit_east_asian(p_pr.find(qn("w:rPr")))
        if value:
            return value
    for style in _style_chain(run, paragraph):
        value = _explicit_east_asian(style.element.rPr)
        if value:
            return value
    return _explicit_east_asian(defaults)


def _size(run, paragraph, defaults=None):
    from docx.oxml.ns import qn
    from docx.shared import Pt

    if run.font.size is not None:
        return run.font.size
    p_pr = paragraph._p.pPr
    if p_pr is not None:
        mark = p_pr.find(qn("w:rPr"))
        size = mark.find(qn("w:sz")) if mark is not None else None
        if size is not None and size.get(qn("w:val")):
            return Pt(int(size.get(qn("w:val"))) / 2)
    for style in _style_chain(run, paragraph):
        if style.font.size is not None:
            return style.font.size
    if defaults is not None:
        size = defaults.find(qn("w:sz"))
        if size is not None and size.get(qn("w:val")):
            return Pt(int(size.get(qn("w:val"))) / 2)
    return None


def check_cjk_fonts(document) -> dict:
    missing_font = []
    missing_size = []
    pairs: dict[tuple[str, str], int] = {}
    cjk_runs = 0
    defaults = _doc_default_rpr(document)
    for paragraph_index, paragraph in enumerate(fill.iter_paragraphs(document), start=1):
        for run in paragraph.runs:
            if not run.text or not CJK_RE.search(run.text):
                continue
            cjk_runs += 1
            font = _east_asian_font(run, paragraph, defaults)
            size = _size(run, paragraph, defaults)
            if not font:
                missing_font.append((paragraph_index, run.text[:20]))
            if size is None:
                missing_size.append((paragraph_index, run.text[:20]))
            key = (font or "（未设置）", f"{size.pt:g}pt" if size is not None else "（未设置）")
            pairs[key] = pairs.get(key, 0) + 1
    if cjk_runs == 0:
        return check("中文字体与字号", "SKIPPED", "文档中没有中文文本")
    problems = []
    if missing_font:
        problems.append(f"{len(missing_font)} 个中文 run 未设置东亚字体（可能渲染为方框），"
                        f"例：段落{missing_font[0][0]}『{missing_font[0][1]}』")
    if missing_size:
        problems.append(f"{len(missing_size)} 个中文 run 未设置字号，"
                        f"例：段落{missing_size[0][0]}『{missing_size[0][1]}』")
    summary = "；".join(f"{font} {size} × {count}" for (font, size), count in sorted(
        pairs.items(), key=lambda item: -item[1])[:8])
    if problems:
        return check("中文字体与字号", "FAIL", "；".join(problems), pairs=summary, cjk_runs=cjk_runs)
    return check("中文字体与字号", "PASS",
                 f"{cjk_runs} 个中文 run 均有显式东亚字体与字号", pairs=summary, cjk_runs=cjk_runs)


# ----------------------------------------------------------------------- 7. placeholders


def check_placeholders(document) -> dict:
    occurrences = []
    for paragraph_index, paragraph in enumerate(fill.iter_paragraphs(document), start=1):
        if PLACEHOLDER in paragraph.text:
            occurrences.append(f"段落{paragraph_index}")
    if occurrences:
        return check("提交就绪：无【待填】占位符", "FAIL",
                     f"仍有 {len(occurrences)} 处【待填（真实人员填毕后此检查才会通过）："
                     + "、".join(occurrences[:10]),
                     count=len(occurrences))
    return check("提交就绪：无【待填】占位符", "PASS", "全文无【待填】")


# ------------------------------------------------------------- 8. Excel summary table


def _require_openpyxl():
    try:
        import openpyxl  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover - depends on the environment
        print("错误：未安装 openpyxl。请用 "
              "`uv run --python 3.11 --with openpyxl python scripts/grant/validate_official_docx.py` 运行。",
              file=sys.stderr)
        raise SystemExit(5)


def validate_summary(path: Path, openpyxl_module, spec: dict | None = None) -> dict:
    """§7.6 checks for the Excel summary table.

    The Word-only checks (margins, page breaks, CJK fonts) do not apply to a
    spreadsheet and are reported as SKIPPED with that reason -- never as a pass.
    """
    spec = spec or fill.DEFAULT_FIELD_MAP["attachment3"]
    try:
        workbook = openpyxl_module.load_workbook(str(path))
    except Exception as exc:  # noqa: BLE001 - any failure here is the finding
        return {"document": str(path), "checks": [
            check("文件与重新打开（Excel）", "FAIL", f"openpyxl 打开失败：{exc}")], "ok": False}

    results = [check("文件与重新打开（Excel）", "PASS",
                     f"{len(workbook.worksheets)} 个工作表：{'、'.join(workbook.sheetnames)}")]

    sheet, header_row = fill._summary_sheet(workbook)
    if sheet is None or header_row is None:
        results.append(check("汇总表表头识别", "FAIL",
                             "找不到含 序号/项目名称/主持人 的表头行"))
        results.append(check("数据行字段读回", "SKIPPED", "未识别到表头，无法定位数据行"))
    else:
        results.append(check("汇总表表头识别", "PASS",
                             f"工作表 {sheet.title} 第 {header_row} 行为表头"))
        columns = fill._header_columns(sheet, header_row)
        data_row = header_row + 1
        problems, readback = [], []
        for entry in spec.get("fields", []):
            column = fill._column_for(columns, entry["labels"])
            if column is None:
                problems.append(f"缺少列「{entry['key']}」")
                continue
            value = sheet.cell(row=data_row, column=column).value
            text = "" if value is None else str(value)
            readback.append(f"{entry['key']}={text!r}")
            if text.strip() != entry["value"].strip():
                problems.append(f"{entry['key']} 读回 {text!r} ≠ 期望 {entry['value']!r}")
        results.append(check("数据行字段读回", "FAIL" if problems else "PASS",
                             "；".join(problems) or "；".join(readback)))
        examples = [cell.coordinate for cell in sheet[data_row]
                    if isinstance(cell.value, str) and cell.value.startswith("例：")]
        results.append(check("模板示例文字已替换", "FAIL" if examples else "PASS",
                             f"数据行仍含“例：”示例：{'、'.join(examples)}" if examples
                             else "数据行无“例：”示例文字"))

    placeholders = [cell.coordinate for sheet in workbook.worksheets
                    for row in sheet.iter_rows() for cell in row
                    if isinstance(cell.value, str) and PLACEHOLDER in cell.value]
    results.append(check("提交就绪：无【待填】占位符", "FAIL" if placeholders else "PASS",
                         f"仍有 {len(placeholders)} 处【待填：{'、'.join(placeholders[:10])}"
                         if placeholders else "全表无【待填】"))
    results.append(check("页边距 / 跨页 / 中文字体（Word 专项）", "SKIPPED",
                         "Excel 汇总表不适用 Word 版式检查；官方要求提交 Excel 版与加盖公章 PDF 版，"
                         "PDF 版式须由人工渲染确认"))

    ok = not any(item["status"] == "FAIL" for item in results)
    return {"document": str(path), "checks": results, "ok": ok}


# -------------------------------------------------------------------------------- main


def validate(path: Path, template_path: Path | None, texts: dict[str, list[str]],
             docx_module) -> dict:
    reopened, document = check_reopen(path, docx_module)
    results = [reopened]
    if document is None:
        return {"document": str(path), "checks": results, "ok": False}

    template = None
    if template_path is not None and template_path.is_file():
        try:
            template = docx_module.Document(str(template_path))
        except Exception:  # noqa: BLE001 - reported below as its own check
            template = None

    counts = section_counts(document, texts)
    results.append(counts["check"])
    results.append(check_margin_values(document))
    results.append(check_tables(document))
    results.extend(check_cross_page(document, path, template))
    results.append(check_cjk_fonts(document))
    results.append(check_placeholders(document))

    if template_path is None:
        results.append(check("页边距与官方模板一致", "SKIPPED",
                             "未提供 --template，无法与官方页边距比对"))
    elif not template_path.is_file():
        results.append(check("页边距与官方模板一致", "SKIPPED", f"模板不存在：{template_path}"))
    elif template is None:
        results.append(check("页边距与官方模板一致", "FAIL", f"模板无法打开：{template_path}"))
    else:
        results.append(check_margins_match(document, template))

    ok = not any(item["status"] == "FAIL" for item in results)
    return {"document": str(path), "checks": results, "sections": counts["rows"], "ok": ok}


def render(report: dict) -> str:
    out = [f"官方 Word 版式核验（§7.6）：{report['document']}", "=" * 78]
    width = max((len(item["name"]) for item in report["checks"]), default=10)
    width = max(width, 12)
    for item in report["checks"]:
        out.append(f"  {item['status']:<7} {item['name']:<{width}}  {item['detail']}")
        if item.get("measured") and not item["detail"]:
            out.append(f"          {item['measured']}")
        if item.get("pairs"):
            out.append(f"          字体/字号分布：{item['pairs']}")
        if item.get("human_command"):
            out.append(f"          人工复核命令：{item['human_command']}")
    out.append("")
    if "sections" in report:
        out.append("六栏字数：")
        for row in report["sections"]:
            filled = "—" if row["filled"] is None else row["filled"]
            out.append(f"  {row['status']:<7} {row['section']:<12} 填后 {filled} / 上限 {row['limit']}"
                       f" / E5_04 {row['source']}")
    failed = [item["name"] for item in report["checks"] if item["status"] == "FAIL"]
    skipped = [item for item in report["checks"] if item["status"] == "SKIPPED"]
    out.append("")
    out.append(f"结论：{'PASS' if report['ok'] else 'FAIL'}")
    if skipped:
        out.append("未能执行的检查（本机条件限制，**不计为通过**）：")
        for item in skipped:
            out.append(f"  - {item['name']}：{item['detail']}")
            if item.get("human_command"):
                out.append(f"    人工复核命令：{item['human_command']}")
    if failed:
        out.append("未通过：" + "、".join(failed))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="对已生成/已填写的官方 Word 文件执行 §7.6 版式与字数核验。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("document", type=Path, help="待核验的 DOCX")
    parser.add_argument("--template", type=Path, default=None,
                        help="官方原件；给出后比对页边距与节数")
    parser.add_argument("--six", type=Path, default=fill.SIX, help="六栏正文来源（用于比对字数）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if not args.document.is_file():
        print(f"错误：文件不存在：{args.document}", file=sys.stderr)
        return 2
    if not args.six.is_file():
        print(f"错误：找不到六栏正文 {args.six}", file=sys.stderr)
        return 2

    if args.document.suffix.lower() in fill.XLSX_SUFFIXES:
        _require_openpyxl()
        import openpyxl as openpyxl_module

        report = validate_summary(args.document, openpyxl_module)
    else:
        _require_docx()
        import docx as docx_module

        texts = fill.section_texts(args.six)
        report = validate(args.document, args.template, texts, docx_module)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
