# 工作包D：独立合成研究展示 — 交付说明

> **全部为合成数据。没有真实学生、真实的实验组干预或真实教师评分。这些统计数字不能证明平台的实际教学效果。**
>
> 数据来源：`ClinPath_WPD_完整工作包D.zip`（离线包原始文件保留在 `docs/` 根目录，未修改）。
> 集成形式：仓库内只读版本化资源 `demo_research/synthetic_v1/`，**不进入任何业务表**。

## 0.1 第三轮说明：模拟时间轴 ≠ 真实 7 天见习

工作包 D 的合成数据使用**虚构的多周时间轴**（`learning_sessions_SYNTHETIC.csv` 中
`week` 取 1/3/5，`date_relative` 为「第1周」「第3周」「第5周」）。

真实教学条件是**每批 7 天**（见 `evidence/E5_protocol/T2_7day_teaching_plan.md`）。
两者**不得混淆**：

| | 合成演示（D） | 真实研究（拟开展） |
| --- | --- | --- |
| 时间单位 | 周（1/3/5 周） | 天（D1–D7） |
| 人数 | 60 名虚拟学生 | 49 名本科见习生 |
| 分组 | 30/30 预设 | 待教研室确认（方案 A 或 B） |
| 数据来源 | 生成器预设参数 | 真实学生作答与教师盲评 |
| 用途 | 演示统计流程可跑通 | 研究 |

**D 的时间轴是演示设计，不是对真实 7 天见习的模拟，也不代表任何真实排课。**
本轮未修改 D 的数据；本说明只防止读者把两者对应起来。

## 0. 第二轮（2026-10-18）复核

本轮**未改动**工作包 D 的任何数据、页面或统计逻辑。复核结果：

```text
cd backend && uv run --python 3.11 --with-requirements requirements.txt \
  pytest -q tests/test_demo_research.py
16 passed
```

- 合成数据仍在 `demo_research/synthetic_v1/`，文件未变；
- 路由与服务仍不 import ORM / DB 会话；7 个端点调用前后业务表行数不变；
- 页面顶部合成横幅、`SYNTHETIC` CSV 文件名与逐行标记保持；
- 与真实研究导出页仍然分离。

第二轮新增的评分来源字段（`baseline_score` / `baseline_source`）只作用于
**真实业务表** `teacher_score_reviews`，与合成演示层无关。

## 1. 交付对照（D01–D05）

| 编号 | 任务 | 状态 | 实现位置 | 证据 |
| --- | --- | --- | --- | --- |
| D01 | 独立、只读、版本化数据资源，不写业务表 | 完成 | `demo_research/synthetic_v1/`（版本化目录） | `backend/tests/test_demo_research.py::test_demo_router_never_touches_the_database`、`::test_service_does_not_import_the_orm_or_a_db_session` |
| D02 | `/teacher/research-demo` + 只读 API + CSV | 完成 | `backend/app/routes/demo_research.py`、`frontend/app/(main)/teacher/research-demo/` | 浏览器实测见 §4；`test_export_csv_is_synthetic_in_name_header_and_rows` |
| D03 | 统计随数据现算，保留种子与生成器版本 | 完成 | `backend/app/services/demo_research.py` | `test_statistics_reproduce_the_offline_workbook` |
| D04 | 与真实导出隔离 + 鉴权 + 业务表行数不变 | 完成 | 两条路由互不引用；`require_role(["teacher"])` | `test_demo_router_never_touches_the_database`、`test_anonymous_and_students_cannot_read_the_demo` |
| D05 | 可选真实 LLM 虚拟学生文本 | **未开始（有意不做）** | 见 §6 | — |

## 2. 页面内容与"模拟"标识

页面 `/teacher/research-demo` 自上而下：

1. **sticky 橙色横幅**：`合成教学研究演示｜虚拟学生、虚拟评分者｜不代表真实教学成效`
   ——`position: sticky` 是为了让截图无论裁剪到哪一段都带着它。
   第二行给出 `dataset_id`、随机种子 `20261018`、`data_origin`。
2. 研究设计、预设情景说明（生成器注入的 CBL≈6 分 / ClinPath≈18 分提升期望）。
3. 两组 T0/T1 均值、平均提升、提升标准差；Welch 检验与 HC3-ANCOVA 的效应、95%CI、P 值，
   下方紧接 `analysis_note`（"P 值不能作为真实教学效果的证据"）。
4. 虚拟学生列表（可按组筛选、按研究编号搜索）+ 每名学生详情：
   六维前后测柱状图、独立前后测明细（含"计算机模拟评分者（非真实教师）"）、
   三次训练过程、五阶段"模拟学生初答 → 模拟AI追问 → 模拟修订作答"。
5. 数据字典、数据来源与可复现性（每个文件的 sha256 前缀）。
6. 真实教师专家审核区：状态固定显示 `PENDING_REAL_REVIEW`，审核人/日期为空；
   待填写数与总行数由 CSV 计算，未收到真实记录前不可能显示"已审核"。
7. CSV 下载：`clinpath-SYNTHETIC-demo-research-v1.csv`。

## 3. 统计真值源

所有数字由 `compute_summary()` 从 `demo_research/synthetic_v1/data/*.csv` 现算，
页面、`/summary` JSON 与 CSV 下载共用同一结果。实现细节与两个"静默分歧"陷阱
（HC3 白化残差、HC3 用正态参考分布）记录在 `docs/ARCH.md` §18.3。

与离线包的复现结果（`backend/tests/test_demo_research.py` 逐项断言）：

| 指标 | 离线 `metrics_SYNTHETIC.json` | 服务端现算 |
| --- | --- | --- |
| CBL 提升均值 | 4.33 | 4.33 |
| ClinPath 提升均值 | 20.15 | 20.15 |
| 提升差 | 15.82 | 15.82 |
| 提升差 95%CI | 13.53–18.11 | 13.53–18.11 |
| Welch t | 13.835 | 13.835 |
| Welch P | 8.5925×10⁻²⁰ | 8.5925×10⁻²⁰（对数尺度比较） |
| ANCOVA 效应 | 15.93 | 15.93 |
| ANCOVA 95%CI | 13.59–18.27 | 13.59–18.27 |
| ANCOVA P | 1.4102×10⁻⁴⁰ | 1.4102×10⁻⁴⁰（对数尺度比较） |

## 4. 实测记录

环境：隔离验收栈，**不是生产**。

```text
backend   uvicorn 127.0.0.1:8201，DATABASE_URL=/tmp/clinpath-demo-verify/verify.db（一次性库）
frontend  next start 127.0.0.1:8202，INTERNAL_API_BASE_URL=http://127.0.0.1:8201/api
账号      verify_teacher（临时创建于一次性库）/ student1（seed 生成，受限演示账号）
```

浏览器（Playwright + Chromium，1440×900）实跑结果：

```text
entry visible: true                       # 从 /teacher/research-export 的入口按钮
banner: 合成教学研究演示｜虚拟学生、虚拟评分者｜不代表真实教学成效 数据集 synthetic_v1 · 随机种子 20261018 · 全部记录标记 SYNTHETIC_DEMO_NOT_REAL_STUDENTS
h1: 合成教学研究演示
download filename: clinpath-SYNTHETIC-demo-research-v1.csv
csv first line: SYNTHETIC_DATA_ORIGIN,study_id,group,cohort,pre_score_T0,...
csv data rows: 60
detail visible: true
detail has simulated raters: true
detail has five stages: 5
detail has 模拟AI追问: 5
pending review visible: true
scrollWidth/clientWidth: { scroll: 1440, client: 1440 }   # 无横向滚动
student redirected to: /student/dashboard                 # 学生访问教师页被弹回
student API status: 403                                   # 直接调 API 被拒
ERRORS: ['console: Failed to load resource: ... 401 (Unauthorized)']  # 见下
```

关于唯一的 console error：它是登录页在会话建立前探测 `/api/auth/me` 的 401，
既有 `frontend/tests/e2e/demo-readiness.spec.ts` 已把该请求列为预期噪声。

截图：`docs/teaching_grant_2026/workpackages/D_research_demo/D01_screenshots/`
（页面顶部、学生详情、专家审核区）。

## 5. 数据完整性（由测试固定）

- 60 个唯一 `study_id`；CBL 30 / ClinPath 30。
- 每人恰好一条 T0、一条 T1；共 120 条独立考核记录。
- 180 条训练记录；450 条五阶段记录，全部可经 `session_id → study_id` 追溯；
  90 个 ClinPath 会话每个恰好 5 步。
- 所有行 `data_origin=SYNTHETIC_DEMO_NOT_REAL_STUDENTS`；评分行 `rater_origin=SIMULATED_NOT_HUMAN`。
- 调用 7 个端点前后，`students` / `case_sessions` / `learning_evidence_events` /
  `teacher_score_reviews` 行数完全不变。

## 6. 为什么 D05 不做

D05（真实 LLM 生成虚拟学生文本）被任务书标为 P1 **可选**。当前数据集的文字列已是
"模型撰写的模板 + 固定随机变化"，并在 CSV 中如实标记
`MODEL_AUTHORED_TEMPLATE_PLUS_DETERMINISTIC_VARIATION`；页面照抄这个事实，
没有把它说成"450 次线上模型调用"。

不做 D05 的理由：
1. 它不会改变任何量化结局，因此不增加申报材料的证据强度；
2. 它需要真实模型调用与专家抽样核查，两者在截止日前都无法可靠完成；
3. 一旦生成，就必须记录 `generator_type/model/prompt_version` 并做医学真实性核查，
   否则反而是新的不可核查内容。

如果后续要做，模板与提示词已在 `demo_research/synthetic_v1/AI_模拟学生提示词.md`。

## 7. 待真实人员完成

- 两位真实带教教师对 6 个病例、六维量表的审核（`templates/expert_review_BLANK.csv` 保持留空）。
- 若开展"专家对模拟作答的评价"，需在 `B03` 模板中由教师本人填写并签署日期；
  这是"专家对合成材料的评价"，不是学生教学效果。
- 真实研究数据的采集须使用 `REAL_CONSENTED` 标记，并与本演示物理/逻辑隔离
  （见 `docs/teaching_grant_2026/evidence/E5_protocol/`）。

## 8. 第二轮隔离复核（2026-10-18，Task 5）

在第二轮改动（评分来源溯源、教师复核页面）之后重跑 D 的隔离测试：

```text
$ cd backend && uv run --python 3.11 --with-requirements requirements.txt pytest -q tests/test_demo_research.py
................                                                         [100%]
16 passed, 1 warning in 2.77s
```

- 路由与服务仍未 import ORM / DB session（`app/services/demo_research.py`
  只依赖标准库）。
- 合成标记逐文件完整：participants 60/60、assessments 120/120、
  learning_sessions 180/180、reasoning_steps 450/450、analysis_ready 60/60。
- 浏览器侧 `tests/e2e/research-demo.spec.ts` 在一次性验收栈上 3/3 通过
  （合成横幅、SYNTHETIC CSV、学生 403、真实导出页仍可用）。
- 环境与命令见 `../ACCEPTANCE_v2.md`。
