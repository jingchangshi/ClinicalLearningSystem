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
提交       ea145d6ca4cbebe21381860961dce59da8baa010
分支       teaching-grant-2026-wpd（未合并、未部署）
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
