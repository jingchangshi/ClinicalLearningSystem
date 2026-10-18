"""Tests for the grant-document checkers (scripts/grant/check_*.py).

The checkers guard the application against stale or fabricated statements, so the
tests pin the two properties that matter most: they catch the planted mistakes, and
they fail (non-zero) when a key document is missing instead of silently passing.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GRANT_SCRIPTS = REPO / "scripts" / "grant"
APPLICATION_DOC = (
    REPO / "docs" / "teaching_grant_2026" / "evidence" / "E5_protocol" / "E5_04_application_text.md"
)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, GRANT_SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


app = _load("check_application_text")
proto = _load("check_protocol_consistency")


# --------------------------------------------------------------------------
# check_application_text
# --------------------------------------------------------------------------


def _doc(tmp_path: Path, mutate=None) -> Path:
    text = APPLICATION_DOC.read_text(encoding="utf-8")
    if mutate:
        text = mutate(text)
    path = tmp_path / "app.md"
    path.write_text(text, encoding="utf-8")
    return path


def _refresh(path: Path) -> None:
    app.update_declarations(path)


def test_real_application_text_passes():
    report = app.check(APPLICATION_DOC)
    failed = [r for r in report["sections"] if r["status"] != "PASS"]
    failed += [c for c in report["content"] if not c["ok"]]
    assert report["ok"], failed
    assert app.main(["--doc", str(APPLICATION_DOC)]) == 0


def test_six_section_limits_match_the_brief():
    assert dict(app.SECTIONS) == {
        "项目研究基础": 600,
        "拟解决的重点问题": 600,
        "项目工作思路与举措": 1000,
        "项目特色与创新": 300,
        "具体实施计划及预期成果": 600,
        "政策支持与经费保障": 800,
    }


def test_missing_document_is_exit_2(tmp_path):
    assert app.main(["--doc", str(tmp_path / "nope.md")]) == 2


def test_missing_section_is_exit_2(tmp_path):
    path = _doc(tmp_path, lambda t: t.replace("## 四、项目特色与创新", "## 四、别的栏目"))
    assert app.main(["--doc", str(path)]) == 2


def test_over_limit_section_fails(tmp_path):
    path = _doc(tmp_path, lambda t: t.replace("## 五、具体实施计划及预期成果\n", "## 五、具体实施计划及预期成果\n\n" + "字" * 700 + "\n", 1))
    _refresh(path)
    report = app.check(path)
    row = next(r for r in report["sections"] if r["section"] == "具体实施计划及预期成果")
    assert row["status"] == "FAIL"
    assert app.main(["--doc", str(path)]) == 1


def test_stale_declaration_fails(tmp_path):
    path = _doc(tmp_path, lambda t: re.sub(r"字数：\d+ / 上限 600", "字数：1 / 上限 600", t, count=1))
    assert app.main(["--doc", str(path)]) == 1


def test_update_declarations_makes_it_consistent(tmp_path):
    path = _doc(tmp_path, lambda t: re.sub(r"字数：\d+ / 上限 600", "字数：1 / 上限 600", t, count=1))
    _refresh(path)
    assert app.main(["--doc", str(path)]) == 0


def test_project_title_fragment_is_caught(tmp_path):
    path = _doc(tmp_path, lambda t: t + "\n\n本项目名为基于人工智能辅助临床推理训练的教学研究。\n")
    report = app.check(path)
    assert not next(c for c in report["content"] if c["name"] == "项目名称全文一致")["ok"]


@pytest.mark.parametrize(
    "bad_sentence",
    [
        "目前已完成49名学生的研究并收集数据。",
        "ClinPath组成绩显著提升，P<0.05。",
        "项目已获伦理批准。",
        "伦理批件号：2026-0123。",
        "每批7人在班内随机分组。",
        "考核使用成人Still病作为A02。",
        "精确检验的最小双侧P为2/35。",
        "合成演示证明ClinPath效果显著。",
        "负责人【待填】〔待用户填写：年份〕。",
        "代码见 https://github.com/someone/ClinicalLearningSystem。",
    ],
)
def test_forbidden_statements_are_caught(tmp_path, bad_sentence):
    # Insert into section one, then refresh declarations so only content checks can fail.
    path = _doc(tmp_path, lambda t: t.replace("## 二、拟解决的重点问题", bad_sentence + "\n\n## 二、拟解决的重点问题", 1))
    _refresh(path)
    report = app.check(path)
    assert not report["ok"], bad_sentence
    assert app.main(["--doc", str(path)]) == 1


def test_negated_honest_statements_are_not_flagged(tmp_path):
    honest = "项目尚未取得伦理批件，没有已完成的真实研究，也不使用合成数据证明效果。"
    path = _doc(tmp_path, lambda t: t.replace("## 二、拟解决的重点问题", honest + "\n\n## 二、拟解决的重点问题", 1))
    _refresh(path)
    assert app.check(path)["ok"]


@pytest.mark.parametrize(
    "needle",
    ["单位承诺：【待填", "最佳带教老师荣誉【待填", "21人的构成及是否与49人重叠【待填"],
)
def test_unknown_facts_must_stay_marked(tmp_path, needle):
    # The doc phrases these slightly differently; locate by a loose pattern and unmark.
    def unmark(text: str) -> str:
        if needle.startswith("单位承诺"):
            return text.replace("单位承诺：【待填：", "单位承诺：某某学院承诺配套（")
        if needle.startswith("最佳带教"):
            return text.replace("获最佳带教老师荣誉【待填：", "获最佳带教老师荣誉（")
        return text.replace("其余21人的构成及是否与49人重叠【待填：", "其余21人的构成已确认（")

    path = _doc(tmp_path, unmark)
    _refresh(path)
    assert not app.check(path)["ok"]


# --------------------------------------------------------------------------
# check_protocol_consistency
# --------------------------------------------------------------------------


@pytest.fixture()
def fake_tree(tmp_path, monkeypatch):
    grant = tmp_path / "docs" / "teaching_grant_2026"
    grant.mkdir(parents=True)
    monkeypatch.setattr(proto, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(proto, "GRANT", grant)
    return grant


def test_missing_key_documents_fail_non_zero(fake_tree):
    # An empty tree: every key document is missing -> exit 2, never "nothing found, pass".
    assert proto.main([]) == 2


def _violations(fake_tree, text: str) -> list[str]:
    path = fake_tree / "x.md"
    path.write_text(text, encoding="utf-8")
    return [v["why"] for v in proto._scan_r74(path, text)]


@pytest.mark.parametrize(
    "line,expected",
    [
        ("CASE-A02 是成人 Still 病伴 MAS 风险的独立考核题本", "AOSD"),
        ("独立考核题本包含 AOSD 病例", "AOSD"),
        ("推荐班内随机分组", "班内"),
        ("D1 考核结果更新能力画像", "D1/T0"),
        ("D4 个性化推荐依据 D1 基线考核", "D4/D5"),
        ("最小双侧 P = 2/35", "2/35"),
        ("α = 0.05 在本设计下不可达", "α=0.05"),
        ("双侧 P 取 2×min(p_lo, p_hi)", "2×min"),
        ("伦理已获批准", "伦理"),
        ("批件号：2026-LL-0123", "批件号"),
        ("已完成 49 名真实学生研究", "已完成"),
        ("合成演示证明 ClinPath 疗效显著", "合成"),
        ("基于人工智能辅助临床推理训练的教学研究", "项目名称"),
    ],
)
def test_r74_rules_catch_planted_mistakes(fake_tree, line, expected):
    whys = _violations(fake_tree, line)
    assert any(expected in w for w in whys), (line, whys)


@pytest.mark.parametrize(
    "line",
    [
        "旧 A02（成人 Still 病）已被新 A02 取代，仅存 Git 历史",
        "D1/T0 不更新能力画像",
        "不得无条件宣称最小双侧 P 为 2/35",
        "尚未取得伦理批件，不预设批件号",
        "合成演示不能作为疗效证据",
        "基于人工智能辅助临床推理训练的医学生个性化学习与形成性评价教学改革研究",
        "感染、药物性狼疮、成人 Still 病、混合性结缔组织病都可模拟 SLE",
    ],
)
def test_r74_rules_accept_honest_statements(fake_tree, line):
    assert _violations(fake_tree, line) == []


@pytest.mark.parametrize(
    "line",
    [
        # The seed Still case lives in the training pool *and* used to be A02, so a
        # training-pool marker must not excuse a stale "current A02 is Still" claim.
        "CASE-A02 为成人 Still 病（种子病例），用于独立考核",
        "CASE-A02（训练库）为成人 Still 病，用于独立考核题本",
        "CASE-A02 是成人 Still 病，属于种子病例",
    ],
)
def test_training_pool_marker_does_not_excuse_a_stale_a02_claim(fake_tree, line):
    assert any("AOSD" in w for w in _violations(fake_tree, line)), line


@pytest.mark.parametrize(
    "line",
    [
        # The legitimate lines that state a training pool does NOT overlap the exam.
        "| 疾病域 | 与训练池（SLE、RA、AAV、IIM，以及种子病例 SLE 合并感染、成人 Still 病）**不重叠**；与 A01/A02 的主诊断也不重叠 |",
        "训练库与考核无同病种内容：种子病例仅 SLE、成人 Still 病、ANCA 血管炎",
        "种子病例为成人 Still 病，与独立考核题本互不重叠",
    ],
)
def test_training_pool_non_overlap_statements_stay_honest(fake_tree, line):
    assert _violations(fake_tree, line) == []


def test_a02_payload_must_be_sicca(fake_tree):
    payload_dir = fake_tree / "workpackages" / "A_cases"
    payload_dir.mkdir(parents=True)
    (payload_dir / "A02_assessment_payload_DRAFT.json").write_text(
        '{"code": "CASE-A02", "title": "成人Still病伴MAS"}', encoding="utf-8"
    )
    whys = [v["why"] for v in proto._check_required()]
    assert any("不是干燥症状病例" in w for w in whys)
    assert any("AOSD" in w for w in whys)


def test_a02_payload_sicca_ok(fake_tree):
    payload_dir = fake_tree / "workpackages" / "A_cases"
    payload_dir.mkdir(parents=True)
    (payload_dir / "A02_assessment_payload_DRAFT.json").write_text(
        '{"code": "CASE-A02-SICCA-V1", "title": "原因待查的干燥症状"}', encoding="utf-8"
    )
    whys = [v["why"] for v in proto._check_required()]
    assert not any("A02 载荷" in w for w in whys)
