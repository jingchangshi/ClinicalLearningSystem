#!/usr/bin/env python3.11
"""Run §7.6's checks on a produced official-form DOCX.

Every check reports ``PASS`` / ``FAIL`` / ``SKIPPED`` with a reason, and a check
that cannot run on this machine says so -- it is never reported as passing. The
checks are:

1. **文件与重新打开** -- the DOCX is a valid zip with the required parts, and
   python-docx can open it and read content back.
2. **字数核验** -- per-section non-whitespace character count from the filled
   section target, against the official limit and against E5_04's own count.
3. **页边距** -- every section has explicit, positive margins. Comparing them with
   the official template needs ``--template``; without it that part is SKIPPED.
4. **表格完整性** -- each row's effective cell count (``gridSpan`` aware) equals the
   table grid's column count; no ragged table.
5. **跨页检查** -- explicit page breaks inside tables, and whether multi-row tables
   allow row splitting (``w:cantSplit``). Visual pagination needs a renderer; when
   none is installed that part is SKIPPED.
6. **中文字体与字号** -- every run carrying CJK text has an explicit East-Asian font
   and size (run, then style, then document default); the distinct font/size pairs
   are reported.
7. **提交就绪** -- no ``【待填`` placeholder remains. Expected to FAIL until real
   people supply the missing facts; it gates submission, not this pipeline.

Usage::

    python3.11 scripts/grant/validate_official_docx.py OUT.docx
    python3.11 scripts/grant/validate_official_docx.py OUT.docx --template official.docx --json

Exit codes: 0 no FAIL, 1 at least one FAIL, 2 the file is missing, 5 python-docx
unavailable.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
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


def section_counts(document, texts: dict[str, list[str]]) -> dict:
    rows = []
    for name, limit in fill.apptext.SECTIONS:
        hit = fill.locate(document, [name, name[2:] if name.startswith("项目") else name])
        source_count = sum(1 for ch in "".join(texts.get(name, [])) if not ch.isspace())
        if hit is None:
            rows.append({"section": name, "filled": None, "source": source_count,
                         "limit": limit, "status": "FAIL", "detail": "官方模板中找不到该栏目标签"})
            continue
        body = hit["target"].text
        if hit["kind"] == "paragraph-append":
            label = hit["label"]
            position = body.find(label)
            if position >= 0:
                body = body[position + len(label):]
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


def check_cross_page(document, path: Path) -> list[dict]:
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
        results.append(check("跨页：多行表格设置行内不拆分", "FAIL",
                             "以下行未设置 w:cantSplit，可能跨页拆分：" + "；".join(unprotected)))
    else:
        results.append(check("跨页：多行表格设置行内不拆分", "PASS", "多行表格均设置 w:cantSplit"))

    renderer = next((name for name in RENDERERS if shutil.which(name)), None)
    if renderer is None:
        results.append(check("跨页：PDF 渲染目视检查", "SKIPPED",
                             "本机无 libreoffice/soffice/pandoc，无法渲染 PDF；"
                             "版式需在有渲染器的机器上人工检查"))
        return results

    with tempfile.TemporaryDirectory() as directory:
        try:
            import subprocess
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


def _east_asian_font(run, paragraph) -> str | None:
    from docx.oxml.ns import qn
    for style in _style_chain(run, paragraph):
        rpr = style.element.rPr
        if rpr is not None and rpr.rFonts is not None:
            value = rpr.rFonts.get(qn("w:eastAsia"))
            if value:
                return value
    return None


def _size(run, paragraph):
    for style in _style_chain(run, paragraph):
        if style.font.size is not None:
            return style.font.size
    return None


def check_cjk_fonts(document) -> dict:
    missing_font = []
    missing_size = []
    pairs: dict[tuple[str, str], int] = {}
    cjk_runs = 0
    for paragraph_index, paragraph in enumerate(fill.iter_paragraphs(document), start=1):
        for run in paragraph.runs:
            if not run.text or not CJK_RE.search(run.text):
                continue
            cjk_runs += 1
            font = _east_asian_font(run, paragraph)
            size = _size(run, paragraph)
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


# -------------------------------------------------------------------------------- main


def validate(path: Path, template_path: Path | None, texts: dict[str, list[str]],
             docx_module) -> dict:
    reopened, document = check_reopen(path, docx_module)
    results = [reopened]
    if document is None:
        return {"document": str(path), "checks": results, "ok": False}

    counts = section_counts(document, texts)
    results.append(counts["check"])
    results.append(check_margin_values(document))
    results.append(check_tables(document))
    results.extend(check_cross_page(document, path))
    results.append(check_cjk_fonts(document))
    results.append(check_placeholders(document))

    if template_path is None:
        results.append(check("页边距与官方模板一致", "SKIPPED",
                             "未提供 --template，无法与官方页边距比对"))
    elif not template_path.is_file():
        results.append(check("页边距与官方模板一致", "SKIPPED", f"模板不存在：{template_path}"))
    else:
        try:
            template = docx_module.Document(str(template_path))
            results.append(check_margins_match(document, template))
        except Exception as exc:  # noqa: BLE001
            results.append(check("页边距与官方模板一致", "FAIL", f"模板无法打开：{exc}"))

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
    out.append("")
    if "sections" in report:
        out.append("六栏字数：")
        for row in report["sections"]:
            filled = "—" if row["filled"] is None else row["filled"]
            out.append(f"  {row['status']:<7} {row['section']:<12} 填后 {filled} / 上限 {row['limit']}"
                       f" / E5_04 {row['source']}")
    failed = [item["name"] for item in report["checks"] if item["status"] == "FAIL"]
    skipped = [item["name"] for item in report["checks"] if item["status"] == "SKIPPED"]
    out.append("")
    out.append(f"结论：{'PASS' if report['ok'] else 'FAIL'}")
    if skipped:
        out.append("未能执行的检查（本机条件限制，不计为通过）：" + "、".join(skipped))
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
