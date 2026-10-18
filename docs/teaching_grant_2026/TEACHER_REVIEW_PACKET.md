# 真实教师审核包 — 操作清单（TEACHER_REVIEW_PACKET）

> **本文件是给两位真实带教教师的使用说明，不是审核结论。**
> **包内没有任何内容被预先批准。** 所有病例卡、量表、模拟作答与合成数据
> 当前状态均为 `PENDING_REAL_REVIEW` / 未审核；`reviewer_name`、`review_date`、
> 分数栏一律为空。任何"已审核""已通过""专家认可"的说法在本轮都不成立。
>
> 本文件也不代表教学有效性证据。系统能跑通（见 `ACCEPTANCE_v2.md`）与
> 教学内容是否准确、是否适合本科见习，是两个独立问题；后者只能由真实教师回答。

适用对象：两位**真实、在岗**的临床带教教师（下称"教师 1""教师 2"）。
两人必须**独立**完成，不互相讨论，不查看对方结论。

> **第三轮更新（2026-10-18）**：真实教学条件已确认——每批 7 天、每批 7 名学生、共 7 批
> （49 名见习生）。本轮新增两项审核材料：
> - `A_cases/A04_assessment_quality_control.md`：两份**独立考核**病例的难度与覆盖对比、
>   T0/T1 题本顺序平衡建议、盲评工作量与裁决规则；
> - `A_cases/A04_difficulty_calibration_BLANK.csv`：难度校准空白表（4 行，教师填写）。
>
> 这两项与原有的病例审核（`A03_teacher_review_form_BLANK.csv`）一并完成。
> **研究设计已锁定为 7 批次整群分配**（申请人已确认教学组织条件不允许批内拆分，
> 见 `evidence/E5_protocol/T3_design_comparison.md`），教师无需就分组方式给出意见。

---

## 0. 一页速览

| 顺序 | 教师要做什么 | 读哪些文件 | 填哪些文件 | 交回后发生什么 |
| --- | --- | --- | --- | --- |
| 1 | 读 6 份病例卡 | `A01_*.md`（6 份） | 不填 | — |
| 2 | 读六维量表 | `B01_rubric_v0.1.md` | 不填 | — |
| 3 | 审核 6 个病例 | 同 1、2 | `A03_teacher_review_form_BLANK.csv`（或 `.md`） | 汇总；≤2 分进入修订 |
| 4 | 对量表给出意见并签字 | `B01_rubric_v0.1.md` §7 | 在 `B01` §7 签字（另存副本） | 权重/锚点确认或提出修改 |
| 5 | 盲评 16 份模拟作答 | `B02_sample_answers.md`、`B03_export_template.md` | `B03_rating_template.csv`（每人独立副本） | 合并后跑 `rubric_agreement.py` |
| 6 | （可选）看合成研究演示 | `/teacher/research-demo` 页面 | 不填 | 仅作技术演示，不作证据 |
| 7 | （可选）看平台实际运行 | `/teacher/dashboard` 等 | 不填 | 观摩意见另行记录 |

**顺序很重要**：必须先完成第 3 步（病例审核），再做第 5 步（盲评）。
若病例本身要改，基于旧病例的评分会作废。

---

## 1. 第 1 步 — 读病例卡（只读）

路径：`docs/teaching_grant_2026/workpackages/A_cases/`

| 文件 | 病例 | 类型 |
| --- | --- | --- |
| `A01_training_SLE.md` | CASE-T01 系统性红斑狼疮 | 训练 |
| `A01_training_RA.md` | CASE-T02 类风湿关节炎 | 训练 |
| `A01_training_AAV.md` | CASE-T03 ANCA 相关血管炎 | 训练 |
| `A01_training_IIM.md` | CASE-T04 特发性炎性肌病 | 训练 |
| `A01_assessment_UA.md` | CASE-A01 未分化关节炎 | 独立考核 |
| `A01_assessment_multisystem.md` | CASE-A02 成人 Still 病 | 独立考核 |
| `A01_case_index.md` | 六例索引与难度标定 | 参考 |

每份卡片含：学习目标、主诉/现病史/查体/检查、标准诊断、鉴别诊断、治疗原则、
六维评分要点，以及**「核对提示」**——即需要教师重点判断的争议点。

**教师要做的事**：逐份通读，记下错误、过时指南版本、超出本科范围的内容。
不要在卡片文件上直接改；意见写进第 3 步的审核表。

---

## 2. 第 2 步 — 读六维量表（只读）

路径：`docs/teaching_grant_2026/workpackages/B_rubric/B01_rubric_v0.1.md`

重点读：

- §2「与平台现有实现的关系」——**平台当前权重是 20/20/20/15/15/10，
  与量表 v0.1 的 10/20/25/15/20/10 不一致**。这是已知差异，不是笔误。
  教师需要决定：确认量表权重，还是按平台现状调整量表。
- §3 六个维度的定义与低/中/高三档锚点——锚点是否可观察、可评分。
- §4 加权总分公式与边界条件。
- §5「内部形成性评分 vs 独立研究主结局」——平台内评分不能当研究主结局。

---

## 3. 第 3 步 — 审核 6 个病例（要填）

填写文件（二选一，推荐 CSV，便于汇总）：

- `docs/teaching_grant_2026/workpackages/A_cases/A03_teacher_review_form_BLANK.csv`
- `docs/teaching_grant_2026/workpackages/A_cases/A03_teacher_review_form_BLANK.md`
  （同一张表的 Markdown 版，含填写说明）

**结构**：12 行 = 6 个病例 × 2 个教师槽位
（`REAL_TEACHER_1` / `REAL_TEACHER_2`）。每位教师只填自己槽位的 6 行。

**每行要填**：

| 列 | 怎么填 |
| --- | --- |
| `reviewer_name` | 本人真实姓名（或工号+姓名）。**不得由他人代填** |
| `review_date` | 实际审核日期 `YYYY-MM-DD` |
| `medical_accuracy_1to5` | 1–5 整数 |
| `undergraduate_fit_1to5` | 1–5 整数 |
| `difficulty_1to5` | 1–5 整数（3 = 与标定难度相符） |
| `rubric_clarity_1to5` | 1–5 整数 |
| `feedback` | 具体修改意见，尽量指到段落/句子 |
| `final_decision` | 由 `PENDING_REAL_REVIEW` 改为 `REVISE_AND_RESUBMIT` / `REJECT` / `ACCEPT_FOR_TEACHING` |
| `review_origin` | 由 `REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED` 改为 `REAL_HUMAN_REVIEW_CONDUCTED` |

不要修改 `case_id` 与 `reviewer_slot`。

**交回后发生什么**：

1. 协调人汇总两份表，**不改动**任何评分或结论。
2. 任一维度 ≤2 分的病例 → 进入修订队列；两位教师结论冲突 → 由第三位教师仲裁。
3. 修订后的病例**重新**进入审核，不复用旧结论。
4. 两份原始表归档为结题证据；只有它们能支撑"已审核"的表述。

---

## 4. 第 4 步 — 对量表签字（要填）

在 `B01_rubric_v0.1.md` §7「待办与签字」处，由教师本人写下：

- 是否确认六个维度与权重（10/20/25/15/20/10）；
- 是否确认三档行为锚点；
- 与平台权重差异如何处理（对齐平台 / 调整量表 / 暂不改）。

**做法**：复制该文件为 `B01_rubric_v0.1_SIGNED_<教师姓名>.md`，在副本末尾追加
签字段（姓名、日期、结论）。**不要覆盖原文件**，原始草案必须保留。

**交回后发生什么**：协调人比对两位教师意见；一致则更新 `STATUS_B.md` 的量表状态；
不一致则保留两套意见，提交项目负责人决定。平台权重是否修改是一个独立的代码变更，
需要单独评审与测试，不会因为签字而自动生效。

---

## 5. 第 5 步 — 盲评 16 份模拟作答（要填）

前置：第 3 步已完成，且相关病例未被判定为 `REJECT`。

要读的文件：

- `docs/teaching_grant_2026/workpackages/B_rubric/B02_sample_answers.md`
  （16 份作答，**不含任何分数**）
- `docs/teaching_grant_2026/workpackages/B_rubric/B03_export_template.md`
  （列定义、加权算法、自查清单）

要填的文件（**每人一份独立副本**）：

- `docs/teaching_grant_2026/workpackages/B_rubric/B03_rating_template.csv`
  （32 行 = 16 样本 × 2 个评分者槽位）

填写要点：

1. 先填六个维度分数（0–100），再按 `B01` §4.1 计算 `total`。
   **不要**填平台生成的 `total_score`——平台权重与量表不同。
2. `rater_id` 填匿名编号（如 `RATER-01`），**不要**填姓名、工号或邮箱。
3. `rater_origin` 保持 `REAL_BLINDED_RATER`。
4. 不要删除行；缺行会导致该样本在分析中被排除。
5. 盲法：评分时不要看另一位教师的文件，也不要在评分前查看任何 AI/规则分数。

**交回后发生什么**：

1. 协调人把两份文件合并（不修改分数），运行：
   `python3.11 scripts/grant/rubric_agreement.py <合并后的 csv>`
2. 该脚本在**没有真实评分**时会以退出码 2 结束且**不输出任何数字**——
   这是防止"用模拟数据冒充一致性"的护栏。
3. 分析结果（均值、加权总分、精确/±5/±10 一致性、ICC(2,1)、三档 kappa）
   写入 `B04_*`，作为量表信度证据。
4. 原始评分文件保留，不覆盖。

> 平台 `/teacher/score-review` 的「复核确认」**不是**盲评：教师能看到 AI/规则分数，
> 且确认结果会回写学生画像。它只能作为教学闭环记录，不能进入一致性分析。

---

## 6. 第 6 步（可选）— 看合成研究演示

页面：教师登录后访问 `/teacher/research-demo`（或在 `/teacher/research-export`
点击进入演示的入口）。

**必须理解**：页面顶部横幅写明
`合成教学研究演示｜虚拟学生、虚拟评分者｜不代表真实教学成效`。
60 名"学生"、效应量、P 值全部由生成器按预设注入，**不是真实教学结果**。
教师只需判断"这个演示能否用于向评审说明技术可行性"，不需要给分数。

相关只读文件（如需核对）：

- `demo_research/synthetic_v1/data/*_SYNTHETIC.csv`
- `demo_research/synthetic_v1/templates/expert_review_BLANK.csv`（专家审核表，保持空白）

> `expert_review_BLANK.csv` 属于**另一项**可选审核（对合成演示的专家意见）。
> 若教师愿意填写，请另存副本并注明"针对合成演示"，**不得**与第 3 步的真实病例审核混用。

---

## 7. 第 7 步（可选）— 平台观摩

若需要看系统实际运行，使用验证/演示环境，**不要**在生产库上做教学操作。
教师只需记录"哪个页面看得懂、哪个页面看不懂"，不需要给分。

---

## 8. 交回方式与归档

| 文件 | 交回给谁 | 归档位置 | 后续状态 |
| --- | --- | --- | --- |
| `A03_teacher_review_form_BLANK.csv`（教师 1、2 各一份） | 项目协调人 | `docs/teaching_grant_2026/evidence/E3_cases_rubric/` | 作为"真实审核"证据 |
| `B01_rubric_v0.1_SIGNED_<姓名>.md` | 项目协调人 | 同上 | 量表确认或修改依据 |
| `B03_rating_template.csv`（每人一份） | 项目协调人 | 同上 | 合并后交 `rubric_agreement.py` |
| 平台观摩意见（自由文本） | 项目协调人 | `C_workflow/` | 仅作观摩记录，非研究数据 |

**归档规则**：原始文件只增不改；任何修订另存并注明原因与日期。
未交回的文件保持 `PENDING_REAL_REVIEW`，**不会**被代填、代签或"补写"。

---

## 9. 明确声明

- 本审核包**不含**任何预填的教师姓名、签名、日期或审核结论。
- 本审核包**不构成**任何形式的预先批准。
- 在两位真实教师完整填写并签字之前：
  - 六份病例卡保持 `PENDING_REAL_REVIEW`；
  - 量表 v0.1 保持"草案"状态；
  - 不得在申报书中写"已完成两位带教教师审核"；
  - 不得把任何 AI 起草内容表述为教师意见。
- 合成数据的统计结果不得表述为真实教学效果。
