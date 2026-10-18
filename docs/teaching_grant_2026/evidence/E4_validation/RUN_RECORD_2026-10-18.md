# E4 运行记录：隔离栈上的完整研究流程与 7 批批量验证

> 状态：**已实际执行**。本文只记录真实命令、真实输出与真实结论。
> 记录时间：2026-10-18 16:27—16:31 UTC。执行环境：独立 worktree `/home/jcshi/workspace/clinpath-final`，
> 分支 `feat/clinpath-final-2026`，运行提交 **`375e197`**（`375e19748baf499908f2b5b78217417762bababa`）。
> **所有账号与数据均为 `TEST` / `SYNTHETIC / SIMULATED_NOT_HUMAN`，不是真实教师、不是真实学生、不是教学效果证据。**

## 1. 一句话结论

在隔离栈（后端 8400 / 前端 8401 / `/tmp` 一次性 SQLite / 构建期烘焙的独立 `NEXT_DIST_DIR`）上：

- 既有 Playwright 套件 + 新增 R8.2 全流程：**35 passed，3 failed，11 skipped**（失败项全部为需要预置演示数据的旧用例，见 §5）；
- R8.2 九个步骤（管理员建题本 → 两教师审核 → 发布 → 学生 T0 → D2/D3 训练 → D4/D5 个性化 → 学生 T1 → 双教师盲评 → 裁决 → 研究导出）**9/9 通过**；
- 7 批 × 7 人 × 98 场批量流程：**7 项不变量全部成立**；
- E2 截图 **16 张**全部来自本次运行。

## 2. 环境与隔离（可复现）

| 隔离项 | 取值 | 说明 |
| --- | --- | --- |
| Git 工作目录 | `/home/jcshi/workspace/clinpath-final` | 独立 worktree，未触碰主检出 |
| 后端端口 | `127.0.0.1:8400` | 启动前校验非 8100，且端口空闲 |
| 前端端口 | `127.0.0.1:8401` | 启动前校验非 8101，且端口空闲 |
| 前端构建目录 | `frontend/.next-accept` | 独立 `NEXT_DIST_DIR`，不覆盖生产 `.next` |
| 构建期 API 目标 | `http://127.0.0.1:8400/api` | 见 §3，构建后已核验 `routes-manifest.json` |
| 数据库 | `sqlite:////tmp/clinpath-e2e/accept.db` | 一次性；`alembic upgrade head` → `20261018_09` |
| 环境变量 | 进程内构造 | 未读取、未写入 `~/.config/clinpath/*.env` |
| 模型密钥 | **刻意留空** | `LLM_API_KEY=""`；AI 不可用，产品必须显式降级 |
| 日志 | `/tmp/clinpath-e2e/logs/` | alembic / seed / build / backend / frontend / 各套件 |
| 截图 | `../E2_platform/screenshots/` | 16 张，见 §6 |

**构建期烘焙核验**（这是 2026-10-18 生产误触事件的根因，必须每次核验）：

```
$ python3 -c "import json;print(json.load(open('frontend/.next-accept/routes-manifest.json'))['rewrites']['afterFiles'])"
[{'source': '/api/:path*', 'destination': 'http://127.0.0.1:8400/api/:path*', ...}]
```

`destination` 指向 8400，**不是** 8100。

## 3. 运行命令

```bash
cd /home/jcshi/workspace/clinpath-final

# 一次完整运行：重置一次性库 → 迁移+seed → 独立构建 → 起服务 →
# fixture → 不变量 → Playwright（既有套件 + R8.2）→ 截图 → 停服务
./scripts/grant/e2e/run_full_acceptance.sh final-run-2
```

单步命令（便于排查）：

```bash
python3 scripts/grant/e2e/stack.py prepare --reset           # 一次性库 + alembic head + seed
python3 scripts/grant/e2e/stack.py build                     # .next-accept，烘焙 8400
./scripts/grant/e2e/run_acceptance.sh --reuse-build          # 栈 + fixture + 全套 Playwright
./scripts/grant/e2e/run_acceptance.sh --no-tests             # 只建 fixture
```

`stack.py serve` 在 `finally` 中按**进程组**停止两个服务（`npm run start` 会 fork
`next-server`，只杀 npm 会留下监听端口的孤儿进程——已实测并修正）。

## 4. 合成研究数据（fixture）

由 `scripts/grant/e2e/build_fixture.py` 通过**产品自身的 HTTP API** 建立（不直写考核表）：

| 项 | 实际值 |
| --- | --- |
| 批次 | 7 个（`TEST-C01`…`TEST-C07`），每批 7 人 |
| 学生 | 49 名 `TEST测试学生NN`，班级 `TEST 临床医学测试班`，**每人都有 CompetencyProfile** |
| 题本 | `TEST-CASE-A01-UA-V1`、`TEST-CASE-A02-SICCA-V1`（来自 `workpackages/A_cases` 草案，加 `TEST-` 前缀） |
| 审核 | 两位不同教师账号 `test_teacher_a` / `test_teacher_b` 各自独立审核通过后，管理员发布 |
| 分配 | 先冻结题本顺序 `FORM-ORDER-pilot_test-821bc1060883`，再抽整批分配 `CLUSTER-pilot_test-51c049aed0fb` |
| 排考 | 98 场（49 人 × T0/T1），全部 `data_origin=pilot_test` |
| 账号来源 | 教师/管理员仅经 `python -m app.manage_users create-teacher|create-admin`（密码走 stdin） |

> `student_ids` 等完整 fixture 清单：`/tmp/clinpath-e2e/fixture.json`（一次性，不提交）。

## 5. Playwright 实际结果（提交 `375e197`）

```
35 passed, 3 failed, 11 skipped (1.8m)
```

### 5.1 R8.2 九步全流程：9/9 通过

`frontend/tests/e2e/research-flow.spec.ts`（新增）

| # | 步骤 | 结果 | 实际断言到的内容 |
| --- | --- | --- | --- |
| 1 | 管理员创建题本草案 | PASS | 列表出现 `TEST-E2E-*`，状态 `PENDING_REAL_REVIEW`；**未审核时 `POST /forms/{id}/approve` 返回 409** |
| 2 | 两位不同教师独立审核 | PASS | `reviews` 长度 2，`teacher_user_id` 去重后为 2，全部 `approve` |
| 3 | 管理员核验并发布 | PASS | `review_status=APPROVED_FOR_ASSESSMENT`，`published_at` 非空；**已冻结版本再提交审核被拒（403/409）** |
| 4 | 学生 T0 独立考核 | PASS | 五阶段提交 → 提交成功页；页面**无** `参考诊断:`/`总分:数字`；含「不显示正确答案」；学生读 `/api/system/ai-invocations` 得 403 |
| 5 | D2/D3 形成性训练 → D4/D5 个性化 | PASS | 两个训练病例提交成功；结果页 `evaluation-mode` 标注引擎；`/api/student/pathway` 有 `recommended_case`、`recommendation_reason_source="rule"`、`recommended_tasks` 非空；`/api/student/history` ≥2 条且 `evaluation_mode ∈ {ai, rule_fallback}` |
| 6 | 学生 T1（另一题本） | PASS | 等待 T1 窗口开启后五阶段提交；学生读 `/api/assessments/admin/sittings/{id}` 得 **403**（两个时点） |
| 7 | 双教师盲评 | PASS | 盲评详情**不含** `student_id`/`student_name`/`study_group`/`timepoint`/`cohort_code`/`other_score`；两位评分者按同一 `blind_code` 各自评分并锁定；评分者 B 的详情不含 `other_score` |
| 8 | 强制分歧裁决 | PASS | 两位评分者给 20 / 90 分（远超阈值 10）→ 进入裁决队列 → 第三方独立裁决 → 管理员 finalize 返回 `scoring_provenance="adjudicated"`（**不是** `dual_mean`） |
| 9 | 研究数据导出 | PASS | `dataset_status=WORKING_NOT_FROZEN`；每行 `study_student_code` 形如 `S[0-9A-F]{8}`；**不含** `student_id`/`student_name`/`student_no`/`name`；`data_origin=pilot_test`；导出文本不含 `TEST测试学生` 或学号；身份映射是独立的、写入审计的管理员调用 |

### 5.2 既有套件

| 结果 | 用例 |
| --- | --- |
| PASS（35 含 R8.2 九项） | `assessment.spec.ts`（角色门、学生列表不泄露分数、管理员门）、`auth.spec.ts`（登录/刷新/伪造 JWT 五种/退出）、`monitoring.spec.ts`、`research-demo.spec.ts`（合成横幅与 CSV、学生 403、真实导出未变）、`teacher.spec.ts`（页面无 5xx/控制台错误、AI 运行时探测、退出与审计） |
| **FAIL（3）** | `demo-readiness.spec.ts` 三条：`李明 profile …`（缺 `growth-trend-chart`）、`研究数据 preview …`（只 1 名学生，断言要 ≥3）、`学习记录 …`（缺 `history-table`） |
| SKIP（11） | `training.spec.ts` 8 条 + `assessment.spec.ts` 2 条 + `auth.spec.ts` 1 条，均因未设 `E2E_RUN_MUTATING` / `E2E_EXPECT_NO_JWT_SECRET` 等显式开关 |

**3 条失败的原因（如实说明）**：它们断言的是「已有教学历史的演示数据集」——
学生画像趋势图、≥3 名学生的研究导出预览、学生已完成病例的学习记录。
本次一次性库只跑 `app.seed_data`（3 名演示学生、无任何已完成训练），因此这些前置数据不存在。
`scripts/prepare_presentation_data.py` 是重建该演示数据集的正规路径，但它要求**真实模型密钥**
（无密钥时脚本主动停止，避免把规则输出写成 AI 评分），与本轮「刻意无密钥」的隔离验收冲突，
故本轮**未**生成该数据集，也**未**把这三条失败改写为跳过。

## 6. 7 批 × 49 人 × 98 场：不变量实际核验

`scripts/grant/e2e/verify_study_invariants.py` 读取**产品自身记录**（分配记录、sitting 列表、导出），
不重算 fixture。输出 `ALL INVARIANTS HOLD (7/7)`，原文：

| # | 不变量 | 结果 | 实测值 |
| --- | --- | --- | --- |
| I1 | 7 批 × 7 人 = 49 名不同学生 | PASS | `per_cohort` 7 批均为 7；`distinct_students=49` |
| I2 | 每批只属一个研究臂；3 ClinPath + 4 CBL；属 35 种合法整批分配 | PASS | ClinPath `TEST-C02/C04/C07`，CBL `TEST-C01/C03/C05/C06`；`split_batches=[]`；合法分配序号 `[1,3,6]`（共 35） |
| I3 | 题本顺序严格早于整批分配 | PASS | frozen_at `16:16:22.101596` < drawn_at `16:16:22.119085`；`form_order_hash` 与冻结记录一致；`mode=randomized` |
| I4 | 98 场，每 (学生,时点) 恰好一场 | PASS | `sittings=98`，`duplicates=[]`，`timepoints=[T0,T1]` |
| I5 | 每人 T0/T1 用**不同**题本，且符合冻结的 X/Y 顺序 | PASS | 49 人，`mismatches=[]`，`different_forms=true` |
| I6 | 每批内 X/Y 约 4/3 | PASS | 7 批均为 `{3,4}` |
| I7 | 导出只含研究编码，绝不出现 `real_study` | PASS | 98 行，`forbidden_keys=[]`，`origins=['pilot_test']`，49 个不同研究编码 |

### 6.1 核验中发现的一个真实 API 缺口（如实记录）

`GET /api/assessments/admin/allocations` 对 `form_order` 记录**只返回批次列表**，不返回
记录正文（`seed` / `frozen_at` / `assignments`）。因此 I3 的微秒级「先后」比较无法仅凭 API 完成，
脚本改为以**只读**方式打开同一一次性库的 `study_allocations.record_json` 读取。
这是只读核查，不构成写入，但它确实说明：**管理员无法通过 API 复核题本顺序的种子与时间戳**。
该缺口未在本轮修复（属后端 `backend/app/assessment/design.py`，不在本成员改动范围），已记录待办。

## 7. 截图（E2 证据）

16 张，全部由 `frontend/tests/e2e/evidence-screenshots.spec.ts` 在**本次运行**中从真实页面截取，
采集时间 **2026-10-18 16:30:02—16:30:24 UTC**，提交 `375e197`，端口 8400/8401。
逐张说明见 `../E2_platform/SCREENSHOTS_2026-10-18.md`。

注意：截图在功能套件**之后**采集，因此 `12_adjudication_queue_flagged_disagreement.png` 中的
那份分歧已显示为「已裁决」（`待裁决 0`），而不是待裁决状态。这是真实状态，不是摆拍；
该图证明的是「分歧进入了独立裁决队列且裁决后状态正确」，裁决明细页未单独截图。

已逐张人工核对其中 5 张（03 分配冻结、02 批次清单、09 盲评队列、14 提交成功页、15b 阶段作答、
12 裁决队列），确认页面内容与文件名描述一致；其余截图由同一脚本同一运行产出。

## 8. 本轮**未**执行 / 未覆盖的事项（不得视为通过）

| 项 | 状态 | 原因 |
| --- | --- | --- |
| `training.spec.ts` 8 条（含五阶段训练、AI 追问、教师复核、去标识化） | **未执行**（skipped） | 需 `E2E_RUN_MUTATING=1`；本轮聚焦考核/研究流程 |
| `assessment.spec.ts` 的「学生完整考试」与「盲评」两条 | **未执行**（skipped） | 同上；其覆盖已由 `research-flow.spec.ts` 步骤 4/7 实测 |
| `demo-readiness.spec.ts` 3 条 | **失败** | 缺预置演示数据集（需真实模型密钥重建） |
| 真实 AI 评分 / AI 追问 | **未验证** | 本轮刻意无密钥；产品降级路径已实测（`rule_fallback`） |
| 断网恢复（真实断网） | **未验证** | 仅覆盖草稿服务器保存 + 刷新恢复（步骤 4 内 `立即保存草稿` → reload） |
| 前端 `npm run typecheck` / `npm run lint` / `npm run build` | **全部通过** | `typecheck` 与 `lint --max-warnings=0` 在本提交上实测无输出错误；build 在 `run_full_acceptance.sh` 内成功 |
| 生产部署与部署后浏览器验收 | **未执行** | 按 R8.4，本轮不部署 |
| 真实教师审核 / 真实学生数据 / 教学效果 | **不存在** | 全部为 TEST 账号与合成数据 |
| 截图的使用授权 | **待办** | 需院系/单位确认可用于申报材料 |

## 9. 复现方式（他人可重跑）

```bash
cd <worktree>            # 任意独立 worktree，勿在生产主检出内运行
./scripts/grant/e2e/run_full_acceptance.sh <label>
```

要求：`uv`、`node`/`npm`、`npx playwright`（chromium 已安装）。脚本会在以下任一情况下**拒绝运行**：
目标端口是 8100/8101；端口已被占用；`INTERNAL_API_BASE_URL` 不是回环或指向生产端口；
数据库不在 `/tmp` 下；一次性库已存在却未要求 `--reset`。
