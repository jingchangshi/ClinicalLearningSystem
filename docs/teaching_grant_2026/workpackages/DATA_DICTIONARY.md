# 研究数据字典（R4.6，冻结数据集）

> 状态：随终稿轮实现，列定义由 `backend/app/research/dataset_export.py::COLUMNS` 强制；
> 本文与该常量必须一致（`backend/tests/test_research_agreement_stats.py` 校验列头顺序）。
> 研究分析只使用**编码数据**；学生真实身份映射表另行存放、限制访问，**不出现在任何导出中**。

> R9 修订：`assessment_form_id` 与题本槽位编码曾被混为一谈——导出写入题本记录 id，
> 而冻结校验按 `A01`/`A02` 槽位比较，导致真实题本 id 不是 1/2 时冻结链路必然失败。
> 现拆分为两列：`assessment_form_id`（记录 id，可追溯）与 `assessment_form_slot`
> （`A01`/`A02` 槽位，**冻结顺序校验的唯一依据**）。

## 1. 粒度与冻结

- 一行 = 一名学生 × 一个时间点（T0 或 T1）；排序键 `(study_student_code, timepoint)`。
- 导出为规范 CSV（UTF-8，`\n` 换行，固定列序，空值为空串）；`dataset_version` 写入每一行，
  整份 CSV 的 SHA-256（`content_sha256`）与 `dataset_version`、`data_origin`、行数一起记入冻结清单。
  相同数据 + 相同版本必产出相同字节；清单中的哈希不符即视为被改动。
- 同一 `dataset_version` 不得重新生成；数据有变须发新版本。
- 行内 `data_origin` 必须与数据集一致；**混合来源被拒绝**。

## 2. 列

| 列 | 类型 | 取值 / 含义 |
| --- | --- | --- |
| `study_student_code` | 文本 | 研究编码（非真实学号/姓名） |
| `cohort_id` | 文本 | 批次编码（7 个完整轮转批次之一，分析单位） |
| `batch_index` | 整数 1–7 | 批次**实际时间顺序**（必填）。第 b 批前有 7(b−1) 名已考完两份题本的学生，用于「题本信息外泄/批次顺序」敏感性分析 |
| `study_group` | 枚举 | `clinpath` / `cbl`；来自冻结的整批随机化记录 |
| `randomization_version` | 文本 | 随机化记录版本（含算法、种子、执行人、时间、方案版本的那条记录） |
| `timepoint` | 枚举 | `T0`（D1 基线）/ `T1`（D6 后测） |
| `assessment_form_id` | 整数 | 题本**记录 id**（数据库主键）。这是本地标识，用于回溯到具体题本记录；**不得**与题本槽位编码比较 |
| `assessment_form_slot` | 枚举 | 该次考核实际使用的**题本槽位** `A01` / `A02`，必须与 `form_order` 和 `timepoint` 一致（`X`：T0=A01, T1=A02；`Y`：T0=A02, T1=A01）。**冻结 CSV 的题本顺序校验以此列为准**，缺失即拒绝 |
| `assessment_form_version` | 文本 | 所用题本版本 |
| `form_order` | 枚举 | `X`：T0=A01, T1=A02；`Y`：T0=A02, T1=A01（组内约 4/3，先于组别抽签冻结） |
| `blinded_rater_1_score` | 数值或空 | 盲评教师 1 的总分（对组别、时间点盲） |
| `blinded_rater_2_score` | 数值或空 | 盲评教师 2 的总分 |
| `adjudicated_score` | 数值或空 | 分歧触发后的裁决分；无分歧为空 |
| `final_score` | 数值或空 | 最终成绩（锁定后）；缺失须有 `missingness` 理由 |
| `assessment_completed_at` | ISO-8601 或空 | 考核完成时间 |
| `training_exposure` | 文本/数值 | 训练暴露（ClinPath 组：D2–D5 完成的形成性训练量；CBL 组：常规教学接触记录） |
| `cbl_case_topics` | 文本 | CBL 组实际教学的病例主题清单（`;` 分隔；**CBL 组必须记录**，空值由 `cbl_rows_missing_topics` 列出，用于核对 CBL 病例是否与考核题本主题重合；ClinPath 组留空） |
| `intervention_count` | 整数 | 教师干预次数 |
| `missingness` | 文本 | `observed`，或缺失原因（如 `absent`、`withdrawn`、`incomplete`） |
| `scoring_provenance` | 文本 | 分数来源链（评分者/裁决/规则或 AI 的 `degraded` 标记等），不含提示词与回答正文 |
| `dataset_version` | 文本 | 冻结数据集版本 |
| `data_origin` | 枚举 | `real_study`（真实研究）/ `synthetic_demo`（合成演示）/ `pilot_test`（预试）；**三者永不混合** |

## 3. 使用约束

- `synthetic_demo` 与 `pilot_test` 数据**不得**用于计算真实研究的预期效应（`real_study_expected_effect` 拒绝）。
- `quasi_experimental` 分配的数据集不得产出随机化检验结论（`exact_randomization_test` 拒绝）。
- 评分者一致性（ICC(2,1)、ICC(2,k) 及 95% CI）由两位盲评分数计算；完整配对不足 10 个受试者时
  输出 `insufficient_data` 且**不给数值**。
- 批次顺序与同批次同题本暴露（`cohort_stats.batch_exposure_sensitivity`）仅作探索性敏感性分析，只给描述性量，不给 P 值。
- 主分析单位为批次；P 值定义见 SAP `E5_02` §3.5.3（全项目唯一一种）。
