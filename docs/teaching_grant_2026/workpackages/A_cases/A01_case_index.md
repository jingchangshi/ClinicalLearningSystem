# A01 病例索引（教学病例卡总表）

> 全部六份病例卡均为 AI 辅助起草的**草稿**，审核状态统一为 `PENDING_REAL_REVIEW`。在两名真实教师完成审核并签字前，任何一份都不得用于正式教学或独立考核，也不得计入学生成绩。

## 病例总表

| 病例编号 | 类型 | 学段（平台五阶段） | 疾病 | 难度 | 审核状态 | 文件 |
| --- | --- | --- | --- | --- | --- | --- |
| CASE-T01 | 训练病例 | 第1–2阶段：关键信息提取 / 初步诊断及依据 | 系统性红斑狼疮（疑伴狼疮肾炎） | 基础 | PENDING_REAL_REVIEW | `A01_training_SLE.md` |
| CASE-T02 | 训练病例 | 第1–2阶段：关键信息提取 / 初步诊断及依据 | 类风湿关节炎（早期活动期） | 基础 | PENDING_REAL_REVIEW | `A01_training_RA.md` |
| CASE-T03 | 训练病例 | 第2–3阶段：初步诊断及依据 / 鉴别诊断 / 临床决策入门 | ANCA 相关性血管炎（GPA 倾向，肺肾受累） | 进阶 | PENDING_REAL_REVIEW | `A01_training_AAV.md` |
| CASE-T04 | 训练病例 | 第2–3阶段：初步诊断及依据 / 鉴别诊断 / 检查策略 | 炎性肌病（抗合成酶综合征伴 ILD） | 进阶 | PENDING_REAL_REVIEW | `A01_training_IIM.md` |
| CASE-A01 | 独立考核病例 | 第2–3阶段：鉴别诊断 / 进一步检查 | 未分化多关节炎 | 中等 | PENDING_REAL_REVIEW | `A01_assessment_UA.md` |
| CASE-A02 | 独立考核病例 | 第3阶段：鉴别诊断 / 临床决策入门 | 干燥症状待查（疑似原发性干燥综合征，未确诊） | 中等（待专家校准） | PENDING_REAL_REVIEW | `A01_assessment_multisystem.md` |

## 训练 / 考核隔离

| 项目 | 说明 |
| --- | --- |
| 训练病例 | CASE-T01～CASE-T04，仅用于形成性训练，不进入独立考核题库 |
| 独立考核病例 | CASE-A01、CASE-A02，考核前不得向学生发放卡片内容，不得在训练环节复用 |
| 疾病不重叠 | 六个病例的主诊断互不相同：SLE / RA / AAV / IIM / UA / 干燥症状待查 |
| 考核与训练的关系 | 两套独立题本不属于四份训练病例；必须排查平台全部可见教材和已有病例是否出现同一题本答案模式 |
| 平台支持情况 | 平台 `Case` 表目前**没有** `assessment_only` / `review_status` 字段，训练/考核隔离目前只靠本目录文档与教师发放流程保证（见 `A02_platform_schema_notes.md`） |

## 六维评分权重（六份卡片一致）

| 维度 | 键 | 权重 |
| --- | --- | --- |
| 医学知识 | medical_knowledge | 10 |
| 关键信息提取 | key_information | 20 |
| 鉴别诊断 | differential_diagnosis | 25 |
| 证据整合 | evidence_integration | 15 |
| 临床决策 | clinical_decision | 20 |
| 循证安全 | evidence_based_medicine | 10 |
| **合计** | | **100** |

> 注意：平台 `backend/app/services/scoring_llm.py` 的规则评分权重为 20/20/20/15/15/10，与本工作包的 10/20/25/15/20/10 **不一致**。本工作包按任务书要求采用后者；平台权重是否需要调整属于平台侧决策，本工作包不改动代码（见 `A02_platform_schema_notes.md` 的“差异”一节）。

## 审核状态说明

| 状态值 | 含义 | 当前 |
| --- | --- | --- |
| `DRAFT_AI` | AI 起草，尚未送审 | 否（本工作包已直接标记为待审） |
| `PENDING_REAL_REVIEW` | 已起草，等待两名真实教师审核 | **是（全部六份）** |
| `REVIEWED_BY_REAL_TEACHER` | 两名真实教师已完成审核并签字 | 否 |
| `APPROVED_FOR_TEACHING` | 经教学管理部门批准可用于教学 | 否 |

本工作包**不产生**任何 `REVIEWED_BY_REAL_TEACHER` 或 `APPROVED_FOR_TEACHING` 状态。

## 文件清单

| 文件 | 用途 |
| --- | --- |
| `A01_training_SLE.md` | 训练病例 CASE-T01 |
| `A01_training_RA.md` | 训练病例 CASE-T02 |
| `A01_training_AAV.md` | 训练病例 CASE-T03 |
| `A01_training_IIM.md` | 训练病例 CASE-T04 |
| `A01_assessment_UA.md` | 独立考核病例 CASE-A01 |
| `A01_assessment_multisystem.md` | 独立考核病例 CASE-A02 |
| `A01_case_index.md` | 本文件 |
| `A02_platform_schema_notes.md` | 平台 schema 映射与限制说明 |
| `A03_teacher_review_form_BLANK.md` | 教师审核表（Markdown 空白模板） |
| `A03_teacher_review_form_BLANK.csv` | 教师审核表（CSV，12 行） |
| `A04_platform_path_status.md` | CASE-T01 的平台路径状态说明 |
| `A04_CASE-T01_payload.json` | CASE-T01 的 `POST /api/teacher/cases` 干跑载荷（**未执行**） |
| `STATUS_A.md` | 本工作包状态报告 |
| `../../../../scripts/grant/check_case_cards.py` | 只读校验脚本（位于仓库 `scripts/grant/`） |
