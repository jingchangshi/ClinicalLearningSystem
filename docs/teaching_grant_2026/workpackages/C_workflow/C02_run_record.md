# C02 · 真实运行记录（教学闭环走查）

> 本文件记录**一次真实发生的运行**：2026-10-18 UTC 在验证栈上，以 `student1` 完成
> 「SLE基础病例」五阶段作答，随后由 `verify_teacher` 复核并记录干预。
> 所有数字抄自 `C02_evidence/` 下保存的原始 HTTP 响应，没有一处是估算。
>
> **边界**：这证明系统按设计运行、数据可追溯，**不证明教学有效性**。样本 n=1，
> 且本次评分走的是规则降级路径。

## 1. 运行环境与版本

| 项目 | 值 | 来源 |
| --- | --- | --- |
| 环境 | `development`（**验证栈，非生产**） | `C02_evidence/22_system_version.json` |
| 后端 | `http://127.0.0.1:8201` | 进程 |
| 前端 | `http://127.0.0.1:8202` | 进程 |
| 数据库 | `sqlite:////tmp/clinpath-demo-verify/verify.db`（一次性） | 启动参数 |
| **运行版本 SHA** | `1d4ef4823c75fb9d89a7aec734b8b84d0bfa5c41`（短 `1d4ef482`），`git_dirty=true` | `GET /api/system/version` |
| 后端源码指纹 | `v1:ff017794a5c4` | 同上 |
| Schema revision | `20260915_06` | 同上 |
| 后端运行时 | `python 3.11` | 同上 |
| 前端构建 SHA | `1d4ef48-dirty` | `/teacher/runtime` 页面 |
| 生产服务 | **未触碰**（`8100/8101`、`backend/clinical_learning.db`） | — |

> 说明：`git_dirty=true` 是因为验证栈运行的工作区包含尚未提交的工作包改动。
> 该 SHA 对应的是**开发/验证栈**，不等于生产 `clinpath.1031989.xyz` 上运行的版本。

## 2. 账号与角色

| 角色 | 账号 | 说明 |
| --- | --- | --- |
| 学生 | `student1`（user id 1 / student_id 1，李明，202601001，临床医学2023级1班） | 只有本人会话的访问权 |
| 教师 | `verify_teacher`（user id 4 / teacher_id 2，验收教师，风湿免疫科） | 教师角色；本记录中的复核与干预均由该账号完成 |

密码不写入本文件，也不出现在任何证据文件里。证据中的 cookie 已丢弃
（`curl` 的 cookie jar 只存在于 `/tmp`，未复制进仓库）。

## 3. 病例与会话

| 项目 | 值 |
| --- | --- |
| 病例 ID | `1` |
| 病例标题 | `SLE基础病例` |
| 疾病分类 / 难度 | 系统性红斑狼疮 / 基础 |
| 主诉 | 女性，21岁，反复发热、面部红斑、关节痛1个月。 |
| 会话 ID | `1` |
| 会话开始 | `2026-10-18T09:28:48.698640` |
| 会话完成 | `2026-10-18T09:29:29.532586` |
| 状态 | `completed` |

## 4. 逐步骤记录（精确时间戳 · 数据来源 · 模型/评价模式）

时间戳全部取自服务端返回的 `created_at`，UTC。

| # | 时刻（UTC） | 环节 | 角色 | 接口 | 实际结果 | 数据来源 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `09:28:48` | 登录 | student1 | `POST /api/auth/login` | 返回 `role=student`、`student_id=1`；写 HttpOnly cookie | 真实 API |
| 2 | `09:28:48.698640` | 开新会话 | student1 | `POST /api/sessions/start` `{case_id:1}` | `session_id=1`，`status=in_progress` | 真实 API |
| 3 | `09:28:48.851830` | S1 关键信息提取 | student1 | `POST /api/sessions/1/answers` | 保存成功（见证据 03） | 真实 API（学生输入） |
| 4 | `09:28:48.896516` | S2 初步诊断及依据 | student1 | 同上 | 保存成功（04） | 真实 API |
| 5 | `09:28:48.939058` | S3 鉴别诊断 | student1 | 同上 | 保存成功（05） | 真实 API |
| 6 | `09:28:48.986166` | S4 进一步检查 | student1 | 同上 | 保存成功（06） | 真实 API |
| 7 | `09:28:49.029260` | S5 治疗方案 | student1 | 同上 | 保存成功（07） | 真实 API |
| 8 | `09:28:50.410250` | S3 AI 导师追问 | student1 | `POST /api/sessions/1/tutor` | 返回 1 条 tutor 气泡 + 规则推理状态 `completion_state=in_progress`、`missing_reasoning_elements=[AOSD, Still, MCTD, APS, 血管炎]` | **AI**：`task_type=tutor_question`，`provider=deepseek`，`model=deepseek-flash`，`success=true`，`latency_ms=1330` |
| 9 | `09:29:29.520696` | 提交并评分 | student1 | `POST /api/sessions/1/submit` | `score_id=1`，`total_score=72.6`，`evaluation_mode=rule_fallback`，`degraded=true` | **规则**（AI 超时降级，见下） |
| 10 | `09:29:29.532586` | 会话完成落库 | 系统 | — | `status=completed` | 真实 API |
| 11 | `09:29:31.165006` | 学习路径解释 | 系统（后台） | `ai_enrichment` | 生成并缓存推荐理由 | **AI**：`task_type=recommendation_explanation`，`success=true`，`latency_ms=1606` |
| 12 | `09:29:32.702432` | 班级洞察刷新 | 系统（后台） | `ai_enrichment` | 生成并缓存班级洞察 | **AI**：`task_type=teacher_insight`，`success=true`，`latency_ms=1523` |
| 13 | `09:33:04.314929` | 教师评分复核 | verify_teacher | `POST /api/teacher/reviews` | `ai_score=72.6` → `teacher_score=73.7`，`agreement_delta=1.1`，六维确认分保留 | 真实 API（教师操作） |
| 14 | `09:36:12.325184` | 记录教学干预 | verify_teacher | `POST /api/teacher/interventions` | `id=1`，`intervention_type=micro_lesson`，目标能力 `evidence_based_medicine` | 真实 API（教师操作） |

## 5. 评价模式（按 API 原样报告）

### 5.1 本次评分 `POST /api/sessions/1/submit`

```json
{
  "total_score": 72.6,
  "evaluation_mode": "rule_fallback",
  "provider": null,
  "model": null,
  "rule_score": 72.6,
  "ai_score": null,
  "degraded": true,
  "evaluator_version": "hybrid-v1",
  "prompt_version": "case-evaluation-v1",
  "rubric_version": "case-rubric-v1",
  "teacher_confirmed_score": null
}
```

**结论：这次评分不是 AI 评分。** 前端把 `evaluation_mode=rule_fallback` + `degraded=true`
显示为「规则降级评价（AI 当前不可用）」，不会伪装成 AI。

降级原因（`GET /api/system/ai-invocations`，审计事件 id 2）：

```json
{
  "task_type": "case_evaluation",
  "provider": "deepseek",
  "model": "deepseek-flash",
  "prompt_version": "case-evaluation-v1",
  "evidence_ref": "case_session:1",
  "session_id": 1,
  "student_id": 1,
  "calls": 4,
  "failures": 4,
  "success": false,
  "fallback_used": true,
  "latency_ms": 37581,
  "error_type": "Timeout",
  "created_at": "2026-10-18T09:29:29.520696"
}
```

即：`LLM_TIMEOUT_SECONDS=12`、`LLM_MAX_RETRIES=2` → 4 次调用全部 `Timeout`，
累计 37.6 秒后按规则评分。审计只记录元数据与证据引用，**不含 prompt / 响应正文**。

### 5.2 同一会话中成功的 AI 调用

| task_type | provider / model | latency | success | evidence_ref |
| --- | --- | --- | --- | --- |
| `tutor_question` | deepseek / deepseek-flash | 1330 ms | true | `case_session:1:step:differential_diagnosis` |
| `recommendation_explanation` | deepseek / deepseek-flash | 1606 ms | true | `learning_pathway:student:1` |
| `teacher_insight` | deepseek / deepseek-flash | 1523 ms | true | `teacher_dashboard` |

### 5.3 `GET /api/system/ai-status`（运行结束时）

```json
{
  "configured": true,
  "provider": "deepseek",
  "model": "deepseek-flash",
  "base_url_host": "api.deepseek.com",
  "last_call_mode": "ai",
  "last_error_type": "Timeout",
  "calls": 6,
  "failures": 1,
  "fallbacks": 1,
  "timeout_seconds": 12.0,
  "max_retries": 2
}
```

> 注意 `last_error_type=Timeout` 与 `calls/failures/fallbacks = 6/1/1` 并存是**正确的**：
> 6 次调用事件中 1 个能力（case_evaluation）失败并回退，其余能力成功。
> 但 `/teacher/runtime` 把这一行的标签写成 `LAST ERROR TYPE`，容易被念成
> 「最近一次调用失败」——见 `C03_page_gaps.md` G-03。

## 6. 教师复核的溯源（证明结论 4：保留 provenance）

`POST /api/teacher/reviews` 的实际返回（`C02_evidence/16_teacher_review_created.json`）：

```json
{
  "id": 1,
  "evidence_event_id": 1,
  "ai_score": 72.6,
  "teacher_score": 73.7,
  "agreement_delta": 1.1,
  "confirmed_dimensions": {
    "medical_knowledge": 91.0,
    "key_information": 74.0,
    "differential_diagnosis": 75.0,
    "evidence_integration": 70.0,
    "clinical_decision": 67.0,
    "evidence_based_medicine": 65.0
  },
  "projector_version": "v1",
  "created_at": "2026-10-18T09:33:04.314929"
}
```

- 原始 AI/规则分 `72.6` 保留在 `ai_score`，未被覆盖
- 教师分 `73.7` 由六个确认维度经 `confirmed_total` 计算，不是直接写一个总分
- `agreement_delta=1.1` 让复核分歧可量化
- 复核另写一条 `teacher_score_confirmed` 证据事件并重新投影能力（证据 23 可对照）

> 声明：本次复核的 `comment` 与六维分数是**验收账号在验证栈上的操作样例**，
> 目的是证明接口与溯源链可用，**不是真实临床教师的评审意见**。真实观察见
> `C04_screenplay.md` 的「待用户/真实教师补入」小节。

## 7. 原始证据清单（`C02_evidence/`）

| 文件 | 内容 |
| --- | --- |
| `00_timeline.txt` | 逐步 UTC 时间线 |
| `01_login_student.json` | 登录返回（仅 user 对象，无 token/cookie） |
| `02_session_start.json` | `POST /api/sessions/start` 返回 |
| `03_answer_S1.json` … `07_answer_S5.json` | 五个阶段的保存结果 |
| `08_tutor_S3.json` | AI 追问 + 规则推理状态 |
| `09_submit.json` | 提交返回（分数摘要 + 推荐） |
| `10_result.json` | `GET /api/sessions/1/result`（评分、六维明细） |
| `11_student_history.json` | 学生学习记录 |
| `12_student_pathway.json` | 学习路径 |
| `13_student_dashboard.json` | 学生首页 |
| `14_teacher_reviewable_evidence.json` | 教师待复核证据 |
| `15_teacher_dashboard.json` | 教师驾驶舱数据 |
| `16_teacher_review_created.json` | 复核创建返回 |
| `17_teacher_reviews.json` | 复核记录列表 |
| `18_teacher_intervention_created.json` | 干预创建返回 |
| `19_teacher_interventions.json` | 干预记录列表 |
| `20_ai_invocations.json` | AI 调用审计（按能力 + 最近事件） |
| `21_ai_status.json` | AI 运行时状态 |
| `22_system_version.json` | 版本与 schema |
| `23_result_after_review.json` | 复核后的结果页数据（含 `teacher_confirmed_score=73.7`） |
| `24_playwright_research_demo.txt` | 自动化 E2E 实跑输出 |

所有证据文件已人工检查：不含 cookie、不含密码、不含 API Key、不含 Authorization 头、
不含 prompt 或模型响应正文。

## 8. 自动化端到端检查

新增 `frontend/tests/e2e/research-demo.spec.ts`，覆盖：

1. 教师打开 `/teacher/research-demo`，看到合成横幅与「下载 SYNTHETIC CSV」，并校验**下载的
   CSV 本身**带 `SYNTHETIC_DEMO_NOT_REAL_STUDENTS` 与「模拟数据，不代表真实教学成效」
2. 学生访问同一路由被重定向离开，且 `summary` / `students` / `export.csv` 三个接口均返回 **403**
3. 真实导出页 `/teacher/research-export` 仍显示「匿名化研究数据」与自己的 CSV 按钮，
   且**不**带合成横幅

### 实跑命令与真实输出

```bash
cd frontend
E2E_BASE_URL=http://127.0.0.1:8202 \
E2E_TEACHER_USERNAME=verify_teacher \
E2E_TEACHER_PASSWORD=... \
E2E_STUDENT_USERNAME=student1 \
E2E_STUDENT_PASSWORD=... \
npx playwright test tests/e2e/research-demo.spec.ts
```

```text
Running 3 tests using 1 worker

  ✓  1 [chromium] › tests/e2e/research-demo.spec.ts:33:7 › synthetic teaching-research demo › a teacher sees the synthetic banner and downloads the SYNTHETIC CSV (2.9s)
  ✓  2 [chromium] › tests/e2e/research-demo.spec.ts:83:7 › synthetic teaching-research demo › a student is redirected away and the API answers 403 (1.2s)
  ✓  3 [chromium] › tests/e2e/research-demo.spec.ts:106:7 › synthetic teaching-research demo › the real research export is unchanged and still offers its own CSV (1.6s)

  3 passed (7.4s)
```

同时跑既有规格 `teacher.spec.ts`：3/3 通过；`demo-readiness.spec.ts`：5/6 通过，
唯一失败项是**数据前置条件**（该断言要求演示库至少有 3 名学生 / 3 个模块 / 3 个日期，
本次一次性验证库只有 3 名学生、1 条训练记录），与本次改动无关。

> **再次声明**：E2E 证明的是「页面能打开、权限会拒绝、文件能下载」。
> 它**不能**证明教学效果，也不应作为教学有效性的证据引用。

## 9. 本次运行未覆盖的部分

| 项目 | 状态 |
| --- | --- |
| AI 评分成功路径（`evaluation_mode="ai"`） | **未取得**（本次 4 次调用均超时） |
| SP 问诊 / 技能站 / 知识测验 / 指南 PICO 会话 | 未开新会话 |
| 生产环境同一走查 | 未执行（约束禁止） |
| 真实学生参与 | 未发生；`student1` 是种子演示账号 |
| 真实教师评审意见 | 未发生；`verify_teacher` 是验收账号 |
