# CASE-A01 / CASE-A02 难度匹配表

> **状态：`PENDING_REAL_REVIEW`　review_origin：`REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED`**。“AI 估计”列为“AI technical/medical DRAFT re-check（非真实教师审定）”，**未经任何真实校准**；“字符数”列由载荷直接计数，可复核。教师栏必须由两位真实教师独立填写。

## 1. 审核人

**REAL_TEACHER_1**（请审核教师本人填写；不得由他人代填）

| 项 | 内容 |
| --- | --- |
| 姓名 / 工号 | |
| 职称 / 单位 | |
| 是否参与过本病例起草或本批次学生带教（利益冲突） | ☐ 否　☐ 是，说明： |
| 声明：本人独立完成审核，未参考另一位教师的意见 | ☐ 已确认 |
| 审核日期（YYYY-MM-DD） | ____-__-__ |
| 签字 | |

**REAL_TEACHER_2**（请审核教师本人填写；不得由他人代填）

| 项 | 内容 |
| --- | --- |
| 姓名 / 工号 | |
| 职称 / 单位 | |
| 是否参与过本病例起草或本批次学生带教（利益冲突） | ☐ 否　☐ 是，说明： |
| 声明：本人独立完成审核，未参考另一位教师的意见 | ☐ 已确认 |
| 审核日期（YYYY-MM-DD） | ____-__-__ |
| 签字 | |

## 2. 逐属性比较（AI 估计 vs 教师判断）

| 属性 | CASE-A01（未分化多关节炎） | CASE-A02（持续性干燥症状待查） | 可比性（AI 估计） | 教师1 判断 | 教师2 判断 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 阶段数 / 结构 | 5（S1–S5，同结构） | 5（S1–S5，同结构） | 相同 | | | PENDING_REAL_REVIEW |
| 学生可见 clinical_information 总字符数（载荷计数） | 604 | 636 | A02 信息量更大 | | | PENDING_REAL_REVIEW |
| 学生可见 question 总字符数（载荷计数） | 222 | 218 | 相近 | | | PENDING_REAL_REVIEW |
| 主要推理步骤（AI 估计） | 约 7：关节计数/炎性判断、入口条件、初诊计分、≥6 个鉴别、检查优先级与安全筛查、随访重新计分、重新分类触发条件 | 约 7：入口与排除条件、客观证据识别、非免疫原因排查、鉴别、2016 计分与未评估项、血清阴性解释与活检指征、对症管理与随访 | 相近 | | | PENDING_REAL_REVIEW |
| 算术/计分负担 | 高：2010 标准在两个时点各计分一次（四项求和） | 中：2016 五项计分，多项“未评估” | A01 更机械 | | | PENDING_REAL_REVIEW |
| 开放性/不确定性 | 中：结论为“未分化+随访” | 高：结论为“不能确诊+决定性检查为活检”，对“万能不确定”答案更脆弱 | A02 评分变异风险更高 | | | PENDING_REAL_REVIEW |
| 所需背景知识 | 关节炎鉴别、2010 RA 标准、早期关节炎管理 | 干眼/口干病因、2016 SjD 标准、唇腺活检、自身抗体局限 | 领域不同，难比较 | | | PENDING_REAL_REVIEW |
| 与训练病例的构念重叠 | 与 CASE-T02（RA）共用 2010 标准计分框架 | 与训练库无同病种内容；与 A01 共享“勿过度诊断+随访”元模式 | 见泄漏审计 | | | PENDING_REAL_REVIEW |
| 预计作答时间（AI 估计，未校准） | 45–60 分钟 | 45–60 分钟 | 相同（假设） | | | PENDING_REAL_REVIEW |
| 评分者一致性风险（AI 估计） | 中低：计分可核对 | 中：依赖对不确定性与优先级的判断 | A02 更高 | | | PENDING_REAL_REVIEW |

## 3. 教师逐例判断（同 A04 空白表字段）

| case_id | reviewer_slot | expected_difficulty_1to5 | actual_undergraduate_fit_1to5 | information_completeness_1to5 | reasoning_steps_required | estimated_minutes | hardest_step | recommended_change | accept_difficulty_gap（是/否） | final_approval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CASE-A01 | REAL_TEACHER_1 | | | | | | | | | PENDING_REAL_REVIEW |
| CASE-A01 | REAL_TEACHER_2 | | | | | | | | | PENDING_REAL_REVIEW |
| CASE-A02 | REAL_TEACHER_1 | | | | | | | | | PENDING_REAL_REVIEW |
| CASE-A02 | REAL_TEACHER_2 | | | | | | | | | PENDING_REAL_REVIEW |

## 4. 顺序与传播相关问题（教师请判断）

| ID | 问题 | 教师1 | 教师2 | 状态 |
| --- | --- | --- | --- | --- |
| M-01 | 若两例难度不等，X/Y 批内交叉（各约 4/3 人）能否使“组别×时点”估计不被题本难度混杂？是否需要在分析中以题本为协变量 | | | PENDING_REAL_REVIEW |
| M-02 | 是否接受两例预计作答时间相同并统一开放窗口；若不同，应分别设为多少分钟 | | | PENDING_REAL_REVIEW |
| M-03 | 是否需要在正式研究前对 A01/A02 做小规模试答（非研究对象的学生/住院医）以校准难度；试答数据不得并入研究数据 | | | PENDING_REAL_REVIEW |
| M-04 | A01 的“高算术负担”与 A02 的“高开放性”是否对不同能力学生有利（例如强于计算者 vs 强于综合者） | | | PENDING_REAL_REVIEW |

## 5. 声明

- 本表不含任何真实教师姓名、签名或日期；AI 估计不构成难度校准结论。
- 两例是否“难度可比”必须由两位真实教师判断；在此之前不得宣称题本等难。
