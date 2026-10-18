#!/usr/bin/env python3.11
"""E5 样本量可行性计算（仅标准库，可离线复现）。

用途：为 docs/teaching_grant_2026/evidence/E5_protocol/E5_02_SAP_statistical_analysis_plan.md
提供真实可复现的算术输出。**本脚本不读取任何真实学生数据**；第 [5] 节读取合成演示
CSV，唯一目的是说明"模拟数据不能用来估计效应量"，不产生任何效应量估计。

**本脚本中的每一个 d 都是"如果真实效应是这个值，需要多少人"的示例假设，
不是对本研究效应的估计，也不是从任何数据算出来的。** 真实效应量未知，
必须由预试验或文献确定（见 SAP §7.6）。

本研究的**真实规模**（教研室已确认的排课条件）：
    风湿免疫本科见习 7 天/批 × 7 人/批 × 7 批 = 49 名见习学生（主研究总体）；
    另有 21 名实习阶段学生为独立扩展人群，**不并入主结局分析**。

**分组方案已锁定为唯一一种：7 个批次整群随机分配。** 预先固定 3 个批次入 ClinPath、
4 个批次入常规 CBL，再随机选定"哪 3 个批次"入 ClinPath——合法分配数 = C(7,3) = 35 种。
申请人已明确**否决**任何"把一个 7 人批次拆成两个教学组"的方案（教学组织约束），
因此本脚本**不再计算任何批内随机（3+4）方案**。第 [6] 节只按这一整群规模重算可行性。

运行：
    python3.11 scripts/grant/sample_size.py

实现约定：
- 正态分位数使用标准库 statistics.NormalDist().inv_cdf（不引入 scipy）。
- t 分位数用不完全 Beta 函数 + 二分法，与 backend/app/services/demo_research.py
  同一套纯标准库做法，避免"论文里一个数、平台里另一个数"。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import NormalDist

N = NormalDist()
ALPHA = 0.05
POWER = 0.80


# --------------------------------------------------------------------------
# 分布工具
# --------------------------------------------------------------------------
def z(p: float) -> float:
    return N.inv_cdf(p)


def _betacf(a: float, b: float, x: float) -> float:
    """不完全 Beta 函数的连分式（Lentz 法）。"""
    tiny, eps, max_iter = 1e-300, 3e-16, 400
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """正则化不完全 Beta 函数 I_x(a, b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(log_beta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    x = df / (df + t * t)
    tail = 0.5 * _betai(df / 2.0, 0.5, x)
    return 1.0 - tail if t >= 0 else tail


def t_quantile(p: float, df: float) -> float:
    """二分法求 t 分位数（p > 0.5）。"""
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# --------------------------------------------------------------------------
# 样本量
# --------------------------------------------------------------------------
def n_normal(d: float, alpha: float = ALPHA, power: float = POWER) -> float:
    """两组等量、双尾、正态近似：n/组 = 2(z_{1-α/2}+z_{1-β})² / d²。"""
    return 2.0 * (z(1 - alpha / 2) + z(power)) ** 2 / d**2


def n_t(d: float, alpha: float = ALPHA, power: float = POWER) -> int:
    """t 分布修正：power(n) = Φ(d·√(n/2) − t_{1−α/2, 2n−2})，向上搜索。"""
    start = max(2, int(math.ceil(n_normal(d, alpha, power))))
    for n in range(start, start + 500):
        crit = t_quantile(1 - alpha / 2, 2 * n - 2)
        achieved = N.cdf(d * math.sqrt(n / 2.0) - crit)
        if achieved >= power:
            return n
    raise RuntimeError("no convergence")


def achieved_power(d: float, n: int, alpha: float = ALPHA) -> float:
    crit = t_quantile(1 - alpha / 2, 2 * n - 2)
    return N.cdf(d * math.sqrt(n / 2.0) - crit)


def mdd(n: int, alpha: float = ALPHA, power: float = POWER) -> float:
    """给定 n/组，80% 功效可检出的最小标准化差值（正态近似）。"""
    return (z(1 - alpha / 2) + z(power)) * math.sqrt(2.0 / n)


def clusters_per_arm(d: float, m: int, rho: float, alpha: float = ALPHA, power: float = POWER) -> float:
    """整群分配（每群 m 人，组内相关 rho）所需群数/组。"""
    deff = 1.0 + (m - 1) * rho
    return n_normal(d, alpha, power) * deff / m


def cluster_effective_n(k: int, m: int, rho: float) -> float:
    """k 个群、每群 m 人时的有效样本量（设计效应校正后）。"""
    return k * m / (1.0 + (m - 1) * rho)


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------
def main() -> None:
    za, zb = z(1 - ALPHA / 2), z(POWER)
    print("=" * 74)
    print("E5 样本量可行性计算   α=0.05（双尾）  power=0.80  两组等量")
    print("=" * 74)
    print("注意：本脚本中的所有 d 都是**示例假设**（“如果真实效应是 d，需要多少人”），")
    print("      不是本研究的效应估计，也不来自任何真实或合成数据。")
    print("      真实效应量未知，须由预试验或文献确定（见 SAP §7.6）。")
    print()
    print(f"z_(1-α/2) = {za:.6f}")
    print(f"z_(1-β)   = {zb:.6f}")
    print(f"(z_(1-α/2)+z_(1-β))^2 = {(za + zb) ** 2:.6f}")
    print(f"2*(...)^2 = {2 * (za + zb) ** 2:.6f}   → n/组 = {2 * (za + zb) ** 2:.4f} / d^2")
    print()

    print("-" * 74)
    print("[1] 正态近似 vs t 分布修正（d = 组间差值 / 变化量标准差；d 为示例假设）")
    print("-" * 74)
    print(f"{'d':>5} {'n/组(正态)':>12} {'n/组(t修正)':>12} {'+15%脱落':>10} {'合计N':>8}")
    for d in (0.40, 0.50, 0.60, 0.70, 0.80, 1.00):
        raw = n_normal(d)
        exact = n_t(d)
        inflated = math.ceil(exact / 0.85)
        print(f"{d:>5.2f} {raw:>12.2f} {exact:>12d} {inflated:>10d} {2 * inflated:>8d}")
    print()

    print("-" * 74)
    print("[2] 可行性反推：若只能招到 n/组，80% 功效能检出多大的 d？")
    print("-" * 74)
    print(f"{'n/组':>6} {'最小可检出d':>14} {'d=0.50功效':>12} {'d=0.60功效':>12} {'d=0.70功效':>12}")
    for n in (10, 15, 20, 21, 28, 30, 40, 45, 60, 90):
        print(
            f"{n:>6d} {mdd(n):>14.3f} {achieved_power(0.50, n):>12.3f} "
            f"{achieved_power(0.60, n):>12.3f} {achieved_power(0.70, n):>12.3f}"
        )
    print("读法：本研究 49 名见习学生按 7 个批次整群分配，3 批 vs 4 批 = 21 vs 28 人/组。")
    print("      较小臂 21 人/组只能稳定检出 d≈0.87 的大效应（尚未计入整群设计效应）；")
    print("      想检出 d=0.50 需要 64 人/组，是当前规模的 3 倍以上。")
    print("      因此本研究的定位是**可行性 + 信号生成**，不是确证性优效检验。")
    print()

    print("-" * 74)
    print("[3] 若按批次整群分配（每批 m=7 人；rho 为示例假设）")
    print("-" * 74)
    print(f"{'d':>5} {'rho':>6} {'设计效应':>10} {'群数/组':>10} {'人数/组':>10}")
    for d in (0.50, 0.60, 0.70):
        for rho in (0.05, 0.10):
            k = clusters_per_arm(d, 7, rho)
            print(f"{d:>5.2f} {rho:>6.2f} {1 + 6 * rho:>10.2f} {math.ceil(k):>10d} {math.ceil(k) * 7:>10d}")
    print("读法：每批只有 7 人时，即使 rho=0.05，设计效应也只有 1.30；")
    print("      表中“群数/组”是达到该功效所需的批次数——12–15 个批次远超实际可用的 7 个批次。")
    print("      也就是说，本设计的问题不是设计效应，而是**群数只有 7 个**（见 [3b] 与 [6]）。")
    print()

    print("-" * 74)
    print("[3b] 群数很少时（7 批次 × 7 人）有效样本量")
    print("-" * 74)
    print(f"{'群数/组':>8} {'每群人数':>8} {'rho':>6} {'设计效应':>10} {'有效n/组':>10} {'总人数/组':>10}")
    for k in (1, 2, 3, 4, 7):
        for rho in (0.05, 0.10, 0.20):
            deff = 1.0 + 6 * rho
            print(f"{k:>8d} {7:>8d} {rho:>6.2f} {deff:>10.2f} "
                  f"{cluster_effective_n(k, 7, rho):>10.1f} {k * 7:>10d}")
    print("读法：7 个批次全部用上、rho=0.20 时，全部 49 人的有效样本量只有约 22 人，")
    print("      而 cluster-robust 推断的自由度只由“群数”决定（G−2 = 5）。")
    print("      7 个群时常规 cluster-robust 标准误**向下偏倚**、置信区间过窄、P 值过小；")
    print("      必须使用 CR2 / Satterthwaite / wild cluster bootstrap 等小样本校正，")
    print("      且 wild cluster bootstrap 在 G=7、Rademacher 权重下只有 2^7=128 种符号组合，")
    print("      双侧 P 值不可能小于 2/128 = 0.0156。因此本设计只能作为**探索性**研究，")
    print("      报告 ICC 与群数，而不报告确证性组间 P 值（见 SAP §3.2）。")
    print()

    print("-" * 74)
    print("[4] ANCOVA 相对变化量检验的效率比 sqrt((1+rho)/2)（rho = 前后测相关）")
    print("-" * 74)
    for rho in (0.30, 0.50, 0.70):
        ratio = math.sqrt((1 + rho) / 2)
        print(f"rho={rho:.2f}  方差比={ratio ** 2:.3f}  n 可乘以 {ratio ** 2:.3f}"
              f"  （例：t修正 64/组 → {math.ceil(64 * ratio ** 2)}/组）")
    print()

    print("-" * 74)
    print("[4b] 以原始分标准差表达的效应量 → ANCOVA 规划用 d_adj = d_raw / sqrt(1-rho)")
    print("-" * 74)
    print(f"{'d_raw':>6} {'rho':>5} {'d_adj':>7} {'n/组(t修正)':>12} {'+15%脱落':>10}")
    for d_raw in (0.40, 0.50, 0.60):
        for rho in (0.30, 0.50, 0.70):
            d_adj = d_raw / math.sqrt(1 - rho**2)
            n = n_t(d_adj)
            print(f"{d_raw:>6.2f} {rho:>5.2f} {d_adj:>7.3f} {n:>12d} {math.ceil(n / 0.85):>10d}")
    print()

    print("-" * 74)
    print("[5] 合成演示数据为什么不能提供效应量（只读 demo_research/synthetic_v1）")
    print("-" * 74)
    root = Path(__file__).resolve().parents[2]
    path = root / "demo_research" / "synthetic_v1" / "data" / "assessments_SYNTHETIC.csv"
    if not path.exists():
        print(f"未找到 {path}（跳过，不影响以上计算）")
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    paired: dict[str, dict[str, float]] = {}
    for row in rows:
        paired.setdefault(row["study_id"], {})[row["timepoint"]] = float(row["independent_total"])
    gains: dict[str, list[float]] = {"CBL": [], "CLINPATH": []}
    group_of = {row["study_id"]: row["group"] for row in rows}
    for sid, tp in paired.items():
        if "T0" in tp and "T1" in tp:
            gains[group_of[sid]].append(tp["T1"] - tp["T0"])
    sd = {}
    for g in ("CBL", "CLINPATH"):
        xs = gains[g]
        mu = sum(xs) / len(xs)
        sd[g] = math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))
        print(f"{g:>9}: n={len(xs):>3d}  提升均值={mu:.2f}  提升标准差={sd[g]:.2f}")
    pooled = math.sqrt((sd["CBL"] ** 2 + sd["CLINPATH"] ** 2) / 2)
    diff = sum(gains["CLINPATH"]) / len(gains["CLINPATH"]) - sum(gains["CBL"]) / len(gains["CBL"])
    print(f"提升差 = {diff:.2f}   合并标准差 = {pooled:.2f}   折算 d = {diff / pooled:.2f}")
    print("说明：该 d 是生成脚本**预先设定**的（nominal 6 vs 18），是生成器参数，")
    print("      不是估计值，也不是本研究的预期效应。它只能证明统计流程可跑通，")
    print("      **禁止**用于任何样本量规划或功效陈述。")
    print()

    print("-" * 74)
    print("[6] 本研究实际规模：49 名见习学生 / 7 批次整群分配（3 批 vs 4 批）")
    print("-" * 74)
    batches, per_batch = 7, 7
    total = batches * per_batch
    print(f"主研究总体 = {batches} 批次 × {per_batch} 人 = {total} 名见习学生")
    print(f"（另有 21 名实习阶段学生为**独立扩展人群**，不并入主结局分析）")
    print()
    print("设计：7 个批次整群随机分配——预先固定 3 个批次入 ClinPath、4 个批次入常规 CBL，")
    print("      再随机选定'哪 3 个批次'入 ClinPath；合法分配数 = C(7,3) = 35 种。")
    print("      （申请人已否决任何批内拆分方案，本脚本不计算批内随机。）")
    print()

    k_small, k_large = 3, 4
    n_small = k_small * per_batch
    n_large = k_large * per_batch
    print(f"7 批次整群分配（3 批 vs 4 批）：")
    print(f"  名义人数 = {n_small} vs {n_large}（合计 {total}）")
    print(f"  以较小臂 n={n_small} 规划：80% 功效最小可检出 d = {mdd(n_small):.3f}（未计设计效应）")
    for d in (0.50, 0.60, 0.70, 0.80):
        print(f"    若真实 d={d:.2f} → 名义功效 {achieved_power(d, n_small):.3f}（未计设计效应）")
    for rho in (0.05, 0.10, 0.20):
        deff = 1.0 + (per_batch - 1) * rho
        eff = cluster_effective_n(batches, per_batch, rho)
        print(f"    rho={rho:.2f} → 设计效应 {deff:.2f}；全部 7 批的有效样本量 = {eff:.1f}"
              f"（名义 {total}）；每臂有效 n ≈ {eff / 2:.1f}")
    print(f"  组别效应的可用自由度：cluster-robust 约 G−2 = {batches - 2}（G = 批次数，不是学生数）")
    print(f"  t 分位数对比：t_(0.975, df=5) = {t_quantile(0.975, 5):.3f}，"
          f"是正态 1.960 的 {t_quantile(0.975, 5) / 1.959964:.2f} 倍")
    print(f"  wild cluster bootstrap（Rademacher 权重，G=7）符号组合数 = 2^7 = {2 ** 7}，")
    print(f"  双侧 P 值不可能小于 2/128 = {2 / 2 ** 7:.4f}")
    print(f"  精确随机化检验：全部合法分配数 = C(7,3) = {math.comb(7, 3)} 种（**可精确枚举**）")
    print(f"  P 值分辨率 1/35 = {1 / math.comb(7, 3):.4f}；最小双侧 P 取决于数据"
          f"（唯一最大 → 1/35，并列 → ≥ 2/35 = {2 / math.comb(7, 3):.4f}）")
    print(f"  → p < 0.05 仅当观察分配 |T| 唯一最大；仍为探索性信号（7 个群的固有信息上限）")
    print()
    print("结论：")
    print(f"  · 49 名学生按 7 批次整群分配为 3 批 vs 4 批（{n_small} vs {n_large} 人）；")
    print(f"    较小臂 {n_small} 人/组、未计设计效应时 80% 功效最小可检出 d = {mdd(n_small):.3f}，")
    print(f"    计入整群设计效应后更差；对 d=0.50 的名义功效仅 {achieved_power(0.50, n_small):.3f}。")
    print(f"  · 组别效应自由度由群数决定（G−2 = {batches - 2}）；精确检验 P 值分辨率 1/35（最小值取决于数据）；")
    print(f"    wild cluster bootstrap 双侧 P 下限为 2/128 ≈ 0.0156。")
    print(f"  · 若要以 80% 功效检出 d=0.50，需要 {n_t(0.50)} 人/组（合计 {2 * n_t(0.50)} 人），"
          f"是 49 人的 {2 * n_t(0.50) / total:.1f} 倍。")
    print(f"  · 因此本研究定位为**探索性 / 可行性研究**；确证性研究需要多中心或多届累积。")


if __name__ == "__main__":
    main()
