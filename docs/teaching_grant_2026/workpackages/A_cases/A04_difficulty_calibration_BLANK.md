# A04 难度校准表（空白）填写说明

> **本表为空白模板，尚未由任何真实教师填写。** `reviewer_name` 与 `review_date` 为空；
> `final_approval` 保持 `PENDING_REAL_REVIEW`。请勿预填、代签或事后补写审核人姓名与日期。
>
> - 配套 CSV：`A04_difficulty_calibration_BLANK.csv`（4 行 = 2 例 × 2 位教师）
> - 用途：为 `A04_assessment_quality_control.md` §1 的难度比较提供**教师实测校准**，
>   并据以判断是否接受两例当前难度差（研究采用 **7 批次整群分配**，题本顺序 X/Y 在
>   **批内**随机平衡，见 `A04_assessment_quality_control.md` §2）
> - 前置阅读：`A04_assessment_quality_control.md`（两例难度与覆盖比较、整批分配下的题本顺序平衡、考核访问隔离）

## 一、目的

由两位真实教师**独立**给出两份独立考核病例（CASE-A01 未分化多关节炎、CASE-A02 成人 Still 病伴 MAS 风险）的难度与本科见习适用性判断，用于：

1. 确认两例是否**难度可比**，并判断是否接受当前难度差（A02 更难）——该难度差在整批分配下由**批内题本顺序平衡**（`A04` §2.3）抵消，故请结合该设计给出是否可接受；
2. 校准 §1.1 表中 AI 估计的"预计作答时间"与"推理步骤数"；
3. 记录教师对"最难步骤"与"建议修改"的具体意见。

**AI 只负责起草与估计，不参与校准结论。** 结论必须由真实教师独立作出。

## 二、填写说明（逐列）

| 列名 | 填写要求 |
| --- | --- |
| `case_id` | 已预填（CASE-A01 / CASE-A02），请勿修改 |
| `reviewer_slot` | 已预填 `REAL_TEACHER_1` / `REAL_TEACHER_2`，请勿修改 |
| `reviewer_name` | 由教师本人填写真实姓名（或工号+姓名），**不得由他人代填**；空白表示尚未审核 |
| `review_date` | 实际审核日期（YYYY-MM-DD）；空白表示尚未审核 |
| `expected_difficulty_1to5` | 1–5 整数：您认为该病例对本科见习学生的难度。1=过易，3=与标定难度相符，5=过难 |
| `actual_undergraduate_fit_1to5` | 1–5 整数：该病例与本科见习（第 2–3 阶段）的**契合度**。1=明显超出范围，5=完全适合 |
| `information_completeness_1to5` | 1–5 整数：病例信息是否足够支持作答。1=明显不足，5=充分 |
| `reasoning_steps_required` | 整数：您认为学生完成本题需要的**主要推理步骤数**（用于与 §1.1 的 5 步 / 6–7 步比较） |
| `estimated_minutes` | 整数：您估计本科见习学生的**作答分钟数** |
| `hardest_step` | 文本：您认为最难的步骤（如"分类标准计分""排除感染与肿瘤""MAS 识别"） |
| `recommended_change` | 文本：具体修改建议（可指出具体段落与句子）；若无需修改写"无" |
| `accept_difficulty_gap` | 取值 `是` / `否`（或 `Y` / `N`）：在**整批分配 + 批内题本顺序平衡**（`A04` §2）下，您是否接受 CASE-A02 明显难于 CASE-A01 的当前难度差。填"否"请在 `recommended_change` 写明应如何平衡（对应 `A04` §1.3 的选项 1 / 2） |
| `final_approval` | 默认保持 `PENDING_REAL_REVIEW`；审核后由教师改为 `APPROVE` / `REVISE` / `REJECT`（按教研室约定的取值） |

## 三、评分刻度（1–5）

| 分值 | 含义 |
| --- | --- |
| 5 | 优秀 / 完全符合 |
| 4 | 良好，需少量文字修改 |
| 3 | 合格，需局部修订 |
| 2 | 不足，需较大修订 |
| 1 | 不合格 / 明显超出本科见习范围 |

## 四、空白表（Markdown 版，4 行）

| case_id | reviewer_slot | reviewer_name | review_date | expected_difficulty_1to5 | actual_undergraduate_fit_1to5 | information_completeness_1to5 | reasoning_steps_required | estimated_minutes | hardest_step | recommended_change | accept_difficulty_gap | final_approval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CASE-A01 | REAL_TEACHER_1 |  |  |  |  |  |  |  |  |  |  | PENDING_REAL_REVIEW |
| CASE-A01 | REAL_TEACHER_2 |  |  |  |  |  |  |  |  |  |  | PENDING_REAL_REVIEW |
| CASE-A02 | REAL_TEACHER_1 |  |  |  |  |  |  |  |  |  |  | PENDING_REAL_REVIEW |
| CASE-A02 | REAL_TEACHER_2 |  |  |  |  |  |  |  |  |  |  | PENDING_REAL_REVIEW |

## 五、填写后如何处理

1. 两位教师各自独立填写，**互不参考**对方答案（保持独立判断）。
2. 填写完成后，对照 `A04_assessment_quality_control.md` §1.1 的 AI 估计，逐维比较：
   - 若两位教师都接受当前难度差（`accept_difficulty_gap` 均为 `是`）→ 按 §1.3 选项 3（不改病例）执行；两例难度差由 §2.3 的**批内题本顺序平衡**在批内、臂间、批次间抵消。
   - 若两位教师都认为"A02 明显更难且需要平衡"（`accept_difficulty_gap` 均为 `否`）→ 从 §1.3 选项 1 / 2 中择一，并由教师写明具体改法。
   - 若两位教师意见不一致 → 由第三位教师（或教研室）裁定。
3. 本表**不产生**任何 `REVIEWED_BY_REAL_TEACHER` / `APPROVED_FOR_TEACHING` 状态；病例卡在两名教师完成审核并签字前保持 `PENDING_REAL_REVIEW`。**正式考核的开放还须满足 `A04` §3.5 的两项前置条件（教师审核 + 考核访问隔离实测验证）。**
