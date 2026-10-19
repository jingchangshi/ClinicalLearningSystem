# R9 — 原有 3 项 Playwright 失败的分类与处置

> 记录时间：2026-10-19。执行分支：`feat/clinpath-r9-finalization`。
> 所有结论来自本轮**实际执行**的隔离栈运行，命令与计数见文末。
> 隔离要求见 `docs/teaching_grant_2026/evidence/E2_platform/ENVIRONMENT_ISOLATION.md`
> 与 `INCIDENT_2026-10-18_production_touch.md`：本轮全程使用
> `scripts/grant/e2e/run_full_acceptance.sh`（后端 8400、前端 8401、无密钥前端 8402、
> 一次性 `/tmp` 数据库、独立 `NEXT_DIST_DIR`），**未触碰生产 8100/8101**。

## 1. 结论摘要

| # | 失败用例 | 分类 | 处置 | 结果 |
| --- | --- | --- | --- | --- |
| 1 | 李明 profile explains the trend and the evidence in teaching language | (a) 可用固定数据离线验证 | 新增离线数据集生成器 | 通过 |
| 2 | 研究数据 preview is readable, honest about its size, and diverse | (a) 可用固定数据离线验证 | 同上 | 通过 |
| 3 | 学习记录 lists finished cases and the review keeps the whole reasoning | (a) 可用固定数据离线验证 | 同上 | 通过 |

**没有一项属于 (b) 真正依赖模型，也没有一项属于 (c) 产品缺陷。**
三项失败的原因相同：验收栈从未生成演示教学数据集。上一轮的判断是"重建该数据集
需要真实模型密钥"，因此把三项留作失败。本轮核实后认为该前提对本数据集不成立。

## 2. 逐项分类依据

### 2.1 三项共同根因

三项断言的都是**演示数据集**的内容，而不是某个页面逻辑：

| 用例 | 断言 | 失败现象（基线实测） |
| --- | --- | --- |
| 1 | `data-testid="growth-trend-chart"` 可见 | 元素不存在 |
| 2 | 预览表中 ≥3 名学生、≥3 个模块、≥3 个日期 | 学生数 = 1 |
| 3 | `data-testid="history-table"` 可见 | 元素不存在 |

关键证据：`GrowthTrendChart` 在**只有 1 个**趋势点时仍会渲染该 testid
（`frontend/components/GrowthTrendChart.tsx:45`），只有 0 个点时才不渲染。因此用例 1
失败说明李明的学习证据事件数为 **0**，而不是"数据不足 2 点"。用例 2 的 `codes.size = 1`
说明整个库里只有一名学生产生过学习证据。用例 3 说明 `student1` 没有任何已完成的
训练会话。

也就是说：三个页面的读路径都是好的，是**数据不存在**。种子数据
（`backend/app/seed_data.py`）只创建学生、能力画像、目录与演示登录，不产生任何学习记录。

### 2.2 为什么"需要真实模型密钥"这个前提不成立

`scripts/prepare_presentation_data.py`（运维工具）确实在无模型时拒绝执行
（`main()` 中 `if not LLM_CONFIGURED: return 2`）。但它的理由写在文件头：*"AI scores are
real model calls with real provenance. If no provider is configured the script stops
instead of writing rule output as if it were AI."* —— 它防的是**把规则输出冒充 AI**。

而本数据集的重放走的是产品真实路由函数，每一条都有**明确标注的规则降级路径**：

- 病例提交：`backend/app/services/scoring_llm.py` 无 provider 时返回
  `evaluation_mode="rule_fallback"`、`degraded=True`、`ai_score=None`；
- 学生端显示为 `规则降级评价（AI 当前不可用）`（`frontend/lib/abilityLabels.ts`）；
- 研究 CSV 与学习记录表都读同一个 `evaluation_mode` 字段。

因此只要**如实标注** `rule_fallback`，该数据集既可离线确定性生成，也不存在
"把规则输出当 AI"的问题。这与 AGENTS.md 不变量 3 一致。

### 2.3 是否存在 (c) 产品缺陷

逐项检查后**未发现产品缺陷**：

- 趋势图、学习记录、研究导出三个读路径都有后端离线测试覆盖，且以固定数据通过
  （`backend/tests/test_presentation_surfaces.py`）；
- 三者的前端渲染逻辑未改动即通过。

唯一发现的相关**行为变更**（不是缺陷）在 §4 说明：研究层的 CBL 访问控制落地后，
R8.2 流程原先选中的学生属于 CBL 组，训练被正确拒绝。

## 3. 实际修复

### 3.1 新增 `scripts/grant/e2e/build_demo_dataset.py`

离线、确定性、无模型地生成演示教学数据集，并在清单中记录来源：

- **复用运维工具的同一份计划与同一批路由函数**（`prepare_presentation_data.py` 的
  `DEMO_STUDENTS` / `ACTIVITIES` / `apply()`），避免出现第二份演示时间线定义；
- **守卫与运维工具互为镜像**：运维工具在无模型时拒绝，本脚本在**有模型时拒绝**
  （`require_keyless()`），因此规则降级数据集不可能被写到本该是 AI 数据集的地方；
- 只写 `/tmp` 下的数据库（复用 `guard.check_database_url`），且加载计划前设置
  `CLINPATH_SKIP_OPERATOR_ENV=1`，**不读取** `~/.config/clinpath/*`；
- 补建种子未创建的第四名演示学生（赵敏），并在其无学习记录、无研究入组时创建；
- 对验收库中不存在的目录引用做**确定性替换**并逐条打印（计划引用病例 #8/#10，
  种子只有 5 个病例，实际替换为 #3/#5），**不新造任何教学病例**；
- 重放后从数据库**回读评分来源**（`verify_rule_fallback_only`），任何非
  `rule_fallback` 或带 provider/model 的评分都会中止并报错；
- 输出 `demo_dataset.json`，标注 `SYNTHETIC / SIMULATED_NOT_HUMAN`、`provenance:
  rule_fallback`、`model_calls: 0`。

该步骤在 `scripts/grant/e2e/run_all_ininside.sh` 中排在 7×7 fixture **之前**：运维工具的
审计会拒绝触碰含有无法识别学生的数据库，而 7×7 fixture 正是 49 名这样的学生。

### 3.2 隔离与可复现性

生成器在同一进程内调用路由函数，因此必须先把进程数据库指向一次性库。脚本在
**导入任何 app 模块之前**设置 `DATABASE_URL`/`CLINPATH_DB_PATH`，导入后**回读
`app.database.DATABASE_URL` 并比对**，不一致即拒绝执行——否则惰性会话会回落到
`sqlite:///./clinical_learning.db`，在 `backend/` 目录下那就是生产库。

## 4. 顺带发现并修复的真实问题

### 4.1 R8.2 研究流程选中了 CBL 组批次

加入演示数据集后，R8.2 第 5 步出现 `POST /api/sessions/start → 403`，其后 4 项未运行。

根因：`research-flow.spec.ts` 的注释写着研究学生"picked from a ClinPath-arm cohort"，
但代码取的是 `manifest.student_ids[0]`，即第一批次的第一名学生；本次冻结抽签把
**TEST-C01 分到了 CBL 组**。研究层 CBL 访问控制（`app/research/study_access.py`）落地后，
该学生被正确拒绝训练。**这是测试与夹具的假设错误，不是产品缺陷。**

修复：夹具从产品自己的分配记录读取各批次组别，把压缩时间窗交给一个 **ClinPath** 批次，
并在清单中记录 `study_groups` / `cohort_students` / `demo_cohort`；用例读取该记录，
若缺失或不是 ClinPath 批次则明确失败。

### 4.2 演示数据集不得进入研究数据

演示学生若被登记为研究 sittings，会污染研究数据集与 7 项不变量。因此演示考核使用
产品自带的第三个 `data_origin`：`synthetic_demo`（`app/research/__init__.py`）。研究导出、
统计与不变量均按 origin 过滤，实测研究数据仍为 98 份 sitting，演示考核单独 2 份。

## 5. 原先 11 项跳过用例的分类与处置

基线 11 项跳过。逐项核实后，**9 项在本环境应当运行**，已启用；2 项保留条件跳过。

| 用例 | 跳过条件 | 本环境是否应运行 | 处置 |
| --- | --- | --- | --- |
| training: SP encounter… | `E2E_RUN_MUTATING=1` | 应运行：本栈是一次性栈 | 已启用 |
| training: knowledge quiz… | 同上 | 应运行 | 已启用 |
| training: re-saving one step… | 同上 | 应运行 | 已启用 |
| training: submitting with missing steps… | 同上 | 应运行 | 已启用 |
| training: student completes a case with Coach… | 同上 | 应运行 | 已启用 |
| training: teacher confirms six dimensions… | 同上 | 应运行 | 已启用 |
| training: teacher case authoring… | 同上 | 应运行 | 已启用 |
| training: a keyless deployment shows the rule fallback honestly | `E2E_EXPECT_FALLBACK=1` | 应运行：本栈按构造无密钥 | 已启用 |
| auth: route protection fails closed when no JWT_SECRET… | 需要无密钥前端 | 应运行：已加入隔离栈（8402） | 已启用 |
| assessment: start → draft survives reload → five stages → submit | `E2E_RUN_MUTATING=1` **且**该账号有开放 sitting | 应运行 | 已启用（专用演示考核账号） |
| assessment: a blinded rater scores… | `E2E_RATER_*` 且队列中有待评答卷 | 运行（通过锁定分支） | 已启用 |

说明：`E2E_RUN_MUTATING` 的文档条件就是"disposable deployment"，本栈完全满足
（一次性 `/tmp` 数据库，`stack.py` 结束时销毁），因此继续关闭它会把本环境**能够**运行的
覆盖排除在外。

## 6. 仍未覆盖的部分（不隐藏）

1. **真实模型评分的浏览器验收**。`E2E_EXPECT_REAL_AI=1` 路径要求真实 provider 调用
   （`training.spec.ts` 会校验 `ai_invocations` 中的 provider/model/success）。本栈按
   设计无密钥，因此该路径**不在本轮执行范围内**。需人工在有密钥的环境执行：

   ```bash
   # 在隔离栈（非 8100/8101）上，使用真实密钥的那一份部署：
   E2E_BASE_URL=http://127.0.0.1:<隔离前端端口> \
   E2E_STUDENT_USERNAME=<学生> E2E_STUDENT_PASSWORD=<密码> \
   E2E_TEACHER_USERNAME=<教师> E2E_TEACHER_PASSWORD=<密码> \
   E2E_RUN_MUTATING=1 E2E_EXPECT_REAL_AI=1 \
   npx playwright test tests/e2e/training.spec.ts -g "Coach"
   ```

   判据：`evaluation-mode` 显示 `AI 语义评价`，且 `ai_invocations` 中
   `provider=deepseek`、`model=deepseek-flash`、`success=1`、`fallback_used=0`。

2. **`prepare_presentation_data.py --apply`（真实演示库）**。本轮的离线生成器只服务
   验收栈，**不替代**运维工具，也**未**对任何真实/生产数据库执行。

3. 演示数据集是**合成数据**，不代表真实教学效果；`demo_dataset.json` 与页面标注均如此声明。

## 7. 本轮实际执行与结果

隔离栈（`run_full_acceptance.sh`，后端 8400 / 前端 8401 / 无密钥前端 8402，
一次性 `/tmp/clinpath-e2e/accept.db`，无 provider 密钥）：

| 项目 | 基线（本轮开始时实测） | 本轮结果 |
| --- | --- | --- |
| 既有 Playwright 套件 | 26 通过 / **3 失败** / 11 跳过 | **40 通过 / 0 失败 / 0 跳过** |
| R8.2 研究全流程 | 9/9 | **9/9** |
| 7 批 49 人 7 项不变量 | 7/7 | **7/7** |
| 演示数据集步骤 | 不存在 | 通过（16 次活动，5 份病例评分全部 `rule_fallback`） |
| E2 证据截图 | 通过 | 通过 |

基线复现说明：本轮开始时在起始 SHA `47d191e` 上先跑了一次完整验收，得到与任务书一致的
26/3/11，确认环境与历史证据一致后，才进行修复。

后端：`pytest -q` 全量结果见 `R9_TEST_REPORT.md`（本轮新增
`backend/tests/test_demo_dataset_offline.py` 9 项）。
