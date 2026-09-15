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
- `JWT_SECRET` 缺失时 proxy 记录错误并退化为「只检查 cookie 是否存在」，绝不因为配置缺失
  把已登录用户锁在门外；后端仍会拒绝任何无效 token。
- `JWT_SECRET` 缺失时**绝不**解码并信任未验证的 role：proxy 对携带 cookie 的受保护请求
  直接返回 `503 Deployment misconfigured: JWT_SECRET is required`，没有 token 时照常跳
  `/login`。这样既不会信任伪造声明，也不会在 `/login` 与 dashboard 之间来回跳转。
  `scripts/start_frontend_8101.sh` 在 `JWT_SECRET` 为空时拒绝启动，让配置错误在启动阶段暴露。
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

## 11. 公网部署形态（当前 vs 目标）

当前入口是裸 HTTP：`http://129.153.118.58:8101`（Next.js），后端 `127.0.0.1:8100` 不对外。
这**不是**理想的生产形态，也不是本文档认可的最终架构。

目标形态：

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

## 12. 已知债务（按优先级）

- P1：`ai_invocations` 以「一次任务一个事件」聚合记录；如需逐次重试级别的审计
  （每次 attempt 一行）仍需扩展。
- P1：五类学习材料都已结构化打标并接入 Candidate → Constraint → Ranker；标签目前由内容
  字段启发式推导，尚未由教师在编辑界面显式维护（缺 tags 的可视化编辑与校验）。
- P1：tutor 只覆盖病例训练的 5 个推理步骤；SP 问诊、指南 PICO、技能训练仍是一次性反馈。
- P1：限流为单进程内存实现，多进程 / 多实例部署前必须替换。
- P2：LLM 出口强制脱敏 + 教师录入时检测提示（可选严格阻断）均已实现；
  剩余限制是正则本身——完全没有标签、也没有性别/年龄等线索的自由文本姓名仍可能漏过。
  当前病例库为教学用示例数据。
- P2：公网仍为 HTTP，需要域名 + HTTPS reverse proxy + `COOKIE_SECURE=true`。
- P2：learner model 仍是加权投影，未纳入 confidence / difficulty / recency / source。

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
