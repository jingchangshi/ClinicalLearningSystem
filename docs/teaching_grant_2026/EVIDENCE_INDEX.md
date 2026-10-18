# 证据索引（EVIDENCE_INDEX）

> 本文件把每一条可用于申报的材料对应到**实际文件路径 + 生成时间 + 来源类别 + 审核责任人 + 审核状态**。
> 任何没有真实人员签署的条目，状态只能是 `待真实审核`。
> 模拟数据一律标注 `SYNTHETIC_DEMO_NOT_REAL_STUDENTS`；模拟评分者标注 `SIMULATED_NOT_HUMAN`。

来源类别：
- `SYNTHETIC` — 合成演示数据，不可作为教学效果证据
- `PLATFORM_EVIDENCE` — 当前系统实际可运行功能（可复查 SHA）
- `DRAFT_PENDING_REVIEW` — Agent 起草，等待真实教师审核
- `REAL_PENDING` — 必须由用户/真实教师/院系提供，尚未收到

| 条目ID | 内容 | 来源类别 | 文件路径 | 生成时间 | 代码 SHA | 负责人 | 审核状态 | 可用于申报书的准确句子 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E-D-01 | 合成研究演示数据层 | SYNTHETIC | `demo_research/synthetic_v1/` | 2026-10-18 | 见下方"生成基线" | 项目组（技术） | 不适用（合成） | "已依托平台构建 60 名虚拟学生的合成研究数据集" |
| E-D-02 | 合成研究演示页面 | SYNTHETIC + PLATFORM_EVIDENCE | `/teacher/research-demo`；截图 `docs/teaching_grant_2026/workpackages/D_research_demo/D01_screenshots/` | 2026-10-18 | 见"生成基线" | 项目组（技术） | 不适用（合成） | "平台具备研究数据采集、导出与统计复现的演示能力" |
| E-D-03 | 统计可复现性 | SYNTHETIC | `backend/tests/test_demo_research.py`；`backend/app/services/demo_research.py` | 2026-10-18 | 见"生成基线" | 项目组（技术） | 测试通过 | "模拟统计结果可由同源数据逐项复算，并与离线工作簿一致" |
| E-D-04 | 页面与真实数据的隔离证明 | PLATFORM_EVIDENCE | `tests/test_demo_research.py::test_demo_router_never_touches_the_database` | 2026-10-18 | 见"生成基线" | 项目组（技术） | 测试通过 | "合成演示不写入任何业务表，调用前后业务表行数不变" |
| E-D-05 | 真实研究导出页（对照） | PLATFORM_EVIDENCE | `/teacher/research-export`；截图 `.../06_real_export_separation.png` | 2026-10-18 | 见"生成基线" | 项目组（技术） | 可复查 | "平台已具备匿名化学习证据导出功能" |
| E-R2-01 | 病例医学一致性修订 | DRAFT_PENDING_REVIEW | `workpackages/A_cases/MEDICAL_REVIEW_ISSUES_v1.md` + 三份已修订病例卡 | 2026-10-18（第二轮） | 见"生成基线" | AI 自查 | **待真实教师确认**；12 个待裁定问题见该文件第三节 | "病例卡已完成内部一致性自查与计分复核" |
| E-R2-02 | 评分来源区分 | PLATFORM_EVIDENCE | `workpackages/SCORING_SOURCE_SPEC.md`；迁移 `20261018_07`；`tests/test_review_score_provenance.py` | 2026-10-18（第二轮） | 见"生成基线" | 项目组（技术） | 测试通过（7 用例） | "平台区分规则分、AI 分、教师确认与独立盲评四类来源" |
| E-R2-03 | 研究方案 v1.1 修订 | DRAFT_PENDING_REVIEW | `evidence/E5_protocol/PROTOCOL_REVISION_NOTES_v1.md` + E5-01/E5-02 | 2026-10-18（第二轮） | 见"生成基线" | 项目组（技术） | 已作废（v1.1 历史记录） | "（历史条目，现行方案见 E-R4-01）" |
| E-R2-04 | 申报书六栏正文 | DRAFT_PENDING_REVIEW | `evidence/E5_protocol/E5_04_application_text.md`；字数校验 `scripts/grant/check_application_text.py` | 2026-10-18（第二轮） | 见"生成基线" | 项目组（技术） | 6/6 栏在限内；含 `〔待用户填写〕` 占位 | "申报书六栏正文已按官方模板起草并校验字数" |
| E-R2-05 | 第二轮独立验收 | PLATFORM_EVIDENCE | `workpackages/ACCEPTANCE_v2.md` | 2026-10-18（第二轮） | 见"生成基线" | 项目组（技术） | 6/6 E2E 通过；1 项因数据量未过 | "在隔离栈完成第二轮浏览器验收" |
| E-R2-06 | 教师审核材料包 | DRAFT_PENDING_REVIEW | `TEACHER_REVIEW_PACKET.md` | 2026-10-18（第二轮） | 见"生成基线" | 项目组（技术） | **待两位真实教师填写与签字** | "已准备可供两位教师审核的材料包" |

## 证据包目录

| 证据包 | 目录 | 状态 |
| --- | --- | --- |
| E1 教学与人员 | `evidence/E1_teaching_credentials/` | 目录 + 缺项清单；材料待用户提供 |
| E2 平台基础 | `evidence/E2_platform/` | 技术证据已收集，可复查 |
| E3 病例与量表 | `evidence/E3_cases_rubric/` | 草稿 + 空白审核表；待真实教师 |
| E4 前期验证 | `evidence/E4_validation/` | C（真实运行）+ D（合成演示），来源分离 |
| E5 研究方案 | `evidence/E5_protocol/` | 计划文件（拟开展），无研究结果 |

## 生成基线

```text
仓库       /home/jcshi/workspace/clinical_learning_system
分支       main
基线 SHA   1d4ef4823c75fb9d89a7aec734b8b84d0bfa5c41（本批改动之前）
提交       ea145d6ca4cbebe21381860961dce59da8baa010（第一轮）
分支       teaching-grant-2026-wpd（未合并、未部署）
第二轮     d65267e932b3fa30db187bb870c60d9d907a1f96
第三轮     e175d6a8560155d7cefc638ed22620f34c522e4d
第四轮     68c14e87ff1ea53a5daf8e3196778ac936bf372b（分支 teaching-grant-2026-wpd，未合并、未部署）
生产       仍运行 1d4ef48；本批未部署
```

> **规则**：提交后必须把上表的 SHA 更新为实际提交 SHA，并在申报材料中引用该 SHA。
> 未提交的工作树不能作为"运行版本"证据。

## 待真实人员补入（不得由 Agent 代填）

| 条目ID | 需要谁提供 | 内容 | 当前状态 |
| --- | --- | --- | --- |
| E1-01 | 用户/院系 | 六年本科见习任务证明 | REAL_PENDING |
| E1-02 | 用户 | 最佳带教老师奖项原件/扫描件 | REAL_PENDING |
| E1-03 | 用户 | 在编资格确认、团队签字 | REAL_PENDING |
| E3-01 | 两位带教教师 | 6 个病例审核意见、日期、签名 | REAL_PENDING |
| E3-02 | 两位带教教师 | 六维量表权重与锚点审核 | REAL_PENDING |
| E3-03 | 两位带教教师 | 对模拟作答的独立盲评（可选，需真实记录） | REAL_PENDING |
| E4-01 | 真实教师 | 教学演示观摩意见 | REAL_PENDING |
| E4-02 | 用户/伦理委员会 | 真实学生试点的伦理与同意材料 | REAL_PENDING |
| E5-01 | 用户/教研室 | 实际轮转时长、可招募人数、组别实施方式 | REAL_PENDING |
| E5-02 | 用户/单位 | 伦理申报与单位支持签章 | REAL_PENDING |

## 第三轮条目（2026-10-18）

| 条目ID | 内容 | 来源类别 | 文件路径 | 审核状态 | 可用于申报书的准确句子 |
| --- | --- | --- | --- | --- | --- |
| E-R3-01 | 7 天见习教学实施表 | DRAFT_PENDING_REVIEW | `evidence/E5_protocol/T2_7day_teaching_plan.md` | 待教研室确认 | "已按每批 7 天设计分步形成性训练的最小有效剂量" |
| E-R3-02 | 两种分组方案比较 | DRAFT_PENDING_REVIEW | `evidence/E5_protocol/T3_design_comparison.md` | **已被第四轮取代**：现为方案 A 唯一设计说明（见 E-R4-01） | "（历史条目）" |
| E-R3-03 | 独立考核质量控制 | DRAFT_PENDING_REVIEW | `workpackages/A_cases/A04_assessment_quality_control.md`；`A04_difficulty_calibration_BLANK.csv` | 待两位教师校准 | "已对两份独立考核病例做难度与覆盖比较并提出题本顺序平衡方案" |
| E-R3-04 | 研究方案 v2.0 | DRAFT_PENDING_REVIEW | `evidence/E5_protocol/E5_02_SAP_statistical_analysis_plan.md`；`PROTOCOL_REVISION_NOTES_v2.md` | 待教研室确认分组单位 | "研究方案已按 49 名学生 / 7 批次的实际规模重算" |
| E-R3-05 | 申报书六栏正文（第三轮） | DRAFT_PENDING_REVIEW | `evidence/E5_protocol/E5_04_application_text.md` | 6/6 栏在限内；12 项待填 | "申报书六栏正文已按正式项目名称与 7 天见习条件定稿" |
| E-R3-06 | AOSD 指南引用核实 | PLATFORM_EVIDENCE | `workpackages/A_cases/A01_assessment_multisystem.md` §10 | 已核实（2024 EULAR/PReS） | "成人 Still 病病例已引用 2024 EULAR/PReS 推荐" |

## 第四轮条目（2026-10-18）

| 条目ID | 内容 | 来源类别 | 文件路径 | 审核状态 | 可用于申报书的准确句子 |
| --- | --- | --- | --- | --- | --- |
| E-R4-01 | 唯一研究设计（7 批次整群随机） | DRAFT_PENDING_REVIEW | `evidence/E5_protocol/T3_design_comparison.md`；`E5_01` §3 | 设计已锁定；待教研室提供批次日期与抽签执行人 | "研究采用 7 批次整群随机分配，从 C(7,3)=35 种合法分配中随机产生" |
| E-R4-02 | 精确随机化检验与小样本限制 | DRAFT_PENDING_REVIEW | `E5_02` §3.3；`scripts/grant/sample_size.py` | 待统计顾问复核 | "以 7 个批次为分析单位，精确枚举 35 种分配；P 取 k/35、最小值取决于数据（唯一最大时 1/35，并列时 ≥2/35），不宣称确证性" |
| E-R4-03 | 个性化闭环代码核验 | PLATFORM_EVIDENCE | `evidence/E5_protocol/T3_personalization_validation.md`；`backend/tests/test_7day_personalization_loop.py` | 测试通过（4 passed, 1 xfailed） | "平台已接通训练评分→能力画像→短板推荐→教师干预的闭环" |
| E-R4-04 | 考核模式缺口（平台无独立考核模式） | PLATFORM_EVIDENCE（缺口） | `evidence/E5_protocol/T3_personalization_gap.md` | 已记录，未改代码 | "平台尚不能在提交层区分训练与独立考核，正式考核前需解决" |
| E-R4-05 | 题本顺序 X/Y 整批内随机 | DRAFT_PENDING_REVIEW | `workpackages/A_cases/A04_assessment_quality_control.md` §2 | 待两位教师校准 | "题本顺序在整批内部随机平衡，不改变批次所属教学组" |
| E-R4-06 | 方案 A 唯一性一致性检查 | PLATFORM_EVIDENCE | `scripts/grant/check_protocol_consistency.py` | PASS（0 违规） | "现行申报文档中不再将方案 B 列为推荐或待确认事项" |

## E1–E5 缺项清单（第二轮更新）

| 证据包 | 已有 | 仍缺 | 谁能提供 |
| --- | --- | --- | --- |
| E1 教学与人员 | 目录与缺项模板 | 六年见习任务证明、奖项原件、在编确认、团队签字 | 用户 / 教研室 / 人事 |
| E2 平台基础 | 版本、测试、截图、演示说明、第二轮验收 | 展示授权、教师实际演示反馈 | 院系 / 真实教师 |
| E3 病例与量表 | 6 份病例（已做一致性修订）、量表 v0.1、16 份模拟作答、空白审核表、审核材料包 | **两位真实教师的审核意见、日期与签名**；量表权重确认 | 两位带教教师 |
| E4 前期验证 | C 教学闭环真实运行记录、D 合成演示（隔离） | 教师观摩意见；如开展真实试点需伦理批件 | 真实教师 / 伦理委员会 |
| E5 研究方案 | v2.0 方案（49 人 / 7 批次）、SAP、数据字典、伦理要点、六栏正文、7 天教学实施表、两种分组方案比较 | **分组单位（方案 A 整群 / 方案 B 班内随机）的书面决定**；7 个批次的起止日期与每天课时；21 名实习生的学段与是否与 49 人重叠；伦理批件；单位支持与签章 | 教研室 / 伦理委员会 / 单位 |
