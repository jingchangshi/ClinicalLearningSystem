# 2026 浙江省本科教改项目 — 交付状态总表（STATUS）

> **第三轮（2026-10-18）已完成，提交 `e175d6a8560155d7cefc638ed22620f34c522e4d`**：按负责人确认的真实教学条件（7 天/批 × 7 人/批 × 7 批 = 49 名见习生）
> 统一项目名称、重设干预、修订研究人群与统计、独立考核质控、申报正文定稿。
> 逐项状态见文末 §7「第三轮交付」。
>
> **第二轮（2026-10-18）已完成，提交 `d65267e932b3fa30db187bb870c60d9d907a1f96`**：医学病例一致性修复、评分来源口径统一、
> 研究方案 v1.1、官方模板六栏正文、独立验收与教师审核材料包。
> 逐项状态见文末 §6「第二轮交付」。

> 生成日期：2026-10-18
> 仓库：`/home/jcshi/workspace/clinical_learning_system`（分支 `teaching-grant-2026-wpd`，基于 `main`）
> 基线 SHA：`1d4ef4823c75fb9d89a7aec734b8b84d0bfa5c41`（本批改动之前）
> 本批提交：`ea145d6ca4cbebe21381860961dce59da8baa010`（分支 `teaching-grant-2026-wpd`）。**未部署**；生产仍运行 `1d4ef48`。

## 0. 一句话结论

工作包 D 已在代码与浏览器中实际跑通；A/B/E5 的材料与脚本已交付并实跑校验；C 的素材与录屏索引已采集。
**没有任何一份病例或量表被写成"已审核"**；**没有任何真实学生或真实教师记录被生成**；
合成数据只展示"技术可行性"，不作为教学效果证据。

## 1. 总表

| 编号 | 任务 | 状态 | 事实与证据 | 阻塞 |
| --- | --- | --- | --- | --- |
| T00 | 资产与证据盘点 | **完成** | `STATUS.md`（本文件）、`EVIDENCE_INDEX.md`；离线 ZIP 已核对并复制为 `demo_research/synthetic_v1/` | — |
| A01 | 6 例标准化病例教学卡（4 训练 + 2 考核） | **完成（草稿）** | `workpackages/A_cases/A01_*.md`，全部 `PENDING_REAL_REVIEW`；校验脚本 88/88 PASS | 两位真实教师审核 |
| A02 | 平台 schema 核对 + 最小导入/校验脚本 | **完成** | `A02_platform_schema_notes.md`、`scripts/grant/check_case_cards.py`（只读 dry-run，实测 PASS/FAIL 双向） | — |
| A03 | 两位教师空白审核表 | **完成** | `A03_teacher_review_form_BLANK.{md,csv}`，12 行，姓名/日期留空，结论 `PENDING_REAL_REVIEW` | 真实教师填写 |
| A04 | 至少 1 例完成真实 UI 教学路径验证 | **部分完成** | 平台已有等价 `SLE基础病例`（`seed_data.py:548`）可走通 UI；新卡 CASE-T01 的导入载荷已通过 schema 与去标识化校验但**未导入**（平台无 `case_type` 字段，无法表达训练/考核隔离） | 平台字段扩展需单独决策 |
| B01 | 六维量表 v0.1（权重 10/20/25/15/20/10） | **完成（草案）** | `B01_rubric_v0.1.md`，含低/中/高三档锚点；**明确写出平台当前 `WEIGHTS=20/20/20/15/15/10` 与量表不一致** | 教师确认权重与锚点 |
| B02 | 12–20 份模拟作答供盲评 | **完成** | 16 份，`B02_sample_answers.{md,csv}`，无任何分数列 | 教师独立盲评 |
| B03 | 统一导出模板 + 盲法说明 | **完成** | `B03_export_template.md`、`B03_rating_template.csv`（32 行空白）；写明平台"复核确认"回写画像、不是盲评 | 教师评分 |
| B04 | 量表一致性分析脚本 | **完成** | `scripts/grant/rubric_agreement.py`；空真实评分时**退出码 2 且不出数**；模拟演示需显式 `--demo`；自检 8/8 PASS | 无真实评分可分析 |
| C01 | SLE 端到端演示流程记录 | **完成** | `C_workflow/C01_demo_walkthrough.md` | — |
| C02 | 每个环节的角色/ID/来源/版本记录 | **完成** | `C_workflow/C02_run_record.md` + `C02_evidence/00–23`（23 份原始 JSON/时间线） | — |
| C03 | 复用既有页面、补可读性 | **完成（1 处内部 key 修复）** | `C_workflow/C03_page_gaps.md`；干预页改为渲染后端 `display_labels` 中文标签（+1 后端测试），学生首页「八维→九维」纠正；其余 4 条记录未改 | — |
| C04 | 3–5 分钟录屏脚本与截图索引 | **完成** | `C_workflow/C04_screenplay.md` + 17 张截图 | 真实专家观摩意见由用户补入 |
| D01 | 独立只读版本化数据资源 | **完成** | `demo_research/synthetic_v1/`；路由与服务不 import ORM/DB；调用 7 端点前后业务表行数不变（测试固定） | — |
| D02 | `/teacher/research-demo` + 只读 API + CSV | **完成** | `routes/demo_research.py`、`research-demo/` 页面；浏览器实测通过（见 §3） | — |
| D03 | 统计随数据现算，保留种子与版本 | **完成** | 与离线工作簿逐项一致（含 HC3 与正态参考分布两个陷阱，见 `ARCH.md §18.3`） | — |
| D04 | 与真实导出隔离、鉴权、行数不变 | **完成** | 匿名 401 / 学生 403；真实导出页加显式"不含合成数据"声明 | — |
| D05 | 可选真实 LLM 虚拟学生文本 | **未开始（有意不做）** | 见 `workpackages/D_research_demo/STATUS_D.md §6` | 截止日前不具证据价值 |
| E1 | 教学与人员证明 | **部分完成（目录+缺项清单）** | 见 `EVIDENCE_INDEX.md` 待真实人员表 | 六年任务证明、奖项原件、在编确认、团队签字 |
| E2 | 平台技术证据 | **完成** | 当前 SHA、测试、截图、演示说明 | 展示授权与教师实际演示反馈 |
| E3 | 病例与量表草稿+审核 | **部分完成（草稿）** | A/B 全部文件 | 两位教师实际审核与签名 |
| E4 | 前期验证 | **部分完成** | C（真实流程回执）+ D（合成演示），来源分离 | 教师观摩意见；如有真实试点需伦理 |
| E5 | 研究方案/SAP/样本量/数据字典/伦理 | **完成（计划文件）** | `evidence/E5_protocol/E5_01–04` + `scripts/grant/sample_size.py`（实跑输出已粘贴） | 轮转时长、可招募人数、伦理申报 |

## 2. 本批实际执行的验证（真实输出）

```text
backend tests     uv run --python 3.11 --with-requirements requirements.txt pytest -q
                  227 passed（基线 211 + 新增 16），1 warning
frontend typecheck  npm run typecheck                → 通过
frontend lint       npm run lint                     → 通过（0 warning）
frontend build      npm run build                    → 通过
playwright          tests/e2e/research-demo.spec.ts   → 3 passed
                    tests/e2e/teacher.spec.ts          → 3 passed
                    tests/e2e/demo-readiness.spec.ts   → 5 passed / 1 failed
                      失败项是数据量前置条件（验证库 1 名学生 / 1 模块 / 1 日期，
                      生产库为 4 / 5 / 17），不是代码回归
case cards          python3.11 scripts/grant/check_case_cards.py → 88/88 PASS，exit 0
rubric script       python3.11 scripts/grant/rubric_agreement.py <空真实表> → exit 2，不出数（护栏生效）
                    python3.11 scripts/grant/rubric_agreement.py --self-check → 8/8 PASS
deploy              ./scripts/verify_deploy.sh       → PASSED（生产仍为 HEAD 1d4ef48）
```

浏览器验收（隔离栈，**非生产**）：教师可从研究数据页进入演示页、看到 sticky 合成横幅、
下载 60 行 `SYNTHETIC` CSV、查看 5 阶段模拟作答；学生访问被重定向且 API 返回 403。

## 3. 一条必须记录的事故与恢复

在验证过程中，我为隔离验收栈执行了 `npm run build`，它覆盖了生产前端服务读取的
`frontend/.next`，使生产入口短暂指向临时后端（8201）或返回 502。

处置：将工作树 stash → 用生产环境变量重建 HEAD 前端 → 重启 `clinical-frontend.service`
→ `./scripts/verify_deploy.sh` 恢复为 **PASSED**（运行版本 = `1d4ef48`）→ 恢复 stash。
当前生产运行的是未改动的 HEAD；本批改动已提交为 `ea145d6ca4cbebe21381860961dce59da8baa010`，**未部署**。

教训：验收栈必须用独立 `distDir`，且绝不能与生产共用 `frontend/.next`。

## 4. 需要用户决定或提供的事项

1. **两位真实带教教师**：填写 `A03_teacher_review_form_BLANK.csv` 与盲评 `B03_rating_template.csv`。
2. **E1 证明材料**：六年本科见习任务证明、最佳带教老师奖项原件/扫描件、在编资格确认、团队签字。
3. **E5 参数**：实际轮转时长、每批次可招募人数、组别实施方式（整群 vs 班次内小组）。
4. **院系支持与伦理申报**：签章与受理号。
5. **平台权重是否对齐**：任务书 10/20/25/15/20/10 与 `scoring_llm.WEIGHTS` 不一致，
   是否改动是一个独立代码变更，需你决定。
6. **是否部署本批改动**：当前刻意未部署，等待你在浏览器里先复核演示页。

## 5. 不得写入申报书的表述

- 不得写"纳入 60 名本科生""P<0.001，ClinPath 显著提升"——这 60 人是虚拟的。
- 不得写"已完成两位带教教师审核"——尚未发生。
- 不得把平台 `total_score` 当作 `rubric-v0.1` 加权总分——二者权重不同。
- 不得把模拟评分者写成真实教师评分者。


---

## 6. 第二轮交付（2026-10-18）

本轮目标：让 A–D 与 E1–E5 具备**医学专家审核、独立教学演示、申报书定稿**的条件。
本轮**不合并主分支、不部署生产**。

| 任务 | 状态 | 交付物 | 待谁确认 |
| --- | --- | --- | --- |
| 1 医学病例一致性 | **已完成（AI 自查修订）** | `workpackages/A_cases/MEDICAL_REVIEW_ISSUES_v1.md`；CASE-A01/T01/T02/T03 已修订；三份病例新增计分表 | 12 个临床/教学取舍问题（清单第三节）需真实教师裁定 |
| 2 评分口径与来源 | **已完成（含迁移与测试）** | `workpackages/SCORING_SOURCE_SPEC.md`；迁移 `20261018_07`；`tests/test_review_score_provenance.py`（7 用例） | 量表权重是否对齐（本轮不改） |
| 3 研究方案修订 | **已完成（v1.1）** | `evidence/E5_protocol/PROTOCOL_REVISION_NOTES_v1.md`；E5-01/E5-02 重写 | **分组单位（整群/班内）须由教研室书面决定** |
| 4 官方模板六栏正文 | **已完成（字数校验通过）** | `evidence/E5_protocol/E5_04_application_text.md`（3599 / 3900 字）；`scripts/grant/check_application_text.py` | 六处 `〔待用户填写〕` |
| 5 独立验收与证据 | **已完成** | `workpackages/ACCEPTANCE_v2.md`（12/12 E2E）；`TEACHER_REVIEW_PACKET.md`；`scripts/grant/make_acceptance_dataset.py` | 两位教师填写与签字 |

### 6.1 本轮实测

```text
backend pytest            235 passed（含新增 7 个评分来源用例）
frontend typecheck        pass
frontend lint             pass
playwright（验收栈 8204）  12 passed（demo-readiness 6 + teacher 3 + research-demo 3）
check_case_cards.py       88/88 PASS
check_application_text.py 6/6 栏在限内
rubric_agreement.py       空真实表 → exit 2（护栏生效）
迁移 20261018_07          在生产库副本上升级/降级/再升级均通过
```

### 6.2 本轮的关键修复

1. **CASE-A01 自相矛盾**：原卡同时声称"计分 7 分 ≥6"与"未满足任何分类标准"。
   现改为病程 5 周（0 分）、2 个小关节（2 分），总分 **2+2+1+0=5 < 6**，
   标准答案"未分化多关节炎"与计分结论一致，并附初诊/随访两张计分表。
2. **CASE-T02 算术错误**：关节数实为 12 个小关节（应计 5 分），总分应为 **10** 而非 8。
3. **规则分冒充 AI 分**：教师复核原先把 `rule_fallback` 的 `total_score` 写进
   `TeacherScoreReview.ai_score`。现由 `_review_baseline()` 统一判定，
   新增 `baseline_score` / `baseline_source`，历史行标 `legacy_ambiguous`。
   页面列标题由「AI评分」改为「对照评分」+「评分来源」。
4. **整群分析错误**：SAP 原默认个体层面 HC3，并声称 HC3 处理群内相关。
   现并列整群/班内两种设计，整群用 cluster-robust 或混合模型并强制报告 ICC；
   删除"单一组别批次内估计组间效应"的错误描述。

### 6.3 第二轮明确未做

- 未合并 `main`，未部署生产（生产仍运行 `1d4ef48`）。
- 未修改生产数据库，未在生产执行迁移。
- 未改变平台形成性评分权重（`20/20/20/15/15/10`）。
- 未伪造任何教师签名、日期或审核结论。
- 未用合成数据估计真实效应或样本量。


---

## 7. 第三轮交付（2026-10-18）

**正式项目名称**：基于人工智能辅助临床推理训练的医学生个性化学习与形成性评价教学改革研究
（子研究/内部研究方案名称：基于 ClinPath 平台的本科风湿免疫见习临床推理形成性训练效果研究）

**本轮确认的真实教学条件**：每批 7 天、每批 7 名学生、7 个批次 = **49 名本科见习生**；
见习 + 实习合计 70 人，其余 21 名实习生为**独立拓展人群**（不并入主要结局分析，学段归属待确认）；
至少 2 位带教教师可参与审核与盲评。

| 任务 | 状态 | 交付物 | 待谁确认 |
| --- | --- | --- | --- |
| T1 项目名称与范围统一 | **完成** | E5-01 §1、E5-04 头部、本文件 | — |
| T2 7 天见习干预设计 | **完成** | `evidence/E5_protocol/T2_7day_teaching_plan.md`；E5-01 §5 | 教研室确认排课与课时 |
| T3 研究人群/分组/统计 | **完成** | `T3_design_comparison.md`；E5-01 §3–4；E5-02 v2.0；`sample_size.py` 重算 | **教研室决定方案 A 还是 B** |
| T4 独立考核质控 | **完成** | `workpackages/A_cases/A04_assessment_quality_control.md`；`A04_difficulty_calibration_BLANK.csv` | 两位教师做难度校准 |
| T5 申报正文六栏 | **完成** | `E5_04_application_text.md`（字数校验通过）；`E5_04_placeholders.md`（12 项） | 12 项待填信息 |
| T6 证据包与验收 | **完成** | 本文件、`EVIDENCE_INDEX.md`、`TEACHER_REVIEW_PACKET.md`、D 时间轴说明 | — |

### 7.1 本轮关键结论

1. **两份独立考核病例难度不可比**：CASE-A02（AOSD 伴 MAS 风险）明显难于 CASE-A01（UA 边界计分）。
   若固定"T0 用 A01、T1 用 A02"，前后测差会混入难度差。已给出交叉反平衡设计（每批内 X/Y 顺序均分）
   与精确分配表，并建议主模型加入 `case_at_T1` 协变量。
2. **方案 B 为推荐设计**：每批 7 人内部 3+4 随机、跨批交替使两臂为 **24 vs 25**；
   批次固定效应**可估**（每批同时含两组），而方案 A 中组别与批次完全共线、批次效应不可识别。
3. **49 人 / 7 批次的功效上限**：80% 功效最小可检出 d ≈ 0.79–0.81；对 d=0.50 功效仅约 0.39–0.40。
   因此研究定位为**探索性/可行性**，不承诺确证性优效。
4. **AOSD 指南引用已核实更正**：原"EULAR/ACR 成人 Still 病管理推荐"实为
   **2024 EULAR/PReS 推荐**（*Ann Rheum Dis* 2024;83(12):1614–1627, PMID 39317417）。

### 7.2 本轮实测

```text
python3.11 scripts/grant/check_application_text.py   6/6 栏在限内，合计 3527/3900
python3.11 scripts/grant/check_case_cards.py         88/88 PASS
python3.11 scripts/grant/sample_size.py              按 49 人 / 7 批次重算，输出已粘贴进 SAP
```

本轮**未修改运行代码**，因此未重复执行后端/前端全量测试与 Playwright（任务书第 T6 条允许）。
生产仍运行 `1d4ef48`，未部署、未迁移。

### 7.3 本轮明确未做

- 未合并 `main`，未部署生产，未在生产库执行迁移。
- 未编造伦理批件号、奖项年份/颁发单位、经费金额或单位承诺（均为 `〔待用户填写〕`）。
- 未用合成数据估计真实效应或样本量。
- 未替教研室决定分组方案，未替教师决定病例难度取舍。
