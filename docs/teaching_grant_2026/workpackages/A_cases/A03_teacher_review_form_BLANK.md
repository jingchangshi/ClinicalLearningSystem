# A03 真实教师审核表（空白模板）

> **本表为空白模板，尚未由任何真实教师填写。** 所有审核结论保持 `PENDING_REAL_REVIEW`；`reviewer_name` 与 `review_date` 为空；`review_origin` 为 `REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED`（真实人工审核尚未进行）。请勿预填、代签或事后补写审核人姓名与日期。
>
> 配套 CSV：`A03_teacher_review_form_BLANK.csv`（12 行 = 6 例 × 2 位审核教师）。

## 一、审核目的

对 A01 的六份病例卡（CASE-T01～T04 训练病例，CASE-A01～A02 独立考核病例）进行**真实教师人工审核**，确认：

1. 医学准确性（诊断逻辑、鉴别诊断、危险信号、检查与治疗原则是否符合当前指南与临床实践）。
2. 本科见习适用性（是否超出本科临床见习学生的知识与能力范围）。
3. 难度标定是否合理。
4. 评分要点（六维量规）是否清晰、可观察、可评分。
5. 是否同意在修订后用于教学或独立考核。

**AI 只负责起草，不参与审核结论。** 审核结论必须由真实教师独立作出。

## 二、填写说明

| 字段 | 填写要求 |
| --- | --- |
| `case_id` | 已预填，请勿修改 |
| `reviewer_slot` | 已预填 `REAL_TEACHER_1` / `REAL_TEACHER_2`，请勿修改 |
| `reviewer_name` | 由审核教师本人填写真实姓名（或工号+姓名），**不得由他人代填** |
| `review_date` | 填写实际审核日期（YYYY-MM-DD） |
| `medical_accuracy_1to5` | 1–5 整数：1=存在明显医学错误，5=完全符合指南与临床实践 |
| `undergraduate_fit_1to5` | 1–5 整数：1=明显超出本科见习范围，5=完全适合本科见习 |
| `difficulty_1to5` | 1–5 整数：1=过易，5=过难；3 表示与标定难度相符 |
| `rubric_clarity_1to5` | 1–5 整数：1=评分要点无法操作，5=清晰可评分 |
| `feedback` | 具体修改意见（可指出具体段落与句子） |
| `final_decision` | 默认 `PENDING_REAL_REVIEW`；审核后可选 `REVISE_AND_RESUBMIT` / `REJECT` / `ACCEPT_FOR_TEACHING`（由教师填写） |
| `review_origin` | 保持 `REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED`，直到真实人工审核实际发生；审核完成后由审核教师改为 `REAL_HUMAN_REVIEW_CONDUCTED` |

**评分刻度**

| 分值 | 含义 |
| --- | --- |
| 5 | 优秀，无需修改 |
| 4 | 良好，需少量文字修改 |
| 3 | 合格，需局部修订 |
| 2 | 不足，需较大修订 |
| 1 | 不合格，需重写 |

## 三、审核表（Markdown 版，12 行）

| case_id | reviewer_slot | reviewer_name | review_date | medical_accuracy_1to5 | undergraduate_fit_1to5 | difficulty_1to5 | rubric_clarity_1to5 | feedback | final_decision | review_origin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CASE-T01 | REAL_TEACHER_1 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-T01 | REAL_TEACHER_2 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-T02 | REAL_TEACHER_1 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-T02 | REAL_TEACHER_2 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-T03 | REAL_TEACHER_1 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-T03 | REAL_TEACHER_2 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-T04 | REAL_TEACHER_1 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-T04 | REAL_TEACHER_2 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-A01 | REAL_TEACHER_1 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-A01 | REAL_TEACHER_2 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-A02 | REAL_TEACHER_1 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |
| CASE-A02 | REAL_TEACHER_2 |  |  |  |  |  |  |  | PENDING_REAL_REVIEW | REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED |

## 四、审核教师需重点核对的事项（与各卡片的 `核对提示` 对应）

| 病例 | 重点核对 |
| --- | --- |
| CASE-T01 | 2019 EULAR/ACR SLE 分类标准的计分表述；EULAR SLE 管理推荐使用 2019 版还是 2023 版；狼疮肾炎分型与肾活检指征的表述 |
| CASE-T02 | 2010 ACR/EULAR RA 分类标准计分（本病例 8 分）是否准确；EULAR RA 管理推荐使用 2019 还是 2022 版；达标治疗目标表述 |
| CASE-T03 | 2022 ACR/EULAR AAV 三份分类标准的前提条件表述；EULAR/ERA-EDTA 推荐版本；KDIGO 指南版本 |
| CASE-T04 | 2017 EULAR/ACR IIM 分类标准与 2017/2023 管理推荐的版本；抗合成酶综合征与抗 MDA5 的表述；肿瘤筛查建议 |
| CASE-A01 | “未分化关节炎”的病程界定；本病例按 RA 计分可达 7 分但临床倾向未分化的表述是否可接受；EULAR 早期关节炎推荐版本 |
| CASE-A02 | Yamaguchi 标准的条目表述；EULAR/ACR AOSD 管理推荐是否真实存在（若不存在请删除该条引用）；HLH-2004 方案的引用深度 |

## 五、审核流程建议

1. 将六份卡片与两张空白审核表（Markdown + CSV）分别发给两位真实教师。
2. 两位教师**独立**填写，不互相讨论，不参考对方结论。
3. 收回后统计：任一维度 ≤2 分的卡片进入修订；两位教师结论冲突时由第三位教师仲裁。
4. 修订完成后，`final_decision` 由审核教师重新填写；`review_origin` 改为 `REAL_HUMAN_REVIEW_CONDUCTED`。
5. 审核记录原件归档，作为结题证据。

## 六、声明

- 本表**不含**任何真实教师姓名、签名或日期。
- 本表**不代表**任何病例已通过审核。
- 在本表被两位真实教师完整填写并签字之前，六份病例卡的审核状态保持 `PENDING_REAL_REVIEW`。
