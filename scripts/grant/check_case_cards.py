#!/usr/bin/env python3
"""Read-only dry-run validator for the 2026 teaching-grant case cards.

Checks the six Markdown cards under
``docs/teaching_grant_2026/workpackages/A_cases/`` for:

  * required metadata fields and required sections,
  * the S1-S5 staged-release table (5 rows, 4 non-empty columns),
  * the six-dimension rubric table with the grant weights 10/20/25/15/20/10,
  * at least four common-error entries,
  * a PENDING_REAL_REVIEW review status and no claim of completed review,
  * a 核对提示 field in the guideline section,
  * non-duplicate primary diagnoses across the six cards,
  * training / assessment isolation declarations.

It is deliberately standalone: Python 3.11 standard library only, no import of
the application, no database access, no file writes. Exit code is 0 when every
check passes and 1 when any check fails.

Usage:
    python3 scripts/grant/check_case_cards.py
    python3 scripts/grant/check_case_cards.py --json
    python3 scripts/grant/check_case_cards.py --dir <path> --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CARD_DIR = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "teaching_grant_2026"
    / "workpackages"
    / "A_cases"
)

CARD_GLOBS = ("A01_training_*.md", "A01_assessment_*.md")

EXPECTED_CASES = {
    "CASE-T01": ("training", "A01_training_SLE.md"),
    "CASE-T02": ("training", "A01_training_RA.md"),
    "CASE-T03": ("training", "A01_training_AAV.md"),
    "CASE-T04": ("training", "A01_training_IIM.md"),
    "CASE-A01": ("assessment", "A01_assessment_UA.md"),
    "CASE-A02": ("assessment", "A01_assessment_sicca.md"),
}

REQUIRED_FIELDS = (
    "病例编号",
    "类型",
    "疾病",
    "主诊断",
    "难度",
    "适用学段",
    "训练/考核隔离",
    "审核状态",
)

# Section keyword -> human label. A section is present when a level-2 heading
# contains the keyword.
REQUIRED_SECTIONS = (
    ("教学目标", "教学目标"),
    ("核心表现", "核心表现"),
    ("按 5 阶段", "五阶段释放表"),
    ("诊断及鉴别逻辑", "诊断及鉴别逻辑"),
    ("危险信号", "危险信号"),
    ("检查策略", "检查策略"),
    ("治疗策略", "治疗策略"),
    ("常见错误", "常见错误"),
    ("评分要点", "评分要点"),
    ("指南与文献", "指南与文献"),
    ("脱敏说明", "脱敏说明"),
    ("脱敏检查", "脱敏检查"),
)

RUBRIC_DIMENSIONS = {
    "医学知识": ("medical_knowledge", 10),
    "关键信息提取": ("key_information", 20),
    "鉴别诊断": ("differential_diagnosis", 25),
    "证据整合": ("evidence_integration", 15),
    "临床决策": ("clinical_decision", 20),
    "循证安全": ("evidence_based_medicine", 10),
}

# Claims that would mean a real review already happened. These must never
# appear in an AI-drafted card.
FORBIDDEN_CLAIMS = (
    "已通过审核",
    "通过审核",
    "已完成审核",
    "已审核通过",
    "审核通过",
    "经教师审核通过",
    "已批准用于教学",
    "APPROVED_FOR_TEACHING",
    "REVIEWED_BY_REAL_TEACHER",
)

REVIEW_STATUS = "PENDING_REAL_REVIEW"

TRAINING_ISOLATION_HINTS = ("不进入独立考核", "仅用于形成性训练", "训练病例")
ASSESSMENT_ISOLATION_HINTS = ("不得用于训练", "独立考核病例", "考核前不得")

PASS = "PASS"
FAIL = "FAIL"


@dataclass
class Card:
    path: Path
    text: str
    case_id: str | None = None
    kind: str | None = None
    fields: dict[str, str] = field(default_factory=dict)
    sections: dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class Result:
    case: str
    check: str
    status: str
    detail: str = ""


def _normalise(text: str) -> str:
    return unicodedata.normalize("NFKC", text).strip()


def _strip_markdown(value: str) -> str:
    """Drop wrapping emphasis/backticks without eating underscores inside keys.

    ``PENDING_REAL_REVIEW`` must survive, so only backticks and *edge* emphasis
    markers are removed.
    """

    value = value.replace("`", "").replace("*", "")
    value = re.sub(r"^[\s_>]+", "", value)
    value = re.sub(r"[\s_]+$", "", value)
    return value.strip()


def parse_card(path: Path) -> Card:
    text = _normalise(path.read_text(encoding="utf-8"))
    card = Card(path=path, text=text)

    for line in text.splitlines():
        match = re.match(r"^\s*[-*]\s*([^:：]+)[:：]\s*(.+)$", line)
        if not match:
            continue
        key = match.group(1).strip()
        value = _strip_markdown(match.group(2))
        if key in REQUIRED_FIELDS and key not in card.fields:
            card.fields[key] = value

    card.case_id = card.fields.get("病例编号")
    card.kind = card.fields.get("类型")

    # Split level-2 sections. The H1 title is the preamble.
    parts = re.split(r"^##\s+", text, flags=re.MULTILINE)
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        card.sections[heading.strip()] = body
    return card


def _section_body(card: Card, keyword: str) -> str | None:
    for heading, body in card.sections.items():
        if keyword in heading:
            return body
    return None


def _table(block: str) -> tuple[list[str], list[list[str]]]:
    """Return ``(header, data_rows)`` for the first Markdown table in ``block``."""

    header: list[str] = []
    rows: list[list[str]] = []
    started = False
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if started and (header or rows):
                break
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells if cell):
            started = True
            continue
        if not started:
            started = True
            header = cells
            continue
        rows.append(cells)
    return header, rows


def _table_rows(block: str) -> list[list[str]]:
    return _table(block)[1]


def _numbered_items(block: str) -> list[str]:
    return [
        line.strip()
        for line in block.splitlines()
        if re.match(r"^\s*\d+[.、)]\s+\S", line)
    ]


def normalise_diagnosis(value: str) -> str:
    """Reduce a primary diagnosis to a comparable disease name."""

    text = _normalise(value)
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    text = re.split(r"[，,、;；/]", text, maxsplit=1)[0]
    if "伴" in text[1:]:
        text = text.split("伴", 1)[0]
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，,。.;；:：、（）()\[\]【】]", "", text)
    return text.lower()


def check_card(card: Card) -> list[Result]:
    results: list[Result] = []
    label = card.case_id or card.name

    def add(check: str, ok: bool, detail: str = "") -> None:
        results.append(Result(label, check, PASS if ok else FAIL, detail))

    # --- identity -------------------------------------------------------
    expected = EXPECTED_CASES.get(card.case_id or "")
    if expected is None:
        add("病例编号合法", False, f"未识别的病例编号：{card.case_id!r}")
    else:
        kind, filename = expected
        add("病例编号合法", True, card.case_id or "")
        add(
            "编号与文件名一致",
            card.name == filename,
            f"期望 {filename}，实际 {card.name}",
        )
        expected_kind = "训练病例" if kind == "training" else "独立考核病例"
        add(
            "类型与编号一致",
            card.kind == expected_kind,
            f"期望 {expected_kind}，实际 {card.kind!r}",
        )

    # --- required fields ------------------------------------------------
    missing = [key for key in REQUIRED_FIELDS if not card.fields.get(key)]
    add("必填字段齐全", not missing, "缺少：" + "、".join(missing) if missing else "8/8")

    # --- review status --------------------------------------------------
    status = card.fields.get("审核状态", "")
    add(
        "审核状态 PENDING_REAL_REVIEW",
        status == REVIEW_STATUS,
        f"实际：{status!r}",
    )

    # --- required sections ----------------------------------------------
    missing_sections = [
        human for keyword, human in REQUIRED_SECTIONS if _section_body(card, keyword) is None
    ]
    add(
        "必需章节齐全",
        not missing_sections,
        "缺少：" + "、".join(missing_sections) if missing_sections else "12/12",
    )

    # --- stage table ----------------------------------------------------
    stage_block = _section_body(card, "按 5 阶段")
    if stage_block is None:
        add("五阶段表 S1-S5", False, "未找到章节")
    else:
        header, rows = _table(stage_block)
        stage_ids = [row[0] for row in rows if row]
        expected_ids = [f"S{index}" for index in range(1, 6)]
        shape_ok = len(rows) == 5 and stage_ids == expected_ids
        empty_cells = [
            (row[0], index)
            for row in rows
            if len(row) < 4 or any(not cell for cell in row[:4])
            for index in [row.index("") if "" in row[:4] else -1]
            if index != -1
        ]
        add(
            "五阶段表 S1-S5",
            shape_ok and not empty_cells,
            "5 行 S1-S5，4 列均非空"
            if shape_ok and not empty_cells
            else f"行数={len(rows)}，编号={stage_ids}，空格={empty_cells}",
        )
        if shape_ok:
            add(
                "五阶段表列名",
                all(
                    any(token in cell for cell in header)
                    for token in ("阶段", "释放", "任务", "错误")
                ),
                "列名：" + " / ".join(header),
            )

    # --- common errors --------------------------------------------------
    error_block = _section_body(card, "常见错误")
    if error_block is None:
        add("常见错误 ≥4 条", False, "未找到章节")
    else:
        items = _numbered_items(error_block)
        add("常见错误 ≥4 条", len(items) >= 4, f"{len(items)} 条")

    # --- rubric ---------------------------------------------------------
    rubric_block = _section_body(card, "评分要点")
    if rubric_block is None:
        add("六维评分表", False, "未找到章节")
    else:
        rows = _table_rows(rubric_block)
        found: dict[str, int] = {}
        for row in rows:
            if not row:
                continue
            dimension = row[0].strip()
            if dimension in RUBRIC_DIMENSIONS:
                try:
                    weight = int(row[1])
                except (IndexError, ValueError):
                    continue
                found[dimension] = weight
        problems = []
        for dimension, (_ability_key, expected_weight) in RUBRIC_DIMENSIONS.items():
            del _ability_key  # the ASCII key is documentation only, not compared
            if dimension not in found:
                problems.append(f"缺少 {dimension}")
            elif found[dimension] != expected_weight:
                problems.append(f"{dimension} 权重 {found[dimension]}≠{expected_weight}")
        total = sum(found.values())
        if total != 100:
            problems.append(f"权重合计 {total}≠100")
        add(
            "六维评分表 10/20/25/15/20/10",
            not problems,
            "；".join(problems) if problems else "六维齐全，合计 100",
        )

    # --- guideline + 核对提示 -------------------------------------------
    guideline_block = _section_body(card, "指南与文献")
    if guideline_block is None:
        add("指南章节含核对提示", False, "未找到章节")
    else:
        has_guideline = bool(re.search(r"(EULAR|ACR|中华医学会|KDIGO|指南|标准)", guideline_block))
        has_hint = "核对提示" in guideline_block
        add(
            "指南章节含核对提示",
            has_guideline and has_hint,
            "含指南引用与核对提示" if has_guideline and has_hint else "缺少指南引用或核对提示",
        )

    # --- de-identification ----------------------------------------------
    deid_block = _section_body(card, "脱敏检查")
    if deid_block is None:
        add("脱敏检查表", False, "未找到章节")
    else:
        rows = _table_rows(deid_block)
        checks = {row[0]: row[1] for row in rows if len(row) >= 2}
        real_name = checks.get("是否使用真实姓名", "")
        real_case = checks.get("是否为真实病例", "")
        ok = real_name.startswith("否") and real_case.startswith("否") and len(rows) >= 5
        add(
            "脱敏检查表",
            ok,
            f"{len(rows)} 项；真实姓名={real_name or '缺失'}；真实病例={real_case or '缺失'}",
        )

    # --- forbidden claims -----------------------------------------------
    hits = [phrase for phrase in FORBIDDEN_CLAIMS if phrase in card.text]
    add("未声称已完成审核", not hits, "命中：" + "、".join(hits) if hits else "无")

    # --- isolation ------------------------------------------------------
    isolation = card.fields.get("训练/考核隔离", "")
    if card.case_id and card.case_id.endswith(tuple(f"T0{index}" for index in range(1, 10))):
        ok = all(hint in isolation for hint in TRAINING_ISOLATION_HINTS[:2])
        add("训练/考核隔离声明", ok, isolation)
    elif card.case_id and card.case_id.startswith("CASE-A"):
        ok = all(hint in isolation for hint in ASSESSMENT_ISOLATION_HINTS[:2])
        add("训练/考核隔离声明", ok, isolation)
    else:
        add("训练/考核隔离声明", False, isolation or "缺失")

    return results


def check_cross_card(cards: list[Card]) -> list[Result]:
    results: list[Result] = []

    def add(check: str, ok: bool, detail: str = "") -> None:
        results.append(Result("ALL", check, PASS if ok else FAIL, detail))

    found_ids = {card.case_id for card in cards if card.case_id}
    expected_ids = set(EXPECTED_CASES)
    add(
        "六个病例齐全",
        found_ids == expected_ids,
        "缺少：" + "、".join(sorted(expected_ids - found_ids))
        if expected_ids - found_ids
        else "6/6",
    )

    # Duplicate primary diagnosis after normalisation.
    seen: dict[str, list[str]] = {}
    for card in cards:
        diagnosis = card.fields.get("主诊断", "")
        if not diagnosis:
            continue
        seen.setdefault(normalise_diagnosis(diagnosis), []).append(
            f"{card.case_id}:{diagnosis}"
        )
    duplicates = {key: value for key, value in seen.items() if len(value) > 1}
    add(
        "主诊断不重复",
        not duplicates,
        "重复：" + json.dumps(duplicates, ensure_ascii=False)
        if duplicates
        else f"{len(seen)} 个不同主诊断",
    )

    # Training and assessment disease pools must not overlap.
    training = {
        normalise_diagnosis(card.fields.get("主诊断", ""))
        for card in cards
        if card.kind == "训练病例"
    }
    assessment = {
        normalise_diagnosis(card.fields.get("主诊断", ""))
        for card in cards
        if card.kind == "独立考核病例"
    }
    overlap = (training & assessment) - {""}
    add(
        "训练/考核疾病池不重叠",
        not overlap,
        "重叠：" + "、".join(sorted(overlap)) if overlap else "无重叠",
    )

    add(
        "训练与考核各 4/2 例",
        sum(1 for card in cards if card.kind == "训练病例") == 4
        and sum(1 for card in cards if card.kind == "独立考核病例") == 2,
        f"训练 {sum(1 for c in cards if c.kind == '训练病例')} 例，"
        f"考核 {sum(1 for c in cards if c.kind == '独立考核病例')} 例",
    )

    return results


def discover(card_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for pattern in CARD_GLOBS:
        paths.extend(sorted(card_dir.glob(pattern)))
    return paths


def render_table(results: list[Result]) -> str:
    headers = ("病例", "检查项", "结果", "说明")
    rows = [(r.case, r.check, r.status, r.detail) for r in results]

    def width(index: int) -> int:
        cells = [headers[index]] + [row[index] for row in rows]
        return max(_display_width(cell) for cell in cells)

    widths = [width(index) for index in range(4)]
    lines = [
        "| " + " | ".join(_pad(headers[i], widths[i]) for i in range(4)) + " |",
        "| " + " | ".join("-" * widths[i] for i in range(4)) + " |",
    ]
    for row in rows:
        lines.append(
            "| " + " | ".join(_pad(row[i], widths[i]) for i in range(4)) + " |"
        )
    return "\n".join(lines)


def _display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def _pad(text: str, width: int) -> str:
    return text + " " * (width - _display_width(text))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="只读校验教学病例卡（不导入应用、不连接数据库、不写文件）"
    )
    parser.add_argument("--dir", type=Path, default=DEFAULT_CARD_DIR, help="病例卡目录")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    paths = discover(args.dir)
    if not paths:
        payload = {
            "ok": False,
            "card_dir": str(args.dir),
            "error": "未找到任何病例卡",
            "results": [],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1

    cards = [parse_card(path) for path in paths]
    results: list[Result] = []
    for card in cards:
        results.extend(check_card(card))
    results.extend(check_cross_card(cards))

    failed = [result for result in results if result.status == FAIL]

    if args.json:
        payload = {
            "ok": not failed,
            "card_dir": str(args.dir),
            "cards": [card.name for card in cards],
            "total": len(results),
            "passed": len(results) - len(failed),
            "failed": len(failed),
            "results": [
                {
                    "case": result.case,
                    "check": result.check,
                    "status": result.status,
                    "detail": result.detail,
                }
                for result in results
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"病例卡目录：{args.dir}")
        print(f"发现 {len(cards)} 份卡片：{', '.join(card.name for card in cards)}")
        print()
        print(render_table(results))
        print()
        print(f"合计 {len(results)} 项检查：通过 {len(results) - len(failed)}，失败 {len(failed)}")
        print("总体结果：" + ("PASS" if not failed else "FAIL"))

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
