# 最终架构摘要（FINAL_DELIVERY / ARCHITECTURE）

> **权威来源是 `docs/ARCH.md`**（由牵头成员维护）；本文件是面向申报材料的摘要，两者冲突时以 `docs/ARCH.md` 为准。
> 本文件只陈述代码里已存在、可核查的结构，并明确哪些隔离性**已有测试证据**、哪些**尚待验收**。
> 快照：分支 `feat/clinpath-final-2026`，已提交基线 `47f7e6d`；他人的未提交修改不在本摘要内。

## 1. 三个逻辑域

```
Training（形成性训练）          Assessment（独立在线考核）         Research（教学研究管理）
Case / CaseSession / StudentAnswer  AssessmentForm(+Review)            StudyCohort / StudyAllocation
Score / TutorTurn                   AssessmentSitting                  整批随机化(35 种)·题本顺序 X/Y
CompetencyProfile                   AssessmentAnswer                   精确随机化检验·ICC·缺失·冻结
LearningRecommendation              AssessmentReview(双教师盲评)         受控导出（研究编码）
教师反馈与干预                       Adjudication / DatasetLock
        │                                   │                                  │
        └──── 共享：用户身份与基础信息 ──────┴────── 只读/受控关联 ─────────────────┘
```

| 域 | 作用 | 代码位置（已提交） |
| --- | --- | --- |
| Training | 五阶段推理、AI 追问（可规则降级并标记）、六维形成性评分、画像、推荐、教师干预 | `backend/app/models.py`、`routes/sessions.py`、`services/` |
| Assessment | 题本与双教师审核、考试编排、独立作答、匿名双评、裁决、锁定 | `backend/app/assessment_models.py`、`routes/assessments.py`、迁移 `20261018_08`（硬化迁移 `_09` 在他人未提交工作中） |
| Research | 整批随机化、精确随机化检验、ICC、批次统计、数据冻结（**纯函数，无 DB/网络/时钟**） | `backend/app/research/`（提交 `8de199b`） |

## 2. 必须成立的隔离（逐条标注证据状态）

| # | 约束 | 证据状态（以 `TEST_REPORT.md` 为准） |
| --- | --- | --- |
| I1 | 考核作答不进入训练 `CaseSession`/`Score`，也不更新 `CompetencyProfile`、不生成 `LearningRecommendation` | 需 Assessment 正向隔离测试通过后才可写「已验证」；旧 `xfail`（`test_7day_personalization_loop.py`）记录的是**普通训练路由**行为 |
| I2 | 考核访问不触发 AI 调用 | 同上 |
| I3 | 学生只能读取本人被分配且在开放窗口内的考试；只见当前阶段，不见答案/评分锚点 | 同上 |
| I4 | 评分者看不到姓名/学号/组别/批次/T0-T1，看不到另一位评分者分数 | 同上 |
| I5 | 研究分析只用研究编码；身份映射限制访问；合成数据与真实数据不混合（`MixedDataOriginError`） | 研究包有单元测试；DB 层接线待验收 |
| I6 | Assessment 最终成绩不回写形成性画像 | 同 I1 |
| I7 | 合成 Demo（60 名虚拟学生）独立只读，不写业务表 | `tests/test_demo_research.py`（已提交） |

## 3. 与既有不变量的关系

遵守 `AGENTS.md` 开发不变量：FastAPI 为权限最终裁决者；学生不得接收隐藏答案；AI 不可用时规则降级必须显式标记；
迁移前做带时间戳的 SQLite 备份；`next.config.ts` 的 `proxyTimeout` 不得为提速而缩短；
Assessment 域**不**调用 `ai_policy` 中的任何任务。

## 4. 已知限制（诚实记录）

1. 评分者若同时带教该批，系统**不能**自动宣称真正盲法；须记录风险并由研究负责人安排独立人员。
2. 学生自行写入答案的身份信息不会被自动视为已匿名化。
3. 题本审核中的「两位教师批准」是账号层面的声明；**真实审核与签字**需单位流程证明，管理员点击不能伪造。
4. 评分量表权重（10/20/25/15/20/10）是待教师确认的研究量表，不覆盖平台形成性权重（20/20/20/15/15/10）。
