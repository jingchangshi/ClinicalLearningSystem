# ClinPath 架构事实源（ARCH.md）

本文档描述**当前代码真实运行的系统**，以及必须遵守的架构不变量。
如果代码与本文不一致，以代码为准，并立即修正本文。
`docs/goal.md` 是历史任务书，不是架构事实源。

## 1. 产品目标与非目标

### Goal

- 临床推理训练（病例 5 阶段推理链）
- formative feedback（形成性反馈，不是终局评分）
- 多模态学习活动（知识 / 技能 / 指南 / SP / 病例）
- longitudinal learning evidence（可追溯的学习证据）
- competency profile（能力画像）
- adaptive learning pathway（自适应学习路径）
- teacher-in-the-loop（教师确认与复核）
- research / audit provenance（研究与审计溯源）

### Non-goal

- 不作为患者临床诊疗工具，不给出真实患者诊疗决策建议
- 不允许未经教师验证的 AI 评分成为最终教育评价
- 不把 LLM 输出当数据库事实
- 不以 LLM 直接替代结构化 learner model

## 2. Runtime architecture

```text
                       Browser
                          |
                          v
                Next.js 16  :8101
                - UI / route groups (main) (demo)
                - AuthProvider (client, /api/auth/me)
                - proxy.ts  (coarse route protection)
                - /api/* rewrite -> INTERNAL_API_BASE_URL
                          |
                       same-origin
                          |
                          v
                 FastAPI  :8100 (internal port)
                 - /api/auth
                 - /api/sessions, /api/student/*   (training)
                 - /api/teacher/*                  (teaching)
                 - /api/system/*  (version / ai-status / ai-probe / reasoning-steps)
                 - services: scoring, competency, evidence, recommendation, LLM
                          |
                          v
                  SQLite (backend/clinical_learning.db)
                          +
                  OpenAI-compatible LLM provider
```

### 生产部署（systemd user units）

```text
~/.config/systemd/user/clinical-backend.service   -> scripts/start_backend_8100.sh
~/.config/systemd/user/clinical-frontend.service  -> scripts/start_frontend_8101.sh

EnvironmentFile clinical-backend.service  = ~/.config/clinpath/backend.env
    CLINPATH_ENV / JWT_SECRET / COOKIE_SECURE / LLM_* (model credentials live only here)
EnvironmentFile clinical-frontend.service = ~/.config/clinpath/frontend.env
    JWT_SECRET (same value as the backend) / NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS /
    NEXT_PUBLIC_ALLOW_PUBLIC_REGISTRATION

Both units must sign/verify cookies with the same JWT_SECRET. The web tier never
receives model credentials; `scripts/verify_deploy.sh` compares only the SHA-256
prefix of the two secrets and prints MATCH/MISMATCH, never a value.
`scripts/start_frontend_8101.sh` refuses to start when JWT_SECRET is empty.
```

`scripts/start_backend_8100.sh` 在 `alembic upgrade head` **之前**比较 `alembic current`
与 `alembic heads`；只要有待执行迁移，就先调用 `scripts/backup_db.sh` 生成带时间戳的
SQLite 备份（sqlite3 backup API，兼容 WAL），然后才升级 schema。

## 3. Authentication architecture

```text
POST /api/auth/login
        |
        v
HttpOnly access_token cookie (JWT HS256, JWT_SECRET, 12h, SameSite=Lax, COOKIE_SECURE)
        |
        v
GET /api/auth/me
        |
        v
frontend AuthProvider (client state + role correction)
        |
        v
role-based navigation
```

不变量：

- **后端 JWT 校验是权限唯一事实源**：`app/auth.py` 的 `get_current_user` /
  `require_role` / `require_student_access` / `student_id_from_user`。
- `frontend/proxy.ts` 只做粗粒度路由保护，并且**必须先用 `JWT_SECRET` 验证 HS256 签名**
  再读取 `role`；未签名、签名错误、已过期、`alg` 非 HS256 的 token 一律视为未认证。
- 角色不匹配不经过 `/login`，直接跳到该角色自己的 dashboard，避免 redirect loop。
- `JWT_SECRET` 缺失时前端**fail closed**，不存在「只检查 cookie 是否存在」这种降级：
  没有 cookie 的受保护路由照常跳 `/login`；**携带 cookie 的受保护请求直接返回**
  `503 Deployment misconfigured: JWT_SECRET is required`。proxy 绝不解码、绝不信任任何
  未验证声明（`role` 也不行），也绝不因为配置缺失把未验证请求放行到页面。
  `scripts/start_frontend_8101.sh` 在 `JWT_SECRET` 为空时拒绝启动，让配置错误在启动阶段暴露。
  该行为由 `E2E_EXPECT_NO_JWT_SECRET=1` 的 E2E 与 `frontend/proxy.ts` 共同固定。
- 公开注册默认关闭（见 §9）。教师 / 管理员账号**从不**由 seed 创建，只能用服务器端
  `python -m app.manage_users create-teacher|create-admin` 开通；`audit-accounts` 用于复查
  账号（含 legacy 名称、未关联 admin、重复学生登录等标记，且从不输出任何口令材料）。

## 4. Deployment truth（运行版本可见性）

生产环境必须能在 30 秒内回答「浏览器里跑的是哪一版」：

- `GET /api/system/version` 返回 `app`、`environment`、`git_sha` / `git_sha_short`、
  `schema_revision`（alembic head）、`backend_runtime`、`ai_configured`。
  绝不返回 key、文件路径或环境变量内容。
- 前端 build 时由 `scripts/start_frontend_8101.sh` 注入 `NEXT_PUBLIC_BUILD_SHA`
  （来自 `git rev-parse --short HEAD`）。
- 教师页面 `/teacher/runtime` 同时展示 backend SHA、frontend build SHA、schema revision、
  environment、backend source fingerprint 与 AI runtime 状态。
- `backend_source_fingerprint` 是 `backend/app/**` 与 `backend/alembic/versions/*.py`
  的 SHA-256 内容指纹（`app/core/source_fingerprint.py`）。未提交的工作树也能被证明：
  本地 `compute_source_fingerprint()` 与线上返回值一致，就说明浏览器背后跑的就是当前源码。
- `scripts/verify_deploy.sh` 把上述判断固化为一条只读命令：
  git HEAD / 未提交文件数 / 本地指纹 / 线上指纹 / schema revision / systemd 状态 / 公网入口。

排查「源码与线上行为不一致」时：先对比 `/teacher/runtime` 的两个 SHA 与 `git rev-parse HEAD`，
或直接跑 `./scripts/verify_deploy.sh`；再怀疑业务逻辑。

## 5. AI runtime 与 provenance

### 5.1 唯一 canonical 配置协议

```text
LLM_PROVIDER         deepseek | openai | openai-compatible
LLM_API_KEY
LLM_BASE_URL
LLM_MODEL            deepseek 默认 deepseek-flash
LLM_TIMEOUT_SECONDS  default 12（生产实测值见 5.1.1）
LLM_MAX_RETRIES      default 2
LLM_THINKING_ENABLED default true
LLM_REASONING_EFFORT default high（none/low/high/max，兼容 low-high 之外的别名）
LLM_MAX_TOKENS       default 8192
```

- 兼容别名（deprecated）：`DEEPSEEK_*`、`OPENAI_*`。
- 解析顺序：canonical 名优先，其次 provider 别名；唯一实现位于 `app/core/llm_config.py`。
- `provider` 不再硬编码；未显式设置时由所用变量名 / base_url host 推断。
- `llm_config_summary()` 只输出非敏感诊断信息（provider、model、base_url host、来源变量名、
  timeout/retries、thinking/effort/max_tokens、仍在使用的 deprecated 变量），用于日志与
  教师 runtime 卡片。思考开关只进入服务端配置，不下发给前端。

### 5.1.1 DeepSeek 官方接口对齐（当前契约）

DeepSeek 已下线 `deepseek-chat` / `deepseek-reasoner` 这一组模型名；生产默认模型是
`deepseek-flash`（OpenAI 兼容的 Chat Completions 接口）：

```text
base URL   https://api.deepseek.com
endpoint   POST /chat/completions          （Authorization: Bearer <key>）
model      deepseek-flash                  （deepseek-v4-pro 可显式选择）
thinking   extra_body={"thinking": {"type": "enabled"|"disabled"}}
effort     reasoning_effort=<none|low|high|max>
JSON        response_format={"type": "json_object"}
```

实现只落在传输层（`app/services/llm_service.py` 的 `build_chat_kwargs()`），scoring、
tutor、recommendation、route 里没有 provider 分支：

- **Thinking Mode 显式声明**：不再依赖 provider 的隐式默认值。开启时同时发送
  `thinking.type=enabled` 与 `reasoning_effort`；`LLM_REASONING_EFFORT=none` 表示明确关闭。
- **温度**：Thinking Mode 忽略 `temperature`（官方文档：不报错但无效），因此开启思考时
  **不发送** `temperature`；非思考模式或其它 OpenAI 兼容 provider 仍按原语义发送。
- **max_tokens**：始终显式发送（默认 8192）。官方默认值是「非思考 8K / 思考 64K」，
  把输出长度交给隐式默认值会让 JSON 结果在中途被截断而无法归因。这个默认值不是猜的：
  用真实评测 prompt 打线上接口实测（每次一次调用），Thinking Mode 会在 `reasoning_content`
  上先花掉约 2.9k–3.3k tokens（reasoning 约 8.8k 字符），正文再占约 0.7k–1.3k tokens；
  配置 4096 时出现过 `finish_reason=length` + `content` 为空（即降级路径），8192 稳定返回
  合法 JSON。同一批实测的单次耗时约 17–31 秒，因此生产把 `LLM_TIMEOUT_SECONDS` 设为 60、
  `LLM_MAX_RETRIES` 设为 1：单次请求最坏约 2 次尝试，既容得下偶发的空正文重试，
  又不会让用户请求无限期挂住。
- **思考轨迹不外泄**：只读取 `choices[0].message.content`；`reasoning_content`
  不落库、不回传学生、不写审计、不进日志。`ai_invocations` 依旧只有元数据。
- **探针**：`/api/system/ai-probe` 只回答「能不能连通」，因此显式
  `thinking=disabled` + 极小 `max_tokens` + 固定提示词，且只返回
  `reachable / latency_ms / provider / model / error_type`，绝不返回 provider 正文。
- **JSON 契约**：所有 JSON 任务都发送 `response_format={"type": "json_object"}`，prompt
  中显式出现 `JSON` 并给出目标 schema；空正文与非法 JSON 一律视为 provider 失败，
  走重试/回退，绝不当作有效 AI 评价。
- **重试语义**：400/401/402/422 属永久失败，不重试直接降级；429/5xx 与网络超时按
  `LLM_MAX_RETRIES` 有界重试（短退避）。降级契约不变：
  `rule_fallback` + `degraded=true`，审计如实记录 `calls/failures/success/fallback_used/
  error_type/latency_ms`。

### 5.2 Runtime observability

```text
GET  /api/system/ai-status   teacher/admin only
POST /api/system/ai-probe    teacher/admin only, rate limited
```

返回 `configured / provider / model / reachable / last_probe_at / latency / last_error_type /
last_call_mode / calls / failures / fallbacks`。`app/core/ai_runtime.py` 保存进程内状态；
`llm_service` 在每次成功调用或降级时记录 `ai` / `rule_fallback`。
永不返回 API key、Authorization header 或 provider 原始响应体。

### 5.3 调用契约（AI Invocation contract）

```text
task_type            case_evaluation | coach_question | sp_patient | sp_evaluation |
                     guideline_rationale | recommendation_explanation |
                     teacher_insight | case_generation
provider, model
prompt_version, rubric_version, evaluator_version
input/evidence ref   指向 session / evidence id，而不是复制原始数据
latency, success/failure
fallback_used        degraded
created_at
```

落库实现：

- `scores` 表保存 case evaluation 的完整 provenance（`evaluation_mode`、`provider`、
  `model`、`prompt_version`、`rubric_version`、`evaluator_version`、`rule_score`、
  `ai_score`、`degraded`、`evaluation_detail_json`）。
- `ai_invocations` 表统一记录**其它所有 AI 能力**（`case_evaluation`、`tutor_question`、
  `sp_patient`、`sp_evaluation`、`guideline_rationale`、`recommendation_explanation`、
  `teacher_insight`、`case_generation`、`skill_feedback`）：一次任务一个事件，
  含 `task_type / provider / model / prompt_version / evidence_ref / session_id /
  student_id / calls / failures / success / fallback_used / latency_ms / error_type /
  created_at`。
- 审计**从不**写入 prompt、响应正文或隐藏答案，只写引用与机器事实（避免 PHI 与 hidden
  answer 进入日志表）；写入失败只记 warning，绝不影响训练请求。
- `GET /api/system/ai-invocations`（teacher/admin）返回最近事件与按 task_type 的汇总，
  在 `/teacher/runtime` 页面展示。

### 5.4 双路径必须可证明

- AI 路径：`evaluation_mode = ai`、`degraded = false`、`provider/model` 非空。
- 降级路径：`evaluation_mode = rule_fallback`、`degraded = true`、`ai_score = null`。
- 两条路径返回**同样结构**的 `evaluation_detail`：每个维度包含
  `score / confidence / evidence / missing_points / feedback / source`，
  因此结果页永远能回答「为什么是这个分数」。
- Prompt 载荷统一经 `llm_service.prompt_json()`（`json.dumps(..., default=str)`）序列化，
  避免 datetime / Decimal 之类对象把请求打成 500
  （历史事故：`/api/student/pathway` 500「Object of type datetime is not JSON serializable」）。

### 5.5 读路径不变式与 task-aware 策略（本阶段新增）

**不变式：普通 GET/读接口不同步依赖外部模型。**

```text
GET/read endpoint
        ↓
数据库 + 确定性逻辑（必需）
        ↓
立刻可用响应（规则理由永远齐全）
        ↓
可选：*仍然有效* 的缓存 AI 解释（有就换上更好的措辞）
```

外部模型慢、限流、不可用或昂贵时，页面不得因此变慢或不可用。实现落点：

- `recommendation_service` 只做确定性规划：`LearnerGap → Candidate Generator →
  Constraint Filter → Ranker`；`choose_recommendation()` / `build_learning_pathway()`
  **不含任何模型调用**，每项任务自带规则理由（`REASON_TEMPLATES`）。
- `app/services/ai_enrichment.py` 负责「生成 + 缓存 + 失效」：
  `ai_enrichments` 表按 `(kind, cache_key)` 存一条 payload，并记录
  `source_fingerprint`。**只有 fingerprint 仍然匹配时才使用缓存**，因此过期的解释
  永远不会被当成当前解释展示。
- fingerprint = 学习者证据（`competency_profile.updated_at` + 最新
  `learning_evidence_events.id`）的摘要；班级洞察用全库最新证据 id + 计数。
  证据一变化（完成病例 / 知识 / 技能 / SP / 指南 / 教师确认复核），缓存自动失效，
  页面退回规则理由，而不是显示旧解释。
- 生成时机：学习事件提交并 `commit` 之后由 `ai_enrichment.schedule_student()` 入队；
  教师可显式 `POST /api/teacher/dashboard/refresh-insight` 生成班级洞察。
  **GET 从不触发生成**（`tests/test_read_paths_never_call_provider.py` 守住）。
- 读缓存**不写假的 `ai_invocations`**：只有真正发生 provider 调用时才产生审计事件。
- 耐久性区别：核心评估状态（score / evidence / competency）在请求事务内同步写入，
  丢失即损坏；AI 解释是可选、可再生成的，因此可以交给尽力而为的后台线程，
  丢了只是少一句更好的措辞。`CLINPATH_AI_ENRICHMENT=off` 可立即停止这类调用。

**task-aware 策略**：`backend/app/core/ai_policy.py` 是唯一声明处，
`AI_TASK_POLICIES[task_type]` 描述每个任务的 `thinking / reasoning_effort /
max_tokens / temperature / timeout / retries`；transport 仍然 provider-aware。
路由与 service 只表达任务语义，**不构造 provider 原始载荷**
（`tests/test_ai_policy.py` 断言只有 `llm_service` 出现 `extra_body`）。

策略值来自 `backend/tools/ai_benchmark.py` 的实测比较，而不是直觉：

```text
task                       thinking   effort   max_tokens  timeout   依据
case_evaluation            enabled    high     8192        60s       正确性优先；关闭 thinking 实测快 4.6×，
                                                                     但属于教学判定，未在证据足够前改动
case_generation            enabled    high     8192        60s       低频、教师侧；实测方差大（14–29s）
tutor_question             disabled   —        600         25s       实测 p50 963ms vs thinking 4672ms
sp_patient                 disabled   —        600         25s       实测 p50 1218ms vs thinking 3252ms
sp_evaluation              disabled   —        2600        40s       实测 1525ms vs 4504ms（结构化 JSON）
guideline_rationale        disabled   —        1200        30s       实测 1286ms vs 5717ms
skill_feedback             disabled   —        700         25s       实测 1295ms vs 2694ms
recommendation_explanation disabled   —        900         25s       实测 1204ms vs 2889ms（路径页解释）
teacher_insight            disabled   —        600         25s       实测 1650ms vs 3967ms
ai_probe                   disabled   —        16          15s       「能不能连通」，不需要推理
```

## 6. Learning integrity（一次训练只算一次）

- `student_answers` 有唯一约束 `uq_student_answers_session_step`：`(session_id, step)`。
- `POST /api/sessions/{id}/answers` 是 **upsert**：同一步骤重复保存只更新文本与 `updated_at`。
- 必需推理步骤的唯一事实源是 `app/core/reasoning_steps.py`，并通过
  `GET /api/system/reasoning-steps` 提供给前端，前后端不会各自维护一份列表。
- `POST /api/sessions/{id}/submit` 校验所有必需步骤存在且非空，否则返回结构化
  `400 {"detail": "...", "missing_steps": [...]}`。
- 提交幂等：`scores` 表对 `session_id` 唯一；重复提交返回既有分数，不重复计入 competency。
- 已完成 session 不允许再改答案（409），也不允许重新计分。
- 前端 `CaseTrainingClient` 追踪 dirty 状态：提交前先保存所有未保存的 textarea；
  未作答或保存失败会给出结构化提示；提供 saving / saved / error 反馈，并在离开页面前提醒。

### 6.1 Step-level formative tutor（AI Tutor v1）

每个推理步骤都有独立的 tutor 状态与对话，而不是一条可被覆盖的 AIMessage：

```text
step, dimension
evidence_already_covered / missing_reasoning_elements
misconceptions / safety_gap
asked_about
turn_count / student_turn_count / max_turns
completion_state = not_started | in_progress | coverage_sufficient | max_turns_reached
```

- 状态由学生自己的文字确定性推导（`app/services/tutor_service.py` 复用评分关键词表），
  LLM 只负责把状态转成一个聚焦问题。
- Prompt 硬约束：不给标准诊断、不给标准治疗、不透露 rubric、每次只问一个问题、
  优先问「为什么」，并要求证据与反证、鉴别排序、验证策略与安全性。
- 泄漏防护（`leaks_hidden_answer()`，两级）：
  - 长片段：treatment plan / rubric / 鉴别诊断条目在问题中逐字出现（≥12 字）→ 拒绝。
  - 短标签：标准诊断按去标点归一化后逐字出现 → 拒绝，除非学生自己的回答里已经写出该诊断
    （此时导师引用它不构成新信息）。因此「你的诊断应该是系统性红斑狼疮」会被拒，
    而「是否需要先排除感染？依据是什么？」这类合法提问不受影响。
  命中即改用规则问题（规则问题同样不泄露答案），并记录 warning；
  发往 provider 的病例上下文只包含 `_visible_case()` 允许的字段。
- 有界：`MAX_TUTOR_TURNS_PER_STEP`（默认 6）与 `MAX_COACH_TURNS_PER_SESSION`（默认 20）。
- 会话上下文：学生回复与保存的回答一起参与状态分析，因此覆盖充分时会自动停止追问。
- API：`POST /api/sessions/{id}/tutor`（可选 `message`）、
  `GET /api/sessions/{id}/tutor?step=...`；`POST /api/sessions/{id}/coach` 保留为
  单问题兼容入口，同样写入 tutor 记录。
- 前端：训练页每个步骤内呈现完整对话（导师/学生气泡）、缺失要素与安全提示、
  以及「继续追问」输入框；写入回答并保存才会进入评分。

## 7. Learner model（当前实现 vs 目标设计）

### Current（MVP，已实现，可审计）

```text
weighted running competency projection
new = old * 0.7 + module_score * 0.3      UPDATE_WEIGHT = 0.3
```

- 每次训练写入不可变 `LearningEvidenceEvent`（含 `competency_updates_json` 与
  `evidence_payload_json`）。
- `competency_projector.reproject_competencies()` 按时间顺序重放全部 evidence；
  教师确认（`TeacherScoreReview.confirmed_dimensions_json`）会替换对应维度的 module_score。
- 这是可审计的投影，**不是** advanced digital twin，不要这样包装。

### Target（尚未实现）

未来版本应考虑 `score`、`confidence`、`evidence count`、`task difficulty`、`recency`、
`source module`、teacher-confirmed evidence、AI-vs-rule source。
在 evidence 正确之前不引入更复杂的算法。

## 8. Adaptive recommendation

当前实现是 **rule-based planner + LLM explanation**：

```text
competency profile
   -> thresholds (determine_pathway_stage)
   -> weakest abilities
   -> candidate task rules (knowledge / skill / case / guideline / sp)
   -> case candidate ranking on machine-readable tags (case_tags)
   -> LLM 只生成解释文本（失败则用规则文案）
```

这是合理的 MVP：结构化逻辑负责可靠性，LLM 只负责语义表达。
不要改成「LLM 决定一切」。

**本阶段修正**：解释文本曾经在 `GET /api/student/pathway`、`GET /api/student/dashboard`、
`GET /api/teacher/dashboard`、`GET /api/teacher/students/{id}/learning-profile`
里同步生成，于是「刷新页面」=「再花一次钱、再等 3–20 秒」。现在这四条读路径
**只读确定性结果 + 仍然有效的缓存解释**（见 §5.5）：

```text
GET /pathway
    ↓
deterministic pathway（规则理由永远可用）
    ↓
ai_enrichments 中 fingerprint 匹配的解释（有则替换措辞）
    ↓
reason_source = ai | rule（不把旧解释伪装成当前解释）
```

推荐理由的生成改到「有意义的学习事件之后」（提交并 commit 之后入队）或教师显式刷新；
LLM 不参与 `selected case`、`pathway_stage`、competency 的任何决定。

病例候选不再按标题字符串匹配：`case_tags(case)` 从结构化字段
（`learning_objectives` / `disease_category` / `chief_complaint` / `difficulty`）
推导 `abilities`、`difficulty_rank`、`disease_category`，`_case_fit_score()`
按最弱能力与难度梯度排序，结果确定（同分按 case id）。

完整的路径推荐管线（`recommendation_service` + `catalog_tags`）：

```text
LearnerGap            weakest_abilities(profile)
   -> Candidate Generator   generate_candidates(): 五类学习材料各自的 tags 是否命中缺口
   -> Constraint Filter     apply_constraints(): 难度上下限 + prerequisites
   -> Ranker                rank_candidates(): 缺口匹配 + 难度适配 + 模块多样性（确定性排序）
   -> LLM explanation       只生成每项推荐理由，失败则用规则文案
```

- `catalog_tags.item_tags(module_type, item)` 是**唯一**标签来源，覆盖
  case / knowledge_unit / clinical_skill / guideline / sp_case：
  `abilities`、`ability_labels`、`difficulty`、`difficulty_rank`、
  `disease_category`、`prerequisites`（`PREREQUISITES_BY_RANK`）。
- 标签来自各类材料的内容字段（学习目标、要点、适应证、指南摘要、SP 任务等）；
  只有内容字段完全没有信号时才回退到标题关键词，不再存在硬编码病例标题列表。
- Constraint Filter 会挡掉「能力分 < 70 却给高阶材料」和「能力分 ≥ 80 却只给基础病例/技能」，
  并检查 prerequisites。
- `tests/test_recommendation.py` 固定了：改名不改变结果、标签驱动候选、
  弱学习者拿不到高阶材料、Ranker 输出模块多样且字段完整。

## 9. 安全与滥用防护

- 公开页面**不展示任何具有写权限的教师账号**；登录页最多保留只读演示用的学生账号
  （`NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS=false` 可完全关闭）。
- `ALLOW_PUBLIC_REGISTRATION`：生产默认**关闭**（`app/core/access_policy.py`）。
  匿名注册必须显式打开，因为每个账号都能消耗付费模型额度。
- `app/core/rate_limit.py`：进程内滑动窗口，按 bucket + 身份限流
  （register / login / coach / submit / sp_message / case_generate / ai_probe），
  超限返回 429 + `Retry-After`。身份优先取 `X-Forwarded-For` 首段，其次对端地址。
- 会话级上限：`MAX_COACH_TURNS_PER_SESSION`、`MAX_SP_MESSAGES_PER_SESSION`。
- AI 病例生成器仅教师可用（`require_role(["teacher"])`）并限流；生成的病例必须教师 approve
  才进入正式 case bank。
- 该限流是单进程实现；一旦后端多进程 / 多实例部署，必须替换为进程外限流（见 §12）。

## 10. 医学教育数据与 AI 安全约束

- AI feedback 是 formative；最终评价由教师确认。
- AI 不用于真实患者临床诊疗决策。
- 真实病例进入 LLM 前必须去标识化；不发送不必要的 PHI。
  实现：`app/core/deidentify.py` 在**唯一出口**做脱敏——`llm_service.prompt_json()`
  （所有结构化 prompt）与 `OpenAICompatibleClient.chat()`（任何来源的最终 messages）。
  覆盖手机号、邮箱、身份证、住院号/门诊号/MRN、带标签的姓名与「患者X，男/女/岁」写法；
  只记录命中类型，绝不记录被脱敏的值。临床数字（体温、白细胞、补体、年龄、剂量）保持不变。
  已知限制（见 §12）：无标签的自由文本姓名无法在不误伤临床症状的前提下可靠识别，
  应在输入边界（教师录入真实病例时）处理。
- **输入边界**（教师录入）也会扫描：`POST/PUT /api/teacher/cases` 与
  `POST /api/teacher/case-generator/generate` 返回
  `deidentification: {clean, findings:[{field, kinds}], message}`，
  只报告**哪些字段**、**哪类标识**，绝不回显标识值；教师端页面会显示黄色提示。
  默认只提示不阻断（`REQUIRE_CASE_DEIDENTIFICATION=true` 时改为 400 并拒绝入库）。
  系统不会静默改写教师输入的病例文本。
- 所有 guideline 内容保留来源与年份（`GuidelineDocument.organization/year`）。
- AI-generated case 必须 teacher approve 才能进入正式 case bank。
- hidden answer 不得出现在学生端 API：`standard_diagnosis`、`treatment_plan`、`rubric`、
  SP `hidden_history`（由 `serialize_case_for_student` 与 SP 序列化裁剪）。

### 学生端可见范围（实现对照）

| 资源 | 学生可见 | 仅教师/管理员 |
| --- | --- | --- |
| 病例 | 主诉/病史/查体/检查/影像/学习目标 | `standard_diagnosis`、`treatment_plan`、`rubric`、`differential_diagnosis` |
| SP 病例 | 患者基本画像、开场白、期望任务、评分维度名 | `hidden_history`（须在问诊中问出）、`scoring_rubric` 内容 |
| 知识单元 | 题目文本、要点、正文 | `quiz_items[].answer_keywords`（服务端判分） |
| 临床技能 | 适应证、禁忌证、步骤、常见错误 | `scoring_rubric`（OSCE 检查表） |

角色判断在路由层完成（`user.role in {"teacher", "admin"}`），
`tests/test_sp_redaction.py` 与 `tests/test_learner_redaction.py` 同时固定
「学生看不到」与「教师仍能看到」，并验证问诊与测验功能未被削弱。

`tests/test_student_api_leak_sweep.py` 把这一类问题变成可回归的不变量：
它用带标记（`SECRET*ALPHA`）的隐藏答案建库，然后以学生身份遍历 20 个
目录/画像端点与训练流（session、coach、tutor、result、SP message/submit/result、
quiz/skill/pico 提交），断言任何响应体都不包含隐藏标记；再用教师身份确认
同一批标记对教师可见（证明扫描不是空跑）。唯一允许出现隐藏标记的是学生自己的
SP 对话与 transcript —— 那是问诊中「问出来」的内容，并且另有测试证明
无关提问不会返回整段隐藏病史。

## 11. 公网部署形态（当前 = 目标）

试点入口已经是 HTTPS：

```text
Internet
    |
    v
https://clinpath.1031989.xyz        (Cloudflare edge TLS)
    |
    v
cloudflared 隧道（出站连接，本机不新监听端口）
    |
    v
Next.js 127.0.0.1:8101              (仅 loopback)
    |
    v
FastAPI 127.0.0.1:8100              (内部；公网 IP:8101 已不再可达)
```

- TLS 由 Cloudflare 边缘终止，`deploy/cloudflared/clinpath-pilot.yml.example` +
  `deploy/systemd-user/clinical-https.service` 固定这条路径；**本机不新增监听端口**。
  这台机器上 443 已被无关服务占用，且没有可用域名证书链，因此没有采用
  Caddy/Nginx + Let's Encrypt 形态。
- 明文 HTTP 请求（`x-forwarded-proto: http`）由前端 307 跳转到
  `https://clinpath.1031989.xyz`（`frontend/next.config.ts`，仅在设置
  `CLINPATH_HTTPS_HOST` 时启用）。
- `COOKIE_SECURE=true`（operator 环境文件，不进仓库）：浏览器只在 HTTPS 下保存会话
  cookie，明文入口失效时是「登录不成功」而不是「明文传输会话」。
- 前端只监听 loopback（`CLINPATH_FRONTEND_HOST=127.0.0.1`），
  `http://129.153.118.58:8101` 不再是可用入口；`verify_deploy.sh` 默认检查
  `https://clinpath.1031989.xyz`，可用 `CLINPATH_PUBLIC_BASE` 覆盖。
- 回退路径（若隧道不可用）：`CLINPATH_FRONTEND_HOST=0.0.0.0` 重启前端 +
  `COOKIE_SECURE=false`，即回到旧的裸 HTTP 形态；这只是应急，不再作为目标架构。

历史目标形态（若将来改为自建反代）：

```text
Domain
  |
  v
HTTPS reverse proxy (Caddy / Nginx)
  |
  v
Next.js :8101
  |
  v
FastAPI :8100 (internal only)
```

迁移要求：反代终止 TLS，只暴露 443（8101 不再对公网开放）；后端 `COOKIE_SECURE=true`
（`_auth_response` 已支持该开关）；`FRONTEND_ORIGINS` 收敛为正式域名。

Caddy 参考：

```caddy
clinpath.example.com {
    reverse_proxy 127.0.0.1:8101
}
```

Nginx 参考：

```nginx
server {
    listen 443 ssl http2;
    server_name clinpath.example.com;
    location / {
        proxy_pass http://127.0.0.1:8101;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

在没有域名 / 证书之前，HTTPS 迁移不阻塞其它修复，但不得再把裸 HTTP 描述为最终生产架构。

## 12. 已知债务（按优先级，依据本阶段实测重排）

- P1：**病例评测仍然是同步的**。真实 provider 实测 p50 17.6–20.3s、p95 28.3s、
  最大 61.7s（并发 2/5/10）。它不再拖累任何读路径，但「提交后等待半分钟」仍是
  教学体验问题。下一步应做异步化设计（冻结作答 → `evaluation_pending` → 后台评测 →
  结果就绪），见 `docs/PILOT_READINESS_REPORT.md` §9。
- P1：`ai_invocations` 以「一次任务一个事件」聚合记录；如需逐次重试级别的审计
  （每次 attempt 一行）仍需扩展。
- P1：五类学习材料都已结构化打标并接入 Candidate → Constraint → Ranker；标签目前由内容
  字段启发式推导，尚未由教师在编辑界面显式维护（缺 tags 的可视化编辑与校验）。
- P1：tutor 只覆盖病例训练的 5 个推理步骤；SP 问诊、指南 PICO、技能训练仍是一次性反馈。
- P1：限流仍是单进程内存实现，而部署已改为多 worker（§16）。
  **当前决策是接受并记录 per-process 语义**：限流是滥用防护，不是配额账本，
  有效上限变成「配置值 × worker 数」对教学试点可接受；换共享限流器需要引入
  额外中间件，本阶段没有证据支持。多实例（多机）部署前必须重新评估。
- P2：`ai_runtime` 的 calls/failures/fallbacks 与最近一次 probe 状态是**进程内**的，
  多 worker 下 `/teacher/runtime` 看到的是「某个 worker」的计数；持久事实以
  `ai_invocations` 表为准。若要跨 worker 一致，需要把计数改为查表。
- P2：LLM 出口强制脱敏 + 教师录入时检测提示（可选严格阻断）均已实现；
  剩余限制是正则本身——完全没有标签、也没有性别/年龄等线索的自由文本姓名仍可能漏过。
  当前病例库为教学用示例数据。
- P2：learner model 仍是加权投影，未纳入 confidence / difficulty / recency / source。
- P2：读接口仍是 GIL 受限的同步实现：4 worker 让 100 并发读 p95 落在 0.14–0.18s，
  但单进程只有几十 req/s；若试点规模继续增长，应先做 N+1/序列化开销优化
  （本阶段已把 pathway 的 161 条 SQL 降到 18 条），再考虑多机。

## 13. 数据库演进与迁移安全

### SQLite 并发不变量

- 引擎在连接时设置 `PRAGMA journal_mode=WAL` 与 `busy_timeout=5000`
  （`app/database.py`）：默认 rollback journal 下读事务会持有共享锁并阻塞写事务，
  曾导致并发请求与 AI 审计写入出现 `database is locked`。
- **不要在持有写事务时调用模型**：`sessions.submit` 过去在 `db.flush()` 之后、`db.commit()`
  之前调用 recommendation LLM，写锁因此被持有数秒，阻塞其它写请求。现在先提交评分/证据/
  能力投影，再在第二个事务里写入推荐（`get_result` 已容忍推荐暂缺）。
- 审计写入不预先执行任何读语句：读会让 INSERT 变成锁升级，SQLite 在这种升级上会立即返回
  `SQLITE_BUSY` 而忽略 `busy_timeout`。审计失败只记 warning，绝不影响训练请求。
- **连接池是一个容量上限，不是一个实现细节**：SQLAlchemy 对文件 SQLite 默认使用
  `QueuePool(pool_size=5, max_overflow=10)`，即整进程只有 15 个并发 session。
  100 并发读实测直接把它打满，请求在池上等 30 秒后抛
  `QueuePool limit of size 5 overflow 10 reached`。现在
  `app/database.py` 显式声明 `pool_size=20 / max_overflow=40 / pool_timeout=5`
  （可用 `CLINPATH_SQLITE_POOL_SIZE` 等覆盖）。缩短 `pool_timeout` 也是刻意的：
  等 30 秒只会把容量问题变成一堆慢 500。
- 读接口是 GIL 受限的同步函数：单进程只能顺序执行 Python 级工作，`docs/PILOT_READINESS_REPORT.md`
  记录了 100 并发下的实测吞吐与多 worker 对比。**提高 worker 数会改变进程内语义**
  （限流窗口与 `ai_runtime` 计数变为 per-process），见 §12 与 §16。

1. 迁移前先跑 `scripts/backup_db.sh` 生成时间戳备份（`start_backend_8100.sh` 会自动执行）。
2. `alembic current` / `alembic heads` 确认迁移链，再 `alembic upgrade head`。
3. 迁移必须容忍历史数据：`20260915_03` 先按 `(session_id, step)` 去重，
   每个 step 保留最新**非空**回答，再建立唯一约束。
4. 禁止删除生产 DB、`seed_data --reset`、`drop all`（disposable test DB 除外）。
5. 迁移后做 schema 与数据量 sanity check。

### 全新安装路径

`app/seed_data.py` 区分两种情况，判断发生在 `create_all` **之前**：

```text
全新空库   -> create_all（当前完整 schema）-> alembic stamp head
已有数据库 -> 绝不 stamp -> alembic upgrade head
```

理由：`stamp` 只是写版本号，不执行迁移。对已有数据库 stamp 会假装它是最新的，
把缺失的列/表留在原地。已有库必须真正跑迁移；`seed_data` 因此调用 `upgrade`，
且迁移本身逐个列/表检查存在性（`20260915_01` 逐列新增、`02`–`05` 先 inspect），
所以「先建表再迁移」也不会因为重复列或 SQLite batch 重建而失败。
`tests/test_seed_migration_semantics.py` 用真实子进程覆盖三种场景：
全新库、被人为改旧的库（缺列必须被迁移补回）、已是最新的库（重复执行幂等）。

## 14. 验证与验收（怎么证明它真的在跑）

本节说明「改完怎么证明」，与 §12 债务区分开：这里是可执行的验收清单。

### 14.1 本地门禁

```bash
cd backend && uv run --python 3.11 --with-requirements requirements.txt pytest -q
cd frontend && npm run typecheck && npm run lint && npm run build
cd frontend && npx playwright test                      # 非破坏性
E2E_RUN_MUTATING=1 E2E_TEACHER_USERNAME=<staff> E2E_TEACHER_PASSWORD=<secret> npx playwright test
```

两个环境门禁默认跳过，只在对应环境里执行（跳过数必须如实上报）：

```text
E2E_EXPECT_FALLBACK=1        针对没有 provider key 的部署，断言结果页显示「规则降级评价」
E2E_EXPECT_NO_JWT_SECRET=1   针对未配置 JWT_SECRET 的前端，断言受保护路由返回 503 而不是信任未验证声明
E2E_EXPECT_REAL_AI=1         针对已配置真实 provider 的生产部署，断言结果页显示「AI 语义评价」，
                             且 evaluation_mode=ai / degraded=false / provider=deepseek /
                             model=deepseek-flash / ai_score 非空；同时核对 ai_invocations 里
                             case_evaluation 与 tutor_question 的 calls>0、success=true、
                             fallback_used=false。DeepSeek 不可用时该门禁必须失败，不允许静默回退。
```

本阶段新增的三类**永久架构门禁**（都在默认 `pytest -q` 内，不需要任何环境变量）：

```text
tests/test_read_paths_never_call_provider.py
    替换 provider 边界计数：/student/pathway、/student/dashboard、/student/competency、
    /teacher/dashboard、/teacher/students/{id}/learning-profile 的 provider_call_count == 0，
    且读请求不产生任何 AI 审计事件；缓存解释过期时展示规则理由、且不在读路径触发生成。
tests/test_ai_policy.py
    每个 audit 能力都有策略；thinking 任务不得携带 temperature；只有 llm_service
    可以碰 `extra_body`；正确性关键任务保留完整推理预算。
tests/test_proxy_timeout_budget.py（既有）
    proxyTimeout 仍是「正确性上限」，不因页面变快而调小。
```

页面延迟证据不使用毫秒断言（浏览器测试会因此变脆），改用
`scripts/measure_page_latency.py` 采样并写进报告；provider 停机的导航验收见 §16。

### 14.2 部署一致性

`./scripts/verify_deploy.sh`（只读）一次核对：HEAD / 未提交文件数 / 本地与线上源码指纹 /
schema 是否为迁移 head / systemd 状态 / 公网入口 / 后端与前端 JWT_SECRET 摘要是否 MATCH。
它同时覆盖「未提交的工作树」这一情形，因此比单看 git SHA 更可靠。
**每一项必需检查都参与最终 exit code**：服务未 active、公网入口不可达、`/api/health`
不健康、指纹/SHA/schema/JWT 任一不符都会以非 0 退出——输出好看但退出 0 的「假绿」
本身就是缺陷，其判定逻辑由 `backend/tests/test_verify_deploy_script.py` 覆盖。

### 14.2.1 Web 层的等待预算必须大于传输层的最坏耗时

Next.js 的 rewrite 代理对每个转发请求有 `experimental.proxyTimeout`，未配置时默认
**30 秒**（`next/dist/server/lib/router-utils/proxy-request.js`）。真实 DeepSeek
Thinking Mode 的一次病例评测实测 15–25 秒，于是出现过：后端已经写出 `scores` 行、
浏览器却收到 500 —— 代理先判了超时。因此：

```text
proxyTimeout (frontend/next.config.ts)  >  LLM_TIMEOUT_SECONDS × (LLM_MAX_RETRIES + 1)
       300s                                    60s × 2 次（生产实测取值）
```

后端对自己的模型调用有界（超时 + 有界重试 + 短退避），Web 层不得成为「更早失败」
的那一层。这条不变量由 `backend/tests/test_proxy_timeout_budget.py` 守住：把
`proxyTimeout` 调回 30s 会让该测试失败。

### 14.3 生产 AI 验收（不看文风，只看元数据）

```text
1. POST /api/system/ai-probe（教师会话）
   -> configured=true, provider=deepseek, model!=null, reachable=true, latency_ms>0, error_type=null
2. 在浏览器里真实完成一次五步病例训练并提交
   -> scores: evaluation_mode=ai, degraded=false, provider/model 非空, ai_score 非空
3. 若使用导师：GET/审计里出现 tutor_question
   -> ai_invocations: calls>0, success=true, fallback_used=false
```

规则回退不算通过「真实 AI 验收」；回退路径由单元测试与 §14.1 的
`E2E_EXPECT_FALLBACK` 单独覆盖，UI 必须显示「规则降级评价」，不得伪装成 AI。

## 15. 目标架构全景（最终形态）

§2 描述的是当前真实运行的系统；本节是它要演进到的整体形态，两者差异必须在
§12 债务中可见，不允许把「目标」当成「已实现」。

```text
                         ┌──────────────────┐
                         │     Browser      │
                         └────────┬─────────┘
                                  │
                         ┌────────▼─────────┐
                         │      Next.js     │
                         │ Auth / Student   │
                         │ Teacher / Status │
                         └────────┬─────────┘
                                  │
                           same-origin API
                                  │
                         ┌────────▼─────────┐
                         │      FastAPI     │
                         └────────┬─────────┘
                                  │
           ┌──────────────────────┼───────────────────────┐
           │                      │                       │
    ┌──────▼──────┐       ┌──────▼──────┐        ┌──────▼──────┐
    │ Training    │       │ Assessment  │        │ AI Service  │
    │ Engine      │       │ Engine      │        │ + Audit     │
    └──────┬──────┘       └──────┬──────┘        └──────┬──────┘
           │                      │                       │
           └──────────────┬───────┴───────────────────────┘
                          │
                  ┌───────▼────────┐
                  │ LearningEvidence│
                  └───────┬────────┘
                          │
                  ┌───────▼────────┐
                  │ Competency Model│
                  └───────┬────────┘
                          │
                  ┌───────▼────────┐
                  │ Adaptive Planner│
                  └───────┬────────┘
                          │
                  ┌───────▼────────┐
                  │ Teacher Review │
                  └────────────────┘
```

映射到当前代码：

| 图中模块 | 当前实现 |
| --- | --- |
| Training Engine | `routes/sessions.py`、`routes/sp.py`、`routes/skills.py`、`routes/knowledge.py`、`routes/guidelines.py` + `tutor_service` |
| Assessment Engine | `services/scoring_llm.py`、`guideline_scoring.py`、`sp_patient.score_sp_session`、`competency_update_service` |
| AI Service + Audit | `services/llm_service.py`、`core/llm_config.py`、`core/ai_runtime.py`、`core/ai_audit.py` |
| LearningEvidence | `models.LearningEvidenceEvent` + `services/learning_evidence_service.py` |
| Competency Model | `models.CompetencyProfile` + `services/competency_projector.py` |
| Adaptive Planner | `services/recommendation_service.py` |
| Teacher Review | `routes/teacher.py`、`models.TeacherScoreReview`、`/teacher/runtime` |

## 16. 容量、SLO 与实测基线

完整数据与复现命令在 `docs/PILOT_READINESS_REPORT.md`；这里只固定**可执行的**目标与
**已经达成的**事实，二者必须分开写，不得互相冒充。

### 目标（试点 SLO）

```text
普通已认证 GET        ：低负载 p95 < 1s（后端）
页面可交互            ：几秒内，不等待模型
GET /student/pathway  ：0 次 provider 调用，确定性响应立即可用
GET /teacher/dashboard：0 次 provider 调用
GET /teacher/.../learning-profile：0 次 provider 调用
AI 任务单独报告        ：Tutor / case evaluation / SP feedback / guideline rationale
```

### 本阶段实测达成情况（单 VPS，4 vCPU，SQLite WAL，4 backend workers）

```text
100 并发非 AI 用户（k6，真实登录 + 导航，2m45s）
    read p95 = 139ms / 187ms（两次运行）
    0% HTTP 失败，0 个 5xx，0 个 429（限流已按 staging 设置抬高）
    backend 峰值 CPU ≈ 2.3 / 4 核，RSS ≈ 655MB
    SQLite 同负载下写入 1283 次：0 失败，p50 1ms / p95 2ms

provider 完全不可达时
    所有导航 GET 200，路径页 27–35ms、教师看板 107–113ms

mock 慢 provider（8s / 15s）+ 25 个并发 AI 请求
    导航 p95 206ms / 326ms，0 5xx；provider 全部 429 时导航 p95 615ms，0 5xx

真实 DeepSeek（deepseek-flash）
    tutor 并发 2/5/10：p50 0.98 / 5.8 / 5.7s，无降级、无 429
    case evaluation 并发 2/5/10：p50 17.6 / 18.8 / 20.3s，p95 28.3s，无降级
```

### 为什么是 4 个 worker

实测：单进程在 100 并发读下 p95 6–10s（GIL 受限的同步请求体），3 worker p95 ≈ 2.0s，
4 worker p95 ≈ 0.19s 且峰值 CPU 2.3/4 核、RSS 655MB，仍有留给 Next.js 与系统的余量。
代价必须一起写下来：限流窗口与 `ai_runtime` 计数变成 per-process（§12）。

### 复现工具

```text
loadtest/k6_navigation.js        场景 A：100 并发非 AI 用户
loadtest/k6_mixed_ai.js          场景 B：导航 + 并发 AI（配合 mock provider）
loadtest/mock_provider.py        确定性假 provider（延迟 / 429 / 5xx / 空体 / 非法 JSON）
loadtest/sqlite_write_probe.py   负载下的 SQLite 写健康
scripts/start_staging_8200.sh    一次性 staging 后端（生产库副本 + 迁移到 head）
scripts/measure_page_latency.py  认证后页面延迟采样（before/after）
backend/tools/ai_benchmark.py    逐任务策略的延迟/质量对比（会消耗真实额度）
backend/tools/ai_concurrency.py  有界真实 provider 并发
```

## 17. 演示层与学习过程复盘（本阶段新增）

上一阶段把系统做成"能跑对"；本阶段把它做成"临床教师看得懂"。两者不是一回事：
数据结构和 API contract 保持稳定英文 key，**人类读到的内容由展示语义层统一定义**。

### 17.1 展示语义层（display labels）

`app/services/display_labels.py` 是唯一的业务中文词表：

- 模块：`knowledge → 基础知识学习`、`skill → 临床技能训练`、`case → 病例推理训练`、
  `guideline → 指南循证学习`、`sp → SP模拟问诊`（同时覆盖 catalog key
  `knowledge_unit` / `clinical_skill` / `sp_case`）。
- 路径阶段：`阶段N：<title>` 由 `recommendation_service.PATHWAY_STAGES` **推导**，
  不另写一份，避免两处定义漂移（阶段 3 的 canonical title 因此统一为「临床决策训练」）。
- 能力维度沿用 `serializers.ABILITY_LABELS`。
- 学习事件类型：`case_session_scored → 病例推理训练完成` 等。

`serialize_student()` 会附带 `current_stage_label`，所以任何页面都不需要自己把
`stage_1_basic_recognition` 变成中文——也就没有第二个地方可以写错。
前端因此不再新增一份中文 map；`lib/abilityLabels.ts`（能力维度与评价方式）与
`lib/format.ts`（时间格式）是仅有的两个前端本地展示工具。

不变量：**开发内部 key 不出现在教师/学生页面可见文本里**。由
`tests/test_presentation_surfaces.py` 与 `frontend/tests/e2e/demo-readiness.spec.ts`
两侧固定（后端断言 payload，浏览器断言可见文本）。

### 17.2 学习证据与趋势必须可解释

- `build_student_evidence_events()` 输出 `module_label`、`activity_title`
  （按 `session_id` / `source_id` 批量回查病例、知识单元、技能、指南、SP 的标题）、
  `event_label` 与 `competency_changes[{key,label,before,after,delta}]`。
  `source_table` / `source_id` / `evidence_payload` 不再返回给教师端。
- `build_growth_trend()` 返回**真正的时间序列**：只包含有分数、有能力变化的训练事件，
  按时间升序，最多保留最近 `GROWTH_TREND_POINT_LIMIT=40` 个点；
  `teacher_score_confirmed` 是既有结果的可信度来源，不是一次新训练，因此不作为数据点。
  页面标题是「阶段性学习表现趋势」而不是「综合能力成长曲线」——底层数据不代表全局胜任力指数。
- 列表默认只展示最近 `EVIDENCE_EVENT_PAGE_SIZE` 条（页面用 `<details>` 展开全部）；
  这是展示裁剪，底层证据一行都没有删除。

### 17.3 研究数据页：预览 ≠ 完整数据集

`GET /api/teacher/export/research-data` 保持匿名字段契约不变，并新增：

- `summary`：学生数、记录数、覆盖模块、数据时间范围、`preview_limit`；
- `preview_rows`：按时间**倒序**的最近 20 条。

完整数据集仍然在 `rows` 中返回，并且新增
`GET /api/teacher/export/research-data.csv`（`text/csv` + UTF-8 BOM，Excel 中文环境可直接打开，
内容为全量记录）。页面显式声明「当前显示 x / 筛选后 y 条 · 完整研究数据共 z 条」，
避免把预览当成研究数据。匿名化不变：只输出 `S<student_id:04d>` 与班级，绝不输出学生姓名。

### 17.4 学习记录与病例复盘（新的历史读路径）

新增 `GET /api/student/history`（`/student/history` 页面）与扩展
`GET /api/sessions/{id}/result` 的 `reasoning_review`：

| 项目 | 事实源 | 说明 |
| --- | --- | --- |
| 五阶段回答 | `StudentAnswer` | 按 `REQUIRED_REASONING_STEPS` 顺序输出，`step_title` 为 canonical 中文 |
| 导师对话 | `TutorTurn` | 一次查询 `WHERE session_id=? ORDER BY step, turn_index`，Python 分组，避免 5 次 N+1 |
| 评分 | `Score` | 沿用既有 `serialize_score`，含 `evaluation_mode` / `provider` / `model` |

硬约束（由测试固定）：

1. **不新增 transcript 表**：`StudentAnswer` + `TutorTurn` 已是历史事实源。
2. **历史读取不调用 provider**：`/api/student/history` 与 `/api/sessions/{id}/result`
   在 `tests/test_read_paths_never_call_provider.py` 中断言 `provider_call_count == 0`，
   且不产生任何 `ai_invocations` 事件。
3. **不泄露隐藏答案**：`tutor_state_json`、`standard_diagnosis`、`treatment_plan`、`rubric`
   与 SP 隐藏病史都不在响应中；`tests/test_presentation_surfaces.py` 同时检查字段名与值。
4. **权限**：list 由 token 决定（`_current_student_id`），单条 result 走
   `require_student_access`；学生 A 读学生 B 的 session 返回 403，匿名返回 401。

### 17.5 教师驾驶舱布局

视频演示的桌面视口是 1440×900 / 1920×1080：热力图占满内容宽度，
「班级能力画像」位于其下方并在内部横向排布（雷达 + 短板卡片网格），
避免旧版左右分栏造成的右侧长条与下方大面积空白。
`frontend/tests/e2e/demo-readiness.spec.ts` 用 bounding box 断言
「画像 top ≥ 热力图 bottom」、画像宽度接近热力图宽度、且页面无横向滚动。

### 17.6 演示数据治理工具

`scripts/prepare_presentation_data.py`（`--dry-run` 默认 / `--apply`）：

1. 先审计数据库，只要出现无法识别为非演示数据的学生账号就**拒绝执行**；
2. 前置检查计划引用的目录记录（病例/知识单元/技能/指南/SP）是否齐全，缺失则整体中止；
3. 执行前强制 `scripts/backup_db.sh` 生成时间戳备份；
4. 只删除 4 名演示学生的合成学习记录，不触碰账号、密码、目录数据与其他学生；
5. 将学生能力画像重置为声明的基线，再**通过真实路由代码**重放 16 次学习活动
   （知识测验 / 技能步骤 / 病例五步作答 + 导师追问 / 指南 PICO / SP 问诊）；
6. 把新建记录重新盖章到计划日期——这个数据集被明确声明为 synthetic，
   `created_at` 的构造是它的目的，不是对真实历史的改写；
7. 重算路径阶段与 AI 说明。

评分仍来自真实模型调用：未配置 provider 时脚本**拒绝执行**，避免把规则输出写成 AI。
因此演示数据集的每一行 AI 评分都能追溯到 `ai_invocations`。
反复执行是幂等的：第二次运行会删除并重建同一批记录，
`tests/test_prepare_presentation_data.py` 断言两次运行后的行数完全一致。
