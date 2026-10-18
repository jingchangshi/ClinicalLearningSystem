# 2026 浙江省本科教改项目 — 交付状态总表（STATUS）

> 生成日期：2026-10-18
> 仓库：`/home/jcshi/workspace/clinical_learning_system`（`main`）
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
| C03 | 复用既有页面、补可读性 | **完成/无改动** | `C_workflow/C03_page_gaps.md`（记录而非重构） | — |
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
