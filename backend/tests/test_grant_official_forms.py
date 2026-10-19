"""Tests for the official-form fill / validation pipeline.

These tests build **synthetic fixtures** with python-docx / openpyxl: a table of six
labelled section rows plus a few labelled metadata rows, a merged-cell fixture that
mirrors the real official 申报书's layout (prompt paragraph + answer paragraphs), and
an Excel summary table. Every fixture is named and built as a fixture, never as an
official template -- and the fill script's "refuse to treat our own draft as
official" rule is tested by putting this repository's own ``非官方模板`` banner into
one of them.

Attachment identity is tested without any attachment number: the real republished
package numbers the summary table 附件4 while an ``附件3`` is the anonymised
application form, so identity must come from the name *and* the content.

Both scripts import python-docx / openpyxl lazily, so the module skips when they are
absent.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GRANT_SCRIPTS = REPO / "scripts" / "grant"
SIX = REPO / "docs" / "teaching_grant_2026" / "evidence" / "E5_protocol" / "E5_04_application_text.md"

docx = pytest.importorskip("docx", reason="python-docx is needed for the DOCX pipeline tests")
openpyxl = pytest.importorskip("openpyxl", reason="openpyxl is needed for the XLSX pipeline tests")
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

if str(GRANT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GRANT_SCRIPTS))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, GRANT_SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


fill = _load("fill_official_forms")
validate = _load("validate_official_docx")


# --------------------------------------------------------------------------- fixtures


def _cant_split(row) -> None:
    row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))


def _chinese_normal_style(document) -> None:
    style = document.styles["Normal"]
    style.font.name = "SimSun"
    style.font.size = Pt(10.5)
    fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:eastAsia"), "宋体")


def _margins(document) -> None:
    section = document.sections[0]
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.18)
    section.right_margin = Cm(3.18)


def _clear_margins(document) -> None:
    """Simulate an official template that inherits its margins (all unset)."""
    section = document.sections[0]
    for attribute in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(section, attribute, None)


def fixture_docx(path: Path, *, banner: bool = False, drop: str | None = None,
                 prefilled: bool = False, rows: int = 6, margins: bool = True,
                 chinese_style: bool = True, cant_split: bool = True) -> Path:
    """A SYNTHETIC stand-in for 附件2 -- field labels only, no official styling.

    This is a test fixture. It is not, and must never be presented as, the official
    template: the real one is supplied by the applicant and is not on this machine.
    """
    document = docx.Document()
    if chinese_style:
        _chinese_normal_style(document)
    if margins:
        _margins(document)
    if banner:
        document.add_paragraph("非官方模板 · 可编辑草稿 · 测试夹具")
    table = document.add_table(rows=rows, cols=2)
    table.style = "Table Grid"
    placed = 0
    for name, _limit in fill.apptext.SECTIONS:
        if name == drop or placed >= rows:
            continue
        table.cell(placed, 0).text = name
        if prefilled:
            table.cell(placed, 1).text = "已有内容"
        if cant_split:
            _cant_split(table.rows[placed])
        placed += 1
    meta = document.add_table(rows=2, cols=2)
    meta.style = "Table Grid"
    for index, (label, value) in enumerate((("项目名称", ""), ("项目类别", ""))):
        meta.cell(index, 0).text = label
        meta.cell(index, 1).text = value
        if cant_split:
            _cant_split(meta.rows[index])
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    return path


def fixture_summary_docx(path: Path, *, banner: bool = False) -> Path:
    document = docx.Document()
    _chinese_normal_style(document)
    _margins(document)
    if banner:
        document.add_paragraph("非官方模板 · 可编辑草稿 · 测试夹具")
    table = document.add_table(rows=3, cols=2)
    table.style = "Table Grid"
    for index, (label, value) in enumerate((("项目名称", ""), ("项目主持人", ""), ("所在单位", ""))):
        table.cell(index, 0).text = label
        table.cell(index, 1).text = value
        _cant_split(table.rows[index])
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    return path


@pytest.fixture()
def map_path(tmp_path: Path) -> Path:
    """Minimal field map: six sections plus two fields, labels only."""
    payload = {
        "attachment2": {
            "sections": [{"key": name, "limit": limit, "labels": [name]}
                         for name, limit in fill.apptext.SECTIONS],
            "fields": [{"key": "项目名称", "value": "测试标题", "labels": ["项目名称"]}],
        },
        "attachment3": {
            "sections": [],
            "fields": [{"key": "项目名称", "value": "测试标题", "labels": ["项目名称"]}],
        },
    }
    path = tmp_path / "map.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


# ------------------------------------------------------------------------ source text


def test_six_section_text_parses_from_the_real_file():
    texts = fill.section_texts(SIX)
    assert [name for name, _ in fill.apptext.SECTIONS] == list(texts)
    for name, lines in texts.items():
        assert lines, name
        # Declaration lines and rules are structural, never part of the body.
        assert not any(line.startswith("> 字数") for line in lines), name


def test_section_counts_agree_with_the_application_text_checker():
    checker = _load("check_application_text")
    report = checker.check(SIX)
    texts = fill.section_texts(SIX)
    for row in report["sections"]:
        assert sum(1 for ch in "".join(texts[row["section"]]) if not ch.isspace()) == row["count"]


# ---------------------------------------------------------------------------- refusing


def test_refuses_when_official_files_are_absent(tmp_path, capsys):
    out = tmp_path / "out"
    code = fill.main([
        "--attachment2", str(tmp_path / "missing2.docx"),
        "--attachment3", str(tmp_path / "missing3.docx"),
        "--official-dir", str(tmp_path / "empty"),
        "--out-dir", str(out),
    ])
    assert code == 2
    assert not out.exists(), "nothing may be generated when the official files are absent"
    assert "拒绝运行" in capsys.readouterr().err


def test_absence_message_lists_every_accepted_location(tmp_path, capsys):
    # The message must tell the applicant every way to supply the files, including
    # the ZIP, so following the document cannot dead-end at exit 2.
    code = fill.main([
        "--zip", str(tmp_path / "nope.zip"),
        "--official-dir", str(tmp_path / "empty"),
        "--out-dir", str(tmp_path / "out"),
    ])
    assert code == 2
    err = capsys.readouterr().err
    assert "--zip" in err and "--official-dir" in err
    assert "--attachment2" in err and "--attachment3" in err
    assert str(tmp_path / "nope.zip") in err
    assert str(tmp_path / "empty") in err


# ------------------------------------------------------------------------------- ZIP


def _official_zip(tmp_path: Path, *, member2: str, member3: str,
                  decoys: bool = True) -> Path:
    """A ZIP shaped like the applicant's: a subdirectory, plus decoys to ignore."""
    two = fixture_docx(tmp_path / "src2.docx")
    three = fixture_summary_docx(tmp_path / "src3.docx")
    archive = tmp_path / "official.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(two, member2)
        bundle.write(three, member3)
        if decoys:
            bundle.writestr("__MACOSX/._附件2.docx", b"junk")
            bundle.writestr("~$附件2.docx", b"lock file")
            bundle.writestr("材料/附件1：项目选题指南.pdf", b"%PDF-1.4 decoy")
            bundle.writestr("材料/申报通知.pdf", b"%PDF-1.4 decoy")
    return archive


@pytest.fixture()
def minimal_map(tmp_path: Path) -> Path:
    path = tmp_path / "map.json"
    path.write_text(json.dumps({
        "attachment2": {"sections": [{"key": name, "limit": limit, "labels": [name]}
                                     for name, limit in fill.apptext.SECTIONS], "fields": []},
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    return path


def test_fills_directly_from_the_zip_the_document_tells_the_applicant_to_drop(tmp_path, minimal_map):
    archive = _official_zip(
        tmp_path,
        member2="2026年浙江省教改项目申报材料/附件2：教学改革项目申报书.docx",
        member3="2026年浙江省教改项目申报材料/附件3：申报汇总表.docx",
    )
    out = tmp_path / "out"
    code = fill.main(["--zip", str(archive), "--out-dir", str(out),
                      "--field-map", str(minimal_map)])
    assert code == 0
    produced = docx.Document(str(out / fill.OUT_ATTACHMENT2.name))
    for name, _limit in fill.apptext.SECTIONS:
        assert fill.locate(produced, [name]) is not None, name
    assert (out / fill.OUT_ATTACHMENT3.name).is_file()


def test_zip_members_are_reported_and_decoys_ignored(tmp_path, capsys, minimal_map):
    archive = _official_zip(
        tmp_path,
        member2="材料/附件2：教学改革项目申报书.docx",
        member3="材料/附件3：申报汇总表.docx",
    )
    fill.main(["--zip", str(archive), "--out-dir", str(tmp_path / "out"),
               "--field-map", str(minimal_map)])
    printed = capsys.readouterr().out
    assert "附件2：教学改革项目申报书.docx" in printed
    assert "附件3：申报汇总表.docx" in printed
    assert "未解压" in printed, "the notice and 附件1 must be reported as not extracted"


def test_zip_contents_never_land_in_the_repository(tmp_path, minimal_map):
    archive = _official_zip(
        tmp_path,
        member2="材料/附件2：教学改革项目申报书.docx",
        member3="材料/附件3：申报汇总表.docx",
    )
    out = tmp_path / "out"
    before = {p.name for p in fill.OFFICIAL_DIR.iterdir()}
    # Another process may legitimately own a same-prefixed directory (the operator's
    # download scratch), so compare before/after instead of demanding none at all.
    temp_before = set(Path(tempfile.gettempdir()).glob("clinpath-official-*"))
    assert fill.main(["--zip", str(archive), "--out-dir", str(out),
                      "--field-map", str(minimal_map)]) == 0
    after = {p.name for p in fill.OFFICIAL_DIR.iterdir()}
    assert before == after, "extraction must not write into the repo's official/ directory"
    # And this run's temporary extraction directory is gone once it finishes.
    leftovers = set(Path(tempfile.gettempdir()).glob("clinpath-official-*")) - temp_before
    assert leftovers == set(), leftovers


def test_zip_with_only_one_form_still_reports_the_other_as_missing(tmp_path, capsys, minimal_map):
    two = fixture_docx(tmp_path / "src2.docx")
    archive = tmp_path / "partial.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.write(two, "材料/附件2：教学改革项目申报书.docx")
    code = fill.main(["--zip", str(archive), "--official-dir", str(tmp_path / "empty"),
                      "--out-dir", str(tmp_path / "out"), "--field-map", str(minimal_map)])
    assert code == 2
    assert "attachment3" in capsys.readouterr().err


def test_unreadable_suffix_inside_the_zip_is_explained(tmp_path, capsys, minimal_map):
    archive = tmp_path / "doc-only.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("材料/附件2：教学改革项目申报书.doc", b"\xd0\xcf\x11\xe0 old format")
        bundle.writestr("材料/附件3：申报汇总表.doc", b"\xd0\xcf\x11\xe0 old format")
    code = fill.main(["--zip", str(archive), "--official-dir", str(tmp_path / "empty"),
                      "--out-dir", str(tmp_path / "out"), "--field-map", str(minimal_map)])
    assert code == 2
    err = capsys.readouterr().err
    # The applicant put the ZIP where the document said to; the failure must say
    # what is actually wrong with it, not just that nothing was found.
    assert "不是 .docx" in err
    assert "已找到的内容" in err


def test_zip_member_matching_prefers_the_right_attachment():
    hints2 = fill.MEMBER_HINTS["attachment2"]
    hints3 = fill.MEMBER_HINTS["attachment3"]
    names = ["材料/附件2：教学改革项目申报书.docx", "材料/附件3：申报汇总表.docx"]
    assert Path(fill.best_match(names, hints2)).name.startswith("附件2")
    assert Path(fill.best_match(names, hints3)).name.startswith("附件3")
    # A lock file or a resource-fork entry must never win.
    noisy = ["~$附件2.docx", "__MACOSX/._附件2.docx", "材料/附件2：教学改革项目申报书.docx"]
    assert Path(fill.best_match(noisy, hints2)).name == "附件2：教学改革项目申报书.docx"


def test_extracted_docx_in_the_official_dir_is_also_accepted(tmp_path, minimal_map):
    official = tmp_path / "official"
    official.mkdir()
    fixture_docx(official / "附件2：教学改革项目申报书.docx")
    fixture_summary_docx(official / "附件3：申报汇总表.docx")
    out = tmp_path / "out"
    code = fill.main(["--official-dir", str(official), "--out-dir", str(out),
                      "--field-map", str(minimal_map)])
    assert code == 0
    assert (out / fill.OUT_ATTACHMENT2.name).is_file()


def test_explicit_paths_win_over_zip_and_directory(tmp_path, capsys, minimal_map):
    archive = _official_zip(tmp_path, member2="材料/附件2：教学改革项目申报书.docx",
                            member3="材料/附件3：申报汇总表.docx")
    explicit2 = fixture_docx(tmp_path / "explicit2.docx")
    explicit3 = fixture_summary_docx(tmp_path / "explicit3.docx")
    out = tmp_path / "out"
    assert fill.main(["--zip", str(archive), "--attachment2", str(explicit2),
                      "--attachment3", str(explicit3), "--out-dir", str(out),
                      "--field-map", str(minimal_map)]) == 0
    printed = capsys.readouterr().out
    assert "命令行指定" in printed


def test_the_home_config_directory_is_really_searched(tmp_path, monkeypatch, minimal_map):
    """Path B in the document must be a location the script actually looks in."""
    home_official = tmp_path / "config" / "clinpath" / "official"
    home_official.mkdir(parents=True)
    archive = _official_zip(tmp_path, member2="材料/附件2：教学改革项目申报书.docx",
                            member3="材料/附件3：申报汇总表.docx")
    # Move the ZIP to the "home" location and point the search list at it.
    target = home_official / fill.ZIP_NAME
    target.write_bytes(archive.read_bytes())
    monkeypatch.setattr(fill, "OFFICIAL_DIRS", (tmp_path / "absent", home_official))
    monkeypatch.setattr(fill, "ZIP_CANDIDATES", (tmp_path / "absent" / fill.ZIP_NAME, target))

    out = tmp_path / "out"
    assert fill.main(["--official-dir", str(tmp_path / "absent"), "--out-dir", str(out),
                      "--field-map", str(minimal_map)]) == 0
    assert (out / fill.OUT_ATTACHMENT2.name).is_file()


def test_a_bad_explicit_zip_still_falls_back_to_the_default_locations(
        tmp_path, monkeypatch, minimal_map):
    home_official = tmp_path / "config" / "clinpath" / "official"
    home_official.mkdir(parents=True)
    archive = _official_zip(tmp_path, member2="材料/附件2：教学改革项目申报书.docx",
                            member3="材料/附件3：申报汇总表.docx")
    target = home_official / fill.ZIP_NAME
    target.write_bytes(archive.read_bytes())
    monkeypatch.setattr(fill, "OFFICIAL_DIRS", (tmp_path / "absent", home_official))
    monkeypatch.setattr(fill, "ZIP_CANDIDATES", (target,))

    out = tmp_path / "out"
    assert fill.main(["--zip", str(tmp_path / "typo.zip"), "--official-dir",
                      str(tmp_path / "absent"), "--out-dir", str(out),
                      "--field-map", str(minimal_map)]) == 0
    assert (out / fill.OUT_ATTACHMENT2.name).is_file()


def test_refuses_to_fill_our_own_generated_draft(tmp_path, capsys):
    two = fixture_docx(tmp_path / "a2.docx", banner=True)
    three = fixture_summary_docx(tmp_path / "a3.docx", banner=True)
    out = tmp_path / "out"
    code = fill.main(["--attachment2", str(two), "--attachment3", str(three), "--out-dir", str(out)])
    assert code == 6
    assert not out.exists()
    assert "非官方模板" in capsys.readouterr().out


def test_missing_field_is_reported_not_skipped(tmp_path, capsys):
    two = fixture_docx(tmp_path / "a2.docx", drop="项目特色与创新")
    three = fixture_summary_docx(tmp_path / "a3.docx")
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {
            "sections": [{"key": name, "limit": limit, "labels": [name]}
                         for name, limit in fill.apptext.SECTIONS],
            "fields": [],
        },
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    code = fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(map_path)])
    assert code == 3
    printed = capsys.readouterr().out
    assert "未找到 section「项目特色与创新」" in printed
    assert not (out / fill.OUT_ATTACHMENT2.name).exists(), "no partial file without --write-partial"


def test_write_partial_still_writes_what_matched(tmp_path):
    two = fixture_docx(tmp_path / "a2.docx", drop="项目特色与创新")
    three = fixture_summary_docx(tmp_path / "a3.docx")
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {
            "sections": [{"key": name, "limit": limit, "labels": [name]}
                         for name, limit in fill.apptext.SECTIONS],
            "fields": [],
        },
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    code = fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(map_path), "--write-partial"])
    assert code == 3
    produced = out / fill.OUT_ATTACHMENT2.name
    assert produced.is_file()
    assert docx.Document(str(produced)) is not None


def test_existing_content_is_a_conflict_unless_overwrite(tmp_path):
    two = fixture_docx(tmp_path / "a2.docx", prefilled=True)
    three = fixture_summary_docx(tmp_path / "a3.docx")
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {"sections": [{"key": "项目研究基础", "limit": 600,
                                      "labels": ["项目研究基础"]}], "fields": []},
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    args = ["--attachment2", str(two), "--attachment3", str(three),
            "--out-dir", str(out), "--field-map", str(map_path)]
    assert fill.main(args) == 7
    assert not (out / fill.OUT_ATTACHMENT2.name).exists()
    assert fill.main(args + ["--overwrite"]) == 0
    assert (out / fill.OUT_ATTACHMENT2.name).is_file()


# ------------------------------------------------------------------------------ filling


def test_fills_six_sections_and_fields(tmp_path):
    two = fixture_docx(tmp_path / "a2.docx")
    three = fixture_summary_docx(tmp_path / "a3.docx")
    out = tmp_path / "out"
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {
            "sections": [{"key": name, "limit": limit, "labels": [name]}
                         for name, limit in fill.apptext.SECTIONS],
            "fields": [{"key": "项目名称", "value": "测试标题", "labels": ["项目名称"]}],
        },
        "attachment3": {"sections": [], "fields": [
            {"key": "项目名称", "value": "测试标题", "labels": ["项目名称"]}]},
    }, ensure_ascii=False), encoding="utf-8")

    assert fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(map_path)]) == 0

    produced = docx.Document(str(out / fill.OUT_ATTACHMENT2.name))
    texts = fill.section_texts(SIX)
    for name, _limit in fill.apptext.SECTIONS:
        hit = fill.locate(produced, [name])
        assert hit is not None, name
        assert hit["target"].text.strip() == "\n".join(texts[name]) or \
            hit["target"].text.strip() == "".join(texts[name]), name
    assert fill.locate(produced, ["项目名称"])["target"].text.strip() == "测试标题"

    summary = docx.Document(str(out / fill.OUT_ATTACHMENT3.name))
    assert fill.locate(summary, ["项目名称"])["target"].text.strip() == "测试标题"


def test_output_character_counts_match_the_source(tmp_path):
    two = fixture_docx(tmp_path / "a2.docx")
    three = fixture_summary_docx(tmp_path / "a3.docx")
    out = tmp_path / "out"
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {"sections": [{"key": name, "limit": limit, "labels": [name]}
                                     for name, limit in fill.apptext.SECTIONS], "fields": []},
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    assert fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(map_path)]) == 0

    produced = docx.Document(str(out / fill.OUT_ATTACHMENT2.name))
    texts = fill.section_texts(SIX)
    for name, _limit in fill.apptext.SECTIONS:
        target = fill.locate(produced, [name])["target"].text
        filled = sum(1 for ch in target if not ch.isspace())
        source = sum(1 for ch in "".join(texts[name]) if not ch.isspace())
        assert filled == source, (name, filled, source)


def test_dry_run_writes_nothing(tmp_path):
    two = fixture_docx(tmp_path / "a2.docx")
    three = fixture_summary_docx(tmp_path / "a3.docx")
    out = tmp_path / "out"
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {"sections": [{"key": name, "limit": limit, "labels": [name]}
                                     for name, limit in fill.apptext.SECTIONS], "fields": []},
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    assert fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(map_path), "--dry-run"]) == 0
    assert not out.exists()


def test_over_limit_section_is_refused(tmp_path):
    # A 5-row fixture cannot take six sections, but an over-long *value* is what
    # the limit rule guards: shrink a section limit to 10 characters.
    two = fixture_docx(tmp_path / "a2.docx")
    three = fixture_summary_docx(tmp_path / "a3.docx")
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {"sections": [{"key": "项目研究基础", "limit": 10,
                                      "labels": ["项目研究基础"]}], "fields": []},
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    assert fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(map_path)]) == 4
    assert not (out / fill.OUT_ATTACHMENT2.name).exists()


def test_labels_are_matched_with_numbering_and_spacing(tmp_path):
    two = fixture_docx(tmp_path / "a2.docx")
    document = docx.Document(str(two))
    table = document.tables[0]
    table.cell(0, 0).text = "一、项目研究基础"
    table.cell(1, 0).text = "拟解决的重点问题："
    document.save(str(two))

    reopened = docx.Document(str(two))
    assert fill.locate(reopened, ["项目研究基础"]) is not None
    assert fill.locate(reopened, ["拟解决的重点问题"]) is not None


def test_locate_falls_back_to_paragraphs(tmp_path):
    path = tmp_path / "p.docx"
    document = docx.Document()
    document.add_paragraph("项目名称：________________")
    document.add_paragraph("")
    document.add_paragraph("项目周期")
    document.add_paragraph("")
    document.save(str(path))

    reopened = docx.Document(str(path))
    name = fill.locate(reopened, ["项目名称"])
    period = fill.locate(reopened, ["项目周期"])
    assert name["kind"] == "paragraph-append"
    assert period["kind"] == "paragraph-next"

    fill.apply_write(name, ["测试标题"])
    fill.apply_write(period, ["【待填：周期】"])
    assert "测试标题" in reopened.paragraphs[0].text
    assert "____" not in reopened.paragraphs[0].text
    assert reopened.paragraphs[3].text == "【待填：周期】"


# --------------------------------------------------------------------------- validation


def _filled(tmp_path: Path) -> Path:
    two = fixture_docx(tmp_path / "a2.docx")
    three = fixture_summary_docx(tmp_path / "a3.docx")
    out = tmp_path / "out"
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {"sections": [{"key": name, "limit": limit, "labels": [name]}
                                     for name, limit in fill.apptext.SECTIONS], "fields": []},
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    assert fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(map_path)]) == 0
    return out / fill.OUT_ATTACHMENT2.name


def _status(report: dict, name: str) -> str:
    return next(item["status"] for item in report["checks"] if item["name"] == name)


def test_validation_passes_a_well_formed_fixture(tmp_path):
    produced = _filled(tmp_path)
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    assert _status(report, "文件与重新打开") == "PASS"
    assert _status(report, "字数核验") == "PASS"
    assert _status(report, "页边距") == "PASS"
    assert _status(report, "表格完整性") == "PASS"
    assert _status(report, "跨页：表格内不得有显式分页符") == "PASS"
    assert _status(report, "跨页：多行表格设置行内不拆分") == "PASS"
    assert _status(report, "中文字体与字号") == "PASS"
    # Without the official template, agreement cannot be claimed.
    assert _status(report, "页边距与官方模板一致") == "SKIPPED"


def test_validation_reports_a_missing_file(tmp_path):
    assert validate.main([str(tmp_path / "nope.docx")]) == 2


def test_validation_flags_unset_chinese_fonts(tmp_path):
    produced = _filled(tmp_path)
    document = docx.Document(str(produced))
    document.styles["Normal"].element.get_or_add_rPr().get_or_add_rFonts().attrib.clear()
    document.styles["Normal"].font.size = None
    document.save(str(produced))
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    assert _status(report, "中文字体与字号") == "FAIL"


def test_validation_flags_a_ragged_table(tmp_path):
    produced = _filled(tmp_path)
    document = docx.Document(str(produced))
    table = document.tables[0]
    table.rows[0]._tr.remove(table.rows[0].cells[-1]._tc)
    document.save(str(produced))
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    assert _status(report, "表格完整性") == "FAIL"


def test_validation_flags_an_explicit_page_break_inside_a_table(tmp_path):
    produced = _filled(tmp_path)
    document = docx.Document(str(produced))
    run = document.tables[0].cell(0, 0).paragraphs[0].add_run()
    run.add_break(docx.enum.text.WD_BREAK.PAGE)
    document.save(str(produced))
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    assert _status(report, "跨页：表格内不得有显式分页符") == "FAIL"


def test_validation_flags_rows_that_may_split(tmp_path):
    produced = _filled(tmp_path)
    document = docx.Document(str(produced))
    for row in document.tables[0].rows:
        properties = row._tr.trPr
        if properties is None:
            continue
        for element in properties.findall(qn("w:cantSplit")):
            properties.remove(element)
    document.save(str(produced))
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    assert _status(report, "跨页：多行表格设置行内不拆分") == "FAIL"


def test_validation_flags_missing_margins(tmp_path):
    two = fixture_docx(tmp_path / "a2.docx", margins=False)
    three = fixture_summary_docx(tmp_path / "a3.docx")
    out = tmp_path / "out"
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {"sections": [{"key": name, "limit": limit, "labels": [name]}
                                     for name, limit in fill.apptext.SECTIONS], "fields": []},
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    assert fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(map_path)]) == 0
    produced = out / fill.OUT_ATTACHMENT2.name
    document = docx.Document(str(produced))
    _clear_margins(document)
    document.save(str(produced))
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    assert _status(report, "页边距") == "FAIL"


def test_validation_compares_margins_with_the_template(tmp_path):
    produced = _filled(tmp_path)
    template = fixture_docx(tmp_path / "a2.docx")
    report = validate.validate(produced, template, fill.section_texts(SIX), docx)
    assert _status(report, "页边距与官方模板一致") == "PASS"

    shifted = docx.Document(str(template))
    shifted.sections[0].left_margin = Cm(1.0)
    shifted_path = tmp_path / "shifted.docx"
    shifted.save(str(shifted_path))
    report = validate.validate(produced, shifted_path, fill.section_texts(SIX), docx)
    assert _status(report, "页边距与官方模板一致") == "FAIL"


def test_validation_reports_over_limit_and_placeholder(tmp_path):
    produced = _filled(tmp_path)
    document = docx.Document(str(produced))
    target = fill.locate(document, ["项目特色与创新"])["target"]
    target.text = "字" * 400
    document.save(str(produced))
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    assert _status(report, "字数核验") == "FAIL"

    document = docx.Document(str(produced))
    fill.locate(document, ["项目名称"])["target"].text = "【待填：姓名】"
    document.save(str(produced))
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    assert _status(report, "提交就绪：无【待填】占位符") == "FAIL"


def test_placeholder_check_passes_only_once_the_text_has_no_markers(tmp_path):
    # The real E5_04 body deliberately carries 13 【待填】 markers, so a fill from
    # the real source must FAIL submission-readiness -- that is the honest result,
    # not a bug. Removing the markers is what a human filling them in looks like.
    produced = _filled(tmp_path)
    assert _status(validate.validate(produced, None, fill.section_texts(SIX), docx),
                   "提交就绪：无【待填】占位符") == "FAIL"

    document = docx.Document(str(produced))
    for paragraph in fill.iter_paragraphs(document):
        for run in paragraph.runs:
            run.text = run.text.replace("【待填", "已填")
    document.save(str(produced))
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    assert _status(report, "提交就绪：无【待填】占位符") == "PASS"


def test_pdf_render_check_is_skipped_honestly_when_no_renderer(tmp_path, monkeypatch):
    monkeypatch.setattr(validate.shutil, "which", lambda _name: None)
    produced = _filled(tmp_path)
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    item = next(item for item in report["checks"] if item["name"] == "跨页：PDF 渲染目视检查")
    assert item["status"] == "SKIPPED"
    # Fixed wording: the report must never drift into implying the check ran.
    assert item["detail"] == (
        "no libreoffice/pandoc on this machine; requires a human render check")
    assert "libreoffice --headless --convert-to pdf" in item["human_command"]
    # A SKIPPED check is never counted as a pass -- the report must say so.
    text = validate.render(report)
    assert "未能执行的检查" in text
    assert "no libreoffice/pandoc on this machine" in text
    assert not any(item["status"] == "PASS" for item in report["checks"]
                   if item["name"] == "跨页：PDF 渲染目视检查")


def test_no_renderer_reason_is_the_agreed_wording():
    assert validate.NO_RENDERER_REASON == (
        "no libreoffice/pandoc on this machine; requires a human render check")
    command = validate.render_command(Path("out.docx"))
    assert command.startswith("libreoffice --headless --convert-to pdf")
    assert "out.docx" in command


def test_render_check_does_not_run_when_no_renderer_is_on_path(tmp_path, monkeypatch):
    """Even if a renderer name were found, absence of the binary must not 'pass'."""
    monkeypatch.setattr(validate.shutil, "which", lambda _name: None)

    def explode(*_args, **_kwargs):  # pragma: no cover - must never be called
        raise AssertionError("the renderer must not be invoked when it is absent")

    monkeypatch.setattr(validate.subprocess, "run", explode, raising=False)
    produced = _filled(tmp_path)
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    item = next(item for item in report["checks"] if item["name"] == "跨页：PDF 渲染目视检查")
    assert item["status"] == "SKIPPED"


def test_render_states_skipped_checks_are_not_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(validate.shutil, "which", lambda _name: None)
    produced = _filled(tmp_path)
    report = validate.validate(produced, None, fill.section_texts(SIX), docx)
    text = validate.render(report)
    assert "未能执行的检查" in text
    assert "PDF 渲染" in text


# --------------------------------------------------- the real 申报书's merged-cell layout


def fixture_official_layout_docx(path: Path, *, tail_row: bool = True) -> Path:
    """A SYNTHETIC stand-in for the real official 申报书's section layout.

    Each section is one merged cell whose FIRST paragraph is the prompt and whose
    following paragraphs are the answer slots; the last section puts its prompt on
    its own row and leaves the next row for the body -- exactly the shape the real
    2026 Zhejiang form uses. This is a test fixture, not the official template.
    """
    document = docx.Document()
    _chinese_normal_style(document)
    _margins(document)
    names = list(fill.apptext.SECTIONS)
    table = document.add_table(rows=len(names) + (1 if tail_row else 0), cols=1)
    table.style = "Table Grid"
    for index, (name, limit) in enumerate(names):
        cell = table.cell(index, 0)
        cell.text = f"{index + 1}.{name}（不超过{limit}字）"
        if not (tail_row and index == len(names) - 1):
            cell.add_paragraph("")
            cell.add_paragraph("")
        _cant_split(table.rows[index])
    if tail_row:
        _cant_split(table.rows[-1])
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    return path


def test_section_body_is_written_after_the_prompt_paragraph(tmp_path):
    two = fixture_official_layout_docx(tmp_path / "a2.docx")
    three = fixture_summary_docx(tmp_path / "a3.docx")
    out = tmp_path / "out"
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {"sections": [
            {"key": name, "limit": limit, "block": True, "labels": [name]}
            for name, limit in fill.apptext.SECTIONS], "fields": []},
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")

    assert fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(map_path)]) == 0

    produced = docx.Document(str(out / fill.OUT_ATTACHMENT2.name))
    texts = fill.section_texts(SIX)
    whole = fill.document_text(produced)
    for index, (name, limit) in enumerate(fill.apptext.SECTIONS, start=1):
        entry = {"key": name, "block": True, "labels": [name]}
        hit = fill.find_section_hit(produced, entry)
        assert hit is not None and hit["kind"] == "cell-block", name
        body = fill.hit_body_text(hit)
        filled = sum(1 for ch in body if not ch.isspace())
        source = sum(1 for ch in "".join(texts[name]) if not ch.isspace())
        assert filled == source, (name, filled, source)
        # The prompt is never overwritten and never duplicated.
        prompt = f"{index}.{name}（不超过{limit}字）"
        assert whole.count(prompt) == 1, (name, whole.count(prompt))


def test_the_prompt_survives_a_second_run_and_the_counts_are_stable(tmp_path):
    two = fixture_official_layout_docx(tmp_path / "a2.docx")
    three = fixture_summary_docx(tmp_path / "a3.docx")
    out = tmp_path / "out"
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {"sections": [{"key": name, "limit": limit, "block": True,
                                      "labels": [name]}
                                     for name, limit in fill.apptext.SECTIONS], "fields": []},
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    args = ["--attachment2", str(two), "--attachment3", str(three),
            "--out-dir", str(out), "--field-map", str(map_path)]
    assert fill.main(args) == 0
    first = (out / fill.OUT_ATTACHMENT2.name).read_bytes()

    # Re-running reads the untouched input again, so the result must be identical:
    # a locator that only recognised empty answer paragraphs would fail here.
    assert fill.main(args) == 0
    assert (out / fill.OUT_ATTACHMENT2.name).read_bytes() == first


def test_re_running_against_an_already_filled_file_is_not_a_conflict(tmp_path):
    """Idempotence: content equal to the value being written is not a conflict."""
    two = fixture_official_layout_docx(tmp_path / "a2.docx")
    three = fixture_summary_docx(tmp_path / "a3.docx")
    out = tmp_path / "out"
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({
        "attachment2": {"sections": [{"key": name, "limit": limit, "block": True,
                                      "labels": [name]}
                                     for name, limit in fill.apptext.SECTIONS], "fields": []},
        "attachment3": {"sections": [], "fields": []},
    }, ensure_ascii=False), encoding="utf-8")
    assert fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(map_path)]) == 0

    # Now feed the FILLED file back in as the input.
    assert fill.main(["--attachment2", str(out / fill.OUT_ATTACHMENT2.name),
                      "--attachment3", str(three), "--out-dir", str(out),
                      "--field-map", str(map_path)]) == 0


# ------------------------------------------------------- identity without a number


def test_the_anonymised_application_is_never_taken_for_the_summary(tmp_path, minimal_map):
    official = tmp_path / "official"
    official.mkdir()
    fixture_docx(official / "附件2：教学改革项目申报书.docx")
    fixture_docx(official / "附件3：申报书匿名版.docx")
    fixture_summary_docx(official / "附件4：申报汇总表.docx")
    out = tmp_path / "out"
    assert fill.main(["--official-dir", str(official), "--out-dir", str(out),
                      "--field-map", str(minimal_map)]) == 0
    summary = docx.Document(str(out / fill.OUT_ATTACHMENT3_DOCX.name))
    assert fill.locate(summary, ["项目主持人"]) is not None
    application = docx.Document(str(out / fill.OUT_ATTACHMENT2.name))
    # The filled application must be the 申报书 (six sections), not the 匿名版.
    assert fill.locate(application, ["项目研究基础"]) is not None


def test_the_application_number_is_never_used_to_choose_the_summary(tmp_path, minimal_map):
    """A summary table numbered 附件3 (as the 通知's own list does) still works."""
    official = tmp_path / "official"
    official.mkdir()
    fixture_docx(official / "附件2：教学改革项目申报书.docx")
    fixture_summary_docx(official / "附件3：申报汇总表.docx")
    out = tmp_path / "out"
    assert fill.main(["--official-dir", str(official), "--out-dir", str(out),
                      "--field-map", str(minimal_map)]) == 0
    assert (out / fill.OUT_ATTACHMENT3_DOCX.name).is_file()


def test_an_anonymous_document_is_not_accepted_as_the_application_form(tmp_path, capsys, minimal_map):
    official = tmp_path / "official"
    official.mkdir()
    fixture_docx(official / "附件3：申报书匿名版.docx")
    fixture_summary_docx(official / "附件4：申报汇总表.docx")
    code = fill.main(["--official-dir", str(official), "--out-dir", str(tmp_path / "out"),
                      "--field-map", str(minimal_map)])
    assert code == 2
    assert "attachment2" in capsys.readouterr().err


def test_the_closing_summary_table_is_never_taken_for_the_application_summary():
    hints = fill.MEMBER_HINTS["attachment3"]
    names = ["附件4：结题验收汇总表.xlsx", "附件4：申报汇总表.xlsx"]
    assert Path(fill.best_match(names, hints, fill.XLSX_SUFFIXES)).name.endswith("申报汇总表.xlsx")


# ------------------------------------------------------------------- Excel summary table


def fixture_summary_xlsx(path: Path, *, banner: bool = False) -> Path:
    """A SYNTHETIC stand-in for 附件4 -- the official summary table is Excel."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet["A1"] = "附件4"
    sheet["A2"] = "浙江省高等教育2026年教学改革项目申报汇总表"
    sheet["A3"] = "学院（盖章）：          联系人：            联系电话："
    if banner:
        sheet["A4"] = "非官方模板 · 可编辑草稿 · 测试夹具"
        header_row = 5
    else:
        header_row = 4
    headers = ["序号", "项目层次", "项目类别", "项目方向", "项目名称", "第一完成单位",
               "主持人", "出生年月", "职称", "管理职务", "项目组主要成员（不超过8位）",
               "主持人是否为中层干部及以上", "备注"]
    for index, header in enumerate(headers, start=1):
        sheet.cell(row=header_row, column=index, value=header)
    data_row = header_row + 1
    sheet.cell(row=data_row, column=1, value=1)
    sheet.cell(row=data_row, column=3, value="01")
    sheet.cell(row=data_row, column=8, value="例：1981.01")
    sheet.cell(row=data_row, column=11, value="例：张三、李四")
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


def _summary_map(tmp_path: Path) -> Path:
    path = tmp_path / "summary_map.json"
    path.write_text(json.dumps({
        "attachment2": {"sections": [{"key": name, "limit": limit, "block": True,
                                      "labels": [name]}
                                     for name, limit in fill.apptext.SECTIONS], "fields": []},
        "attachment3": fill.DEFAULT_FIELD_MAP["attachment3"],
    }, ensure_ascii=False), encoding="utf-8")
    return path


def test_fills_the_excel_summary_table(tmp_path):
    two = fixture_official_layout_docx(tmp_path / "a2.docx")
    three = fixture_summary_xlsx(tmp_path / "a3.xlsx")
    out = tmp_path / "out"
    assert fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(_summary_map(tmp_path))]) == 0

    produced = out / fill.OUT_ATTACHMENT3_XLSX.name
    assert produced.is_file(), "the summary output keeps the official Excel format"
    sheet = openpyxl.load_workbook(produced)["Sheet1"]
    assert sheet["B5"].value == "02"
    assert sheet["C5"].value == "01", "the template's pre-filled 项目类别 is untouched"
    assert sheet["D5"].value == fill.PROJECT_DIRECTION
    assert sheet["E5"].value == fill.TITLE
    for column in ("F", "G", "H", "I", "J", "K", "L"):
        assert "【待填" in str(sheet[f"{column}5"].value), column
    # The template's own examples must not survive as if they were data.
    assert not str(sheet["H5"].value).startswith("例：")
    assert not str(sheet["K5"].value).startswith("例：")
    # A person's facts are never invented.
    assert sheet["G5"].value == fill.PENDING_HOST


def test_the_excel_summary_is_identified_by_content_not_by_number(tmp_path, capsys):
    official = tmp_path / "official"
    official.mkdir()
    fixture_official_layout_docx(official / "附件2：教学改革项目申报书.docx")
    fixture_docx(official / "附件3：申报书匿名版.docx")
    fixture_summary_xlsx(official / "att4_汇总表.xlsx")
    out = tmp_path / "out"
    code = fill.main(["--official-dir", str(official), "--out-dir", str(out),
                      "--field-map", str(_summary_map(tmp_path))])
    assert code == 0, capsys.readouterr().out
    assert (out / fill.OUT_ATTACHMENT3_XLSX.name).is_file()


def test_the_official_draft_banner_stops_the_excel_path(tmp_path, capsys):
    two = fixture_official_layout_docx(tmp_path / "a2.docx")
    three = fixture_summary_xlsx(tmp_path / "a3.xlsx", banner=True)
    out = tmp_path / "out"
    code = fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(_summary_map(tmp_path))])
    assert code == 6
    # The 申报书 is written first, so only the rejected summary must be absent.
    assert not (out / fill.OUT_ATTACHMENT3_XLSX.name).exists()
    assert "非官方模板" in capsys.readouterr().out


def test_xlsx_summary_validation_reads_the_values_back(tmp_path):
    two = fixture_official_layout_docx(tmp_path / "a2.docx")
    three = fixture_summary_xlsx(tmp_path / "a3.xlsx")
    out = tmp_path / "out"
    assert fill.main(["--attachment2", str(two), "--attachment3", str(three),
                      "--out-dir", str(out), "--field-map", str(_summary_map(tmp_path))]) == 0
    report = validate.validate_summary(out / fill.OUT_ATTACHMENT3_XLSX.name, openpyxl)
    assert _status(report, "文件与重新打开（Excel）") == "PASS"
    assert _status(report, "汇总表表头识别") == "PASS"
    assert _status(report, "数据行字段读回") == "PASS"
    assert _status(report, "模板示例文字已替换") == "PASS"
    # Real people are still missing, so submission readiness is honestly FAIL.
    assert _status(report, "提交就绪：无【待填】占位符") == "FAIL"
    # Word-only checks never become passes for a spreadsheet.
    assert _status(report, "页边距 / 跨页 / 中文字体（Word 专项）") == "SKIPPED"
    assert report["ok"] is False


def test_xlsx_summary_validation_reports_a_missing_file(tmp_path):
    assert validate.main([str(tmp_path / "nope.xlsx")]) == 2


def test_missing_openpyxl_exits_with_the_same_code_as_missing_python_docx(capsys, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake(name, *args, **kwargs):
        if name == "openpyxl":
            raise ModuleNotFoundError("No module named 'openpyxl'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(SystemExit) as excinfo:
        fill._require_openpyxl()
    assert excinfo.value.code == 5
    assert "未安装 openpyxl" in capsys.readouterr().err


# ------------------------------------------------------- the official field map itself


def test_the_default_field_map_never_invents_a_person():
    """Every identity field in the official map is a 【待填】 marker, not a name."""
    for entry in fill.DEFAULT_FIELD_MAP["attachment2"]["fields"]:
        if entry["key"] in {"项目名称", "项目层次", "项目方向"}:
            continue
        assert "【待填" in entry["value"], entry["key"]
    for entry in fill.DEFAULT_FIELD_MAP["attachment3"]["fields"]:
        if entry["key"] in {"项目名称", "项目层次", "项目方向", "备注"}:
            continue
        assert "【待填" in entry["value"], entry["key"]


def test_the_default_map_carries_the_real_official_section_labels():
    labels = {entry["key"]: entry["labels"]
              for entry in fill.DEFAULT_FIELD_MAP["attachment2"]["sections"]}
    assert "项目拟解决的重点问题" in labels["拟解决的重点问题"]
    assert "本项目特色与创新之处" in labels["项目特色与创新"]
    assert "具体实施计划（含进展安排）及预期成果" in labels["具体实施计划及预期成果"]


def test_project_direction_records_its_evidence_and_its_alternative():
    assert fill.PROJECT_DIRECTION == "十"
    assert fill.PROJECT_DIRECTION_ALTERNATIVE == "九"
    assert fill.PROJECT_DIRECTION_STATUS == "待申请人确认"
