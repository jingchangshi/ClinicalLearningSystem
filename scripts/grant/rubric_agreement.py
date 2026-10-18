#!/usr/bin/env python3
"""六维形成性评价量表的评分者一致性分析（工作包 B04）。

只使用 Python 3.11 标准库。设计原则：

1. **没有真实评分就不出数**。若输入文件中
   ``rater_origin=REAL_BLINDED_RATER`` 的有效评分为 0，
   脚本打印明确提示并以退出码 2 结束，绝不生成占位数字。
2. **模拟评分者必须显式声明**。``rater_origin=SIMULATED_NOT_HUMAN``
   的文件必须加 ``--demo`` 才会分析，且输出带醒目横幅。
3. **一个样本一行**。同一 ``sample_id`` 必须恰好有两位评分者的完整评分；
   缺项样本被排除并列出，不插补。
4. 所有统计量都在本文件内计算，不调用外部统计库。

用法::

    python3.11 scripts/grant/rubric_agreement.py <ratings.csv>
    python3.11 scripts/grant/rubric_agreement.py <ratings.csv> --demo
    python3.11 scripts/grant/rubric_agreement.py --self-check

退出码::

    0  成功（仅真实评分；或 --self-check 通过）
    2  尚无可分析的真实评分
    3  输入格式错误
    4  模拟数据但未加 --demo
    5  --demo 文件混入真实评分，或真实文件混入模拟评分
    6  自检失败
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RUBRIC_VERSION = "rubric-v0.1"

# 权重必须与 B01_rubric_v0.1.md 第 1.1 节一致。改这里就是改量表，必须升版本号。
DIMENSIONS: list[tuple[str, str, float]] = [
    ("medical_knowledge", "医学知识", 0.10),
    ("key_information", "关键信息", 0.20),
    ("differential_diagnosis", "鉴别诊断", 0.25),
    ("evidence_integration", "证据整合", 0.15),
    ("clinical_decision", "临床决策", 0.20),
    ("evidence_based_medicine", "循证安全", 0.10),
]
DIMENSION_KEYS = [key for key, _, _ in DIMENSIONS]

REAL_ORIGIN = "REAL_BLINDED_RATER"
SIMULATED_ORIGIN = "SIMULATED_NOT_HUMAN"

BANNER_SIMULATED = "模拟评分者示例｜SIMULATED_NOT_HUMAN｜不是真实教师一致性"
NO_REAL_DATA_MESSAGE = (
    "尚无可分析的真实评分（REAL_BLINDED_RATER=0），不得报告真实教师一致性"
)

EXIT_OK = 0
EXIT_NO_REAL_DATA = 2
EXIT_BAD_INPUT = 3
EXIT_DEMO_FLAG_REQUIRED = 4
EXIT_MIXED_ORIGIN = 5
EXIT_SELF_CHECK_FAILED = 6


# ---------------------------------------------------------------------------
# 统计核心
# ---------------------------------------------------------------------------


def round_half_up(value: float, digits: int = 1) -> float:
    """四舍五入（不用 Python 的银行家舍入），与 B01 第 4.1 节的算例一致。"""
    quant = Decimal(1).scaleb(-digits)
    return float(Decimal(repr(value)).quantize(quant, rounding=ROUND_HALF_UP))


def weighted_total(scores: dict[str, float]) -> float:
    """按量表权重合成总分：Σ(score × weight%)，保留 1 位小数（四舍五入）。"""
    return round_half_up(sum(scores[key] * weight for key, _, weight in DIMENSIONS), 1)


def icc_2_1(matrix: Sequence[Sequence[float]]) -> float | None:
    """ICC(2,1)：双向随机效应、绝对一致性、单评分者。

    ``matrix`` 为 n 个受试者 × k 个评分者的完整平衡矩阵。
    使用 Shrout & Fleiss 的 ICC(2,1) 公式：

        ICC(2,1) = (MSR - MSE) / (MSR + (k-1)·MSE + k·(MSC - MSE)/n)

    方差为零或设计不平衡时返回 ``None``（不制造数字）。
    """
    n = len(matrix)
    if n < 2:
        return None
    k = len(matrix[0])
    if k < 2 or any(len(row) != k for row in matrix):
        return None

    grand = sum(sum(row) for row in matrix) / (n * k)
    row_means = [sum(row) / k for row in matrix]
    col_means = [sum(matrix[i][j] for i in range(n)) / n for j in range(k)]

    ss_rows = k * sum((mean - grand) ** 2 for mean in row_means)
    ss_cols = n * sum((mean - grand) ** 2 for mean in col_means)
    ss_total = sum((value - grand) ** 2 for row in matrix for value in row)
    ss_error = ss_total - ss_rows - ss_cols

    ms_rows = ss_rows / (n - 1)
    ms_cols = ss_cols / (k - 1)
    ms_error = ss_error / ((n - 1) * (k - 1))

    denominator = ms_rows + (k - 1) * ms_error + k * (ms_cols - ms_error) / n
    if denominator <= 0:
        return None
    return (ms_rows - ms_error) / denominator


def bin_score(score: float) -> str:
    """把 0-100 分数映射到量表的三档锚点。"""
    if score <= 39.999:
        return "low"
    if score <= 69.999:
        return "mid"
    return "high"


def cohen_kappa(pairs: list[tuple[str, str]], categories: list[str] | None = None) -> float | None:
    """两名评分者、无序类别的 Cohen's kappa。

    ``pairs`` 是 ``(rater1_category, rater2_category)`` 的列表。
    期望一致率 pe=1（只有一个类别被使用）时返回 ``None``，因为 kappa 无定义。
    """
    if not pairs:
        return None
    if categories is None:
        categories = sorted({label for pair in pairs for label in pair})
    if len(categories) < 2:
        return None

    total = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / total
    expected = 0.0
    for category in categories:
        p_a = sum(1 for a, _ in pairs if a == category) / total
        p_b = sum(1 for _, b in pairs if b == category) / total
        expected += p_a * p_b
    if math.isclose(expected, 1.0):
        return None
    return (observed - expected) / (1.0 - expected)


def agreement_rates(deltas: list[float]) -> dict[str, float]:
    """完全一致 / ±5 以内 / ±10 以内的比例。"""
    if not deltas:
        return {"exact": 0.0, "within5": 0.0, "within10": 0.0}
    total = len(deltas)
    return {
        "exact": sum(1 for d in deltas if abs(d) < 1e-9) / total,
        "within5": sum(1 for d in deltas if abs(d) <= 5 + 1e-9) / total,
        "within10": sum(1 for d in deltas if abs(d) <= 10 + 1e-9) / total,
    }


# ---------------------------------------------------------------------------
# 自检：证明 ICC 与 kappa 的实现是对的
# ---------------------------------------------------------------------------


def self_check() -> bool:
    checks: list[tuple[str, bool, str]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append((name, passed, detail))

    # 1. 完全一致 -> ICC = 1
    perfect = [[10, 10], [20, 20], [30, 30], [40, 40]]
    value = icc_2_1(perfect)
    record("完全一致的评分 ICC=1", value is not None and math.isclose(value, 1.0, abs_tol=1e-9),
           f"得到 {value!r}")

    # 2. 手算样例：MSR=848/3, MSE=8/3, MSC=0, n=4, k=2 -> 280/284
    hand = [[10, 12], [20, 22], [30, 28], [40, 38]]
    value = icc_2_1(hand)
    expected = 280 / 284
    record("手算样例 ICC=280/284", value is not None and math.isclose(value, expected, abs_tol=1e-12),
           f"得到 {value!r}，期望 {expected!r}")

    # 3. 系统性偏移会降低 ICC(2,1)（绝对一致性，不是一致性相关）
    shifted = [[10, 15], [20, 25], [30, 35], [40, 45]]
    value = icc_2_1(shifted)
    record("系统性偏移使 ICC<1", value is not None and value < 1.0, f"得到 {value!r}")

    # 4. 受试者顺序不影响 ICC
    reordered = list(reversed(hand))
    value = icc_2_1(reordered)
    record("受试者重排不改变 ICC", value is not None and math.isclose(value, expected, abs_tol=1e-12),
           f"得到 {value!r}")

    # 5. kappa 手算样例：10 对，一致 8 对（0.80）；两评分者边际均为 7/3，
    #    pe = 0.7*0.7 + 0.3*0.3 = 0.58；kappa = (0.80-0.58)/(1-0.58) = 0.5238
    pairs = [("1", "1")] * 6 + [("1", "0"), ("0", "1")] + [("0", "0")] * 2
    value = cohen_kappa(pairs, ["0", "1"])
    expected_kappa = (0.8 - 0.58) / (1 - 0.58)
    record("手算样例 kappa=0.5238", value is not None and math.isclose(value, expected_kappa, abs_tol=1e-12),
           f"得到 {value!r}，期望 {expected_kappa!r}")

    # 6. kappa 完全一致 -> 1
    value = cohen_kappa([("low", "low"), ("high", "high"), ("mid", "mid")], ["low", "mid", "high"])
    record("完全一致的 kappa=1", value is not None and math.isclose(value, 1.0, abs_tol=1e-12),
           f"得到 {value!r}")

    # 7. 三档分箱边界
    bins_ok = [bin_score(x) for x in (0, 39, 39.9, 40, 69, 69.9, 70, 100)] == [
        "low", "low", "low", "mid", "mid", "mid", "high", "high",
    ]
    record("低/中/高分箱边界", bins_ok, "39→low, 40→mid, 69→high 边界正确")

    # 8. 加权总分
    total = weighted_total({
        "medical_knowledge": 80, "key_information": 70, "differential_diagnosis": 60,
        "evidence_integration": 75, "clinical_decision": 65, "evidence_based_medicine": 90,
    })
    record("加权总分=70.3", math.isclose(total, 70.3, abs_tol=1e-9), f"得到 {total}")

    # 9. 权重和必须为 1.00（B01 第 4.2 节第 3 条）
    weight_sum = sum(Decimal(str(weight)) for _, _, weight in DIMENSIONS)
    record("权重和=1.00", weight_sum == Decimal("1.00"), f"得到 {weight_sum}")

    width = max(len(name) for name, _, _ in checks)
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name:<{width}}  {detail}")
    return all(passed for _, passed, _ in checks)


# ---------------------------------------------------------------------------
# 输入
# ---------------------------------------------------------------------------


@dataclass
class Rating:
    sample_id: str
    case_id: str
    rubric_version: str
    rater_id: str
    rater_origin: str
    scores: dict[str, float]
    total: float | None
    review_date: str
    remarks: str


class InputError(Exception):
    pass


def _parse_float(raw: str, column: str, row_number: int) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise InputError(f"第 {row_number} 行 {column} 不是数字：{raw!r}") from None
    if not 0 <= value <= 100:
        raise InputError(f"第 {row_number} 行 {column} 超出 0-100：{value}")
    return value


def read_ratings(path: Path) -> list[Rating]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise InputError("CSV 没有表头")
        missing = [name for name in ("sample_id", "case_id", "rubric_version", "rater_id",
                                     "rater_origin", *DIMENSION_KEYS, "total",
                                     "review_date", "remarks") if name not in reader.fieldnames]
        if missing:
            raise InputError(f"缺少列：{', '.join(missing)}")

        ratings: list[Rating] = []
        for row_number, row in enumerate(reader, start=2):
            if not (row.get("sample_id") or "").strip():
                continue
            scores: dict[str, float] = {}
            for key in DIMENSION_KEYS:
                raw = (row.get(key) or "").strip()
                if raw:
                    scores[key] = _parse_float(raw, key, row_number)
            raw_total = (row.get("total") or "").strip()
            ratings.append(Rating(
                sample_id=row["sample_id"].strip(),
                case_id=(row.get("case_id") or "").strip(),
                rubric_version=(row.get("rubric_version") or "").strip(),
                rater_id=(row.get("rater_id") or "").strip(),
                rater_origin=(row.get("rater_origin") or "").strip(),
                scores=scores,
                total=_parse_float(raw_total, "total", row_number) if raw_total else None,
                review_date=(row.get("review_date") or "").strip(),
                remarks=(row.get("remarks") or "").strip(),
            ))
    return ratings


# ---------------------------------------------------------------------------
# 分析
# ---------------------------------------------------------------------------


@dataclass
class Analysis:
    complete_samples: list[str]
    excluded: list[str]
    rater_ids: list[str]
    per_dimension: dict[str, dict[str, str | float | int | None]]
    totals: dict[str, float | int | None]
    agreement: dict[str, dict[str, float]]
    icc: dict[str, float | None]
    kappa: dict[str, float | None]
    kappa_pooled: float | None
    total_warnings: list[str]


def analyse(ratings: list[Rating]) -> Analysis:
    by_sample: dict[str, list[Rating]] = {}
    for rating in ratings:
        by_sample.setdefault(rating.sample_id, []).append(rating)

    complete: dict[str, list[Rating]] = {}
    excluded: list[str] = []
    for sample_id, rows in by_sample.items():
        usable = [row for row in rows if set(row.scores) == set(DIMENSION_KEYS)]
        if len(usable) == 2:
            complete[sample_id] = usable
        else:
            excluded.append(sample_id)

    sample_ids = sorted(complete)
    rater_ids = sorted({row.rater_id for rows in complete.values() for row in rows})

    per_dimension: dict[str, dict[str, str | float | int | None]] = {}
    for key, label, _ in DIMENSIONS:
        values = [row.scores[key] for rows in complete.values() for row in rows]
        per_dimension[key] = {
            "label": label,
            "mean": round(statistics.fmean(values), 2) if values else None,
            "sd": round(statistics.stdev(values), 2) if len(values) > 1 else None,
            "n": len(values),
        }

    # 总分：优先使用填写的 total，缺失时按量表权重计算；不一致时记录警告。
    totals: dict[str, float | None] = {"mean": None, "sd": None, "n": None}
    total_warnings: list[str] = []
    computed: list[float] = []
    for sample_id in sample_ids:
        for row in complete[sample_id]:
            value = weighted_total(row.scores)
            if row.total is not None and not math.isclose(row.total, value, abs_tol=0.05):
                total_warnings.append(
                    f"{sample_id}/{row.rater_id or '?'}: 填写 total={row.total} "
                    f"与加权计算 {value} 不一致（已按加权计算值分析）"
                )
            computed.append(value)
    if computed:
        totals = {
            "mean": round(statistics.fmean(computed), 2),
            "sd": round(statistics.stdev(computed), 2) if len(computed) > 1 else None,
            "n": len(computed),
        }

    # 配对：按 rater_id 排序保证 A/B 顺序稳定。
    def pair(sample_id: str) -> tuple[Rating, Rating]:
        rows = sorted(complete[sample_id], key=lambda row: row.rater_id)
        return rows[0], rows[1]

    agreement: dict[str, dict[str, float]] = {}
    icc: dict[str, float | None] = {}
    kappa: dict[str, float | None] = {}
    kappa_pairs: list[tuple[str, str]] = []

    for key, label, _ in DIMENSIONS:
        deltas = [pair(sample_id)[0].scores[key] - pair(sample_id)[1].scores[key]
                  for sample_id in sample_ids]
        agreement[key] = agreement_rates(deltas)
        matrix = [[pair(sample_id)[0].scores[key], pair(sample_id)[1].scores[key]]
                  for sample_id in sample_ids]
        icc[key] = icc_2_1(matrix)
        binned = [(bin_score(pair(sample_id)[0].scores[key]), bin_score(pair(sample_id)[1].scores[key]))
                  for sample_id in sample_ids]
        kappa_pairs.extend(binned)
        kappa[key] = cohen_kappa(binned, ["low", "mid", "high"])

    total_deltas = [weighted_total(pair(sample_id)[0].scores) - weighted_total(pair(sample_id)[1].scores)
                    for sample_id in sample_ids]
    agreement["total"] = agreement_rates(total_deltas)
    icc["total"] = icc_2_1([
        [weighted_total(pair(sample_id)[0].scores), weighted_total(pair(sample_id)[1].scores)]
        for sample_id in sample_ids
    ])
    total_binned = [
        (bin_score(weighted_total(pair(sample_id)[0].scores)),
         bin_score(weighted_total(pair(sample_id)[1].scores)))
        for sample_id in sample_ids
    ]
    kappa["total"] = cohen_kappa(total_binned, ["low", "mid", "high"])

    return Analysis(
        complete_samples=sample_ids,
        excluded=excluded,
        rater_ids=rater_ids,
        per_dimension=per_dimension,
        totals=totals,
        agreement=agreement,
        icc=icc,
        kappa=kappa,
        kappa_pooled=cohen_kappa(kappa_pairs, ["low", "mid", "high"]),
        total_warnings=total_warnings,
    )


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------


def _fmt(value: object, digits: int = 3) -> str:
    if not isinstance(value, (int, float)):
        return "不可计算"
    return f"{value:.{digits}f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "不可计算"
    return f"{value * 100:.1f}%"


def print_report(result: Analysis, *, demo: bool, source: Path, row_count: int) -> None:
    rule = "=" * 78
    print(rule)
    if demo:
        print(f"  {BANNER_SIMULATED}")
        print("  本输出由计算机生成的模拟评分者产生，仅用于验证脚本可运行。")
        print("  它不能用于任何关于真实教师评分者一致性的陈述。")
    else:
        print("  ClinPath 六维形成性评价量表 评分者一致性分析")
        print("  数据来源：REAL_BLINDED_RATER（真实盲法评分者）")
    print(rule)
    print(f"  输入文件      : {source}")
    print(f"  量表版本      : {RUBRIC_VERSION}")
    print(f"  评分行数      : {row_count}")
    print(f"  完整样本数    : {len(result.complete_samples)}（每个样本恰好两位评分者）")
    print(f"  评分者        : {', '.join(result.rater_ids) if result.rater_ids else '无'}")
    if result.excluded:
        print(f"  已排除样本    : {', '.join(result.excluded)}（评分者不足两位或维度不完整）")
    print()

    print("[1] 各维度描述统计（合并两位评分者的全部评分）")
    print(f"  {'维度':<10}{'key':<26}{'均值':>8}{'SD':>8}{'n':>6}")
    for key, label, _ in DIMENSIONS:
        stats = result.per_dimension[key]
        print(f"  {label:<10}{key:<26}{_fmt(stats['mean'], 2):>8}{_fmt(stats['sd'], 2):>8}{stats['n']:>6}")
    print()

    print("[2] 加权总分（Σ 维度分 × 权重）")
    print(f"  均值 {_fmt(result.totals['mean'], 2)}  SD {_fmt(result.totals['sd'], 2)}  n {result.totals['n']}")
    if result.total_warnings:
        print("  注意：以下行的 total 列与加权计算不一致，分析采用加权计算值：")
        for warning in result.total_warnings:
            print(f"    - {warning}")
    print()

    print("[3] 两评分者配对一致性")
    print(f"  {'维度':<10}{'完全一致':>12}{'±5以内':>12}{'±10以内':>12}")
    for key, label, _ in DIMENSIONS:
        rates = result.agreement[key]
        print("  " + label.ljust(10) + _pct(rates["exact"]).rjust(12)
              + _pct(rates["within5"]).rjust(12) + _pct(rates["within10"]).rjust(12))
    rates = result.agreement["total"]
    print("  " + "加权总分".ljust(10) + _pct(rates["exact"]).rjust(12)
          + _pct(rates["within5"]).rjust(12) + _pct(rates["within10"]).rjust(12))
    print()

    print("[4] ICC(2,1)：双向随机效应 / 绝对一致性 / 单评分者")
    print(f"  {'维度':<10}{'ICC(2,1)':>12}")
    for key, label, _ in DIMENSIONS:
        print(f"  {label:<10}{_fmt(result.icc[key]):>12}")
    print(f"  {'加权总分':<10}{_fmt(result.icc['total']):>12}")
    print("  说明：n<2、评分完全无差异或方差为 0 时显示“不可计算”，不插补。")
    print()

    print("[5] Cohen's kappa（分数按低 0-39 / 中 40-69 / 高 70-100 分箱）")
    print(f"  {'维度':<10}{'kappa':>12}")
    for key, label, _ in DIMENSIONS:
        print(f"  {label:<10}{_fmt(result.kappa[key]):>12}")
    print(f"  {'加权总分':<10}{_fmt(result.kappa['total']):>12}")
    print(f"  {'全部维度合并':<10}{_fmt(result.kappa_pooled):>12}")
    print("  说明：只有一个分箱被使用时 kappa 无定义，显示“不可计算”。")
    print()

    print("[6] 解释边界")
    print("  - 这些数字只描述本文件中的评分者，不外推到其他教师或其他样本。")
    print("  - 一致性高不等于评分正确；两位评分者可能共同偏离量表锚点。")
    print("  - 样本量小时置信区间很宽，不应据此做通过/不通过的硬性判定。")
    if demo:
        print(f"  - {BANNER_SIMULATED}")
    print(rule)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="六维量表评分者一致性分析（B04）")
    parser.add_argument("ratings", nargs="?", type=Path, help="评分 CSV 路径")
    parser.add_argument("--demo", action="store_true",
                        help="显式声明输入为模拟评分者数据；输出会带 SIMULATED_NOT_HUMAN 横幅")
    parser.add_argument("--self-check", action="store_true", help="运行 ICC/kappa 自检后退出")
    args = parser.parse_args(argv)

    if args.self_check:
        print("ICC(2,1) / Cohen's kappa 自检：")
        return EXIT_OK if self_check() else EXIT_SELF_CHECK_FAILED

    if args.ratings is None:
        parser.error("需要提供评分 CSV 路径，或使用 --self-check")

    try:
        ratings = read_ratings(args.ratings)
    except (OSError, InputError) as error:
        print(f"输入错误：{error}", file=sys.stderr)
        return EXIT_BAD_INPUT

    origins = {rating.rater_origin for rating in ratings}
    unknown = origins - {REAL_ORIGIN, SIMULATED_ORIGIN}
    if unknown:
        print(f"输入错误：未知 rater_origin：{', '.join(sorted(unknown))}", file=sys.stderr)
        return EXIT_BAD_INPUT

    real_count = sum(
        1 for rating in ratings
        if rating.rater_origin == REAL_ORIGIN and set(rating.scores) == set(DIMENSION_KEYS)
    )
    simulated_count = sum(
        1 for rating in ratings
        if rating.rater_origin == SIMULATED_ORIGIN and set(rating.scores) == set(DIMENSION_KEYS)
    )

    if simulated_count and real_count:
        print("输入错误：同一文件混有真实评分与模拟评分，必须分开。", file=sys.stderr)
        return EXIT_MIXED_ORIGIN

    if simulated_count:
        if not args.demo:
            print("输入文件是模拟评分者数据（SIMULATED_NOT_HUMAN）。", file=sys.stderr)
            print("如确需演示脚本，请显式加 --demo；输出会被标注为模拟示例。", file=sys.stderr)
            return EXIT_DEMO_FLAG_REQUIRED
        if simulated_count < 2:
            print(NO_REAL_DATA_MESSAGE)
            return EXIT_NO_REAL_DATA
        result = analyse(ratings)
        print_report(result, demo=True, source=args.ratings, row_count=len(ratings))
        return EXIT_OK

    if real_count == 0:
        print(NO_REAL_DATA_MESSAGE)
        print(f"（文件：{args.ratings}；REAL_BLINDED_RATER 有效评分行 = 0）")
        return EXIT_NO_REAL_DATA

    result = analyse(ratings)
    warnings = [
        f"{row.sample_id}/{row.rater_id or '?'}: rater_id 为空" if not row.rater_id else ""
        for row in ratings if row.rater_origin == REAL_ORIGIN and not row.rater_id
    ]
    warnings += [
        f"{row.sample_id}/{row.rater_id}: review_date 为空" if not row.review_date else ""
        for row in ratings if row.rater_origin == REAL_ORIGIN and row.rater_id and not row.review_date
    ]
    warnings = [text for text in warnings if text]
    if warnings:
        print("输入警告：真实评分缺少评分者身份或日期（B03 要求必填）：", file=sys.stderr)
        for text in warnings[:10]:
            print(f"  - {text}", file=sys.stderr)
        if len(warnings) > 10:
            print(f"  - 其余 {len(warnings) - 10} 条省略", file=sys.stderr)
        print("", file=sys.stderr)
    if len(result.complete_samples) < 2:
        print(NO_REAL_DATA_MESSAGE)
        print(
            f"（仅有 {len(result.complete_samples)} 个样本具备两位评分者的完整评分；"
            "至少需要 2 个才能计算一致性）"
        )
        return EXIT_NO_REAL_DATA

    print_report(result, demo=False, source=args.ratings, row_count=len(ratings))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
