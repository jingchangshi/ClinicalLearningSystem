# 统计分析计划（STATISTICAL_ANALYSIS_PLAN）

> **本文件只引用，不定义。** 统计分析计划的唯一正文是
> `../evidence/E5_protocol/E5_02_SAP_statistical_analysis_plan.md`，由研究统计负责人维护；
> 统计量、随机化机制与**双侧 P 值定义**以该文件为准，本文件不得改写、不得并列第二种定义。
> 数据字典：`../workpackages/DATA_DICTIONARY.md`。纯函数实现：`backend/app/research/`
> （`exact_permutation.py`、`randomization.py`、`agreement.py`、`cohort_stats.py`、`dataset_export.py`、`order_balance.py`）。

## 申报材料引用 SAP 时的口径（供写作核对）

1. 研究是**探索性 / 可行性**研究；49 人、7 个批次不支持确证性优效推断。
2. 精确随机化检验枚举 35 种整批分配，P 值取 `k/35`；**不得无条件宣称最小双侧 P 为 2/35**，
   最小值取决于数据（SAP §3.5 给出定义、条件与固定算例）。
3. 不得用合成 Demo 中预设的组间差异计算真实研究的预期效应。
4. 评分者一致性（ICC）样本不足时如实提示，不伪造可靠性指标。

## 一致性检查

`python3 scripts/grant/check_protocol_consistency.py` 机械检查各现行文档不出现与 SAP 冲突的 P 值表述
（无条件的 2/35、另一种 2×min 定义、「α=0.05 不可达」的无条件说法）。
