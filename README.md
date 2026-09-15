# ClinPath：AI辅助临床教学与自适应学习路径系统

ClinPath 是面向临床医学本科生的医学教育 MVP 系统。它不是普通问答机器人，而是围绕风湿免疫病例训练形成教学闭环：病例训练、临床推理追问、推理链分析、自动评分、能力画像、自适应学习路径推荐和教师驾驶舱。

## 核心功能

- 学生端首页：选择学生，查看基本信息、能力画像、推荐病例和学习建议。
- 病例训练：基于真实 SQLite 病例数据完成 5 个临床推理步骤。
- 临床推理追问：规则版 AI Coach，保留 OpenAI 兼容 API 接入点。
- 自动评分：按 6 个能力维度生成分项评分、总分、优点、不足和形成性反馈。
- 能力画像更新：按“旧分数 * 0.7 + 本次分数 * 0.3”更新学生画像。
- 自适应学习路径：按能力短板进入 4 个学习阶段并推荐下一病例。
- 统一学习路径：按能力短板混合推荐知识、技能、病例、指南和 SP 任务。
- 基础知识学习：提供风湿免疫核心知识单元、学生学习进度和知识测验。
- 临床技能训练：提供查体/操作步骤练习、OSCE 风格评分和改进反馈。
- 循证指南学习：提供指南摘要、推荐意见、PICO 练习和循证医学能力更新。
- 标准化病人 SP：提供虚拟病人问诊、沟通训练和 OSCE 风格评分。
- AI 病例生成器：教师输入疾病类别、教学目标和能力维度后生成病例草稿，并可批准入库。
- 展示模式：提供 `/demo` 课题申报截图页，集中展示 AI Learning Profile、Learner Digital Twin、Competency Growth Map、SP-OSCE 和 Teacher Analytics。
- 教师驾驶舱：展示班级整体表现、共性短板、教学重点、学生表格和最近训练记录。
- 病例管理：教师端支持病例查看、新增、编辑和删除。

## 如何使用

1. 初始化/重置数据库：

```
cd backend
uv run --with-requirements requirements.txt python -m app.seed_data --reset
```

2. 启动后端：

```
cd backend
uv run --with-requirements requirements.txt uvicorn app.main:app --reload
后端地址：http://localhost:8000
OpenAPI：http://localhost:8000/docs
```

Oracle VPS 公网演示建议使用 8100 作为内部后端端口：

```
cd backend
FRONTEND_ORIGINS=http://129.153.118.58:8101 \
uv run --with-requirements requirements.txt uvicorn app.main:app --host 0.0.0.0 --port 8100
```

3. 启动前端：

```
cd frontend
npm install
npm run dev
前端地址：http://localhost:3000
```

Oracle VPS 公网演示建议只暴露 8101 给浏览器；前端会把 `/api/...` 同源代理到 VPS 内部的 `127.0.0.1:8100`：

```
cd frontend
npm install
INTERNAL_API_BASE_URL=http://127.0.0.1:8100 npm run build
INTERNAL_API_BASE_URL=http://127.0.0.1:8100 npm run start -- --hostname 0.0.0.0 --port 8101
```

4. 推荐使用路径：
    打开 / → 学生端 → 选择学生 → 知识单元学习/临床技能训练/循证指南学习/SP模拟考核/点击推荐病例 → 完成 5 个阶段回答 → 每阶段获取追问 → 提交病例 → 查看结果页 → 查看学习路径 → 教师端查看班级表现。


## 技术栈

- 前端：Next.js、React、Tailwind CSS、Recharts、lucide-react
- 后端：FastAPI、SQLAlchemy
- 数据库：SQLite
- AI 接口：`backend/app/services/llm_client.py` 预留 OpenAI API 兼容调用，默认规则逻辑

## 项目结构

```text
frontend/
backend/
  app/
    main.py
    database.py
    models.py
    schemas.py
    routes/
    services/
      llm_client.py
      scoring_llm.py
      recommendation_service.py
    seed_data.py
docs/
```

## 数据库初始化

后端启动时会自动创建 SQLite 数据库并初始化种子数据。手动初始化：

```bash
cd backend
python3 -m app.seed_data
```

重建数据库：

```bash
cd backend
python3 -m app.seed_data --reset
```

数据库文件位于 `backend/clinical_learning.db`。种子数据包括 3 名学生、5 个风湿免疫病例、3 个知识单元、2 个临床技能、2 份指南、2 个 SP 病例、初始能力画像和学习推荐。

## 后端启动

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

如果本机没有 `venv` 或 `pip`，可使用 `uv`：

```bash
cd backend
uv run --with-requirements requirements.txt uvicorn app.main:app --reload
```

后端默认地址：`http://localhost:8000`

- 健康检查：`http://localhost:8000/api/health`
- OpenAPI 文档：`http://localhost:8000/docs`

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端默认地址：`http://localhost:3000`

如果后端地址变化：

```bash
export NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

生产部署到 Oracle VPS 时不要设置 `NEXT_PUBLIC_API_BASE_URL`，默认让浏览器请求同源 `/api`，由 Next.js 转发到 `INTERNAL_API_BASE_URL`。这样公网只需要访问 8101，后端 8100 可作为内部端口使用。

## Oracle VPS 生产部署

推荐端口：

- 前端公网入口：`http://129.153.118.58:8101`
- 后端内部地址：`http://127.0.0.1:8100`
- 前端同源 API：`http://129.153.118.58:8101/api/...`

一键启动脚本：

```bash
cd /home/jcshi/workspace/clinical_learning_system
./scripts/start_backend_8100.sh
```

另开一个终端：

```bash
cd /home/jcshi/workspace/clinical_learning_system
./scripts/start_frontend_8101.sh
```

用户级 systemd 保活：

```bash
mkdir -p ~/.config/systemd/user
cp deploy/systemd-user/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable clinical-backend.service clinical-frontend.service
systemctl --user start clinical-backend.service clinical-frontend.service
```

代码更新后重新构建并重启：

```bash
cd /home/jcshi/workspace/clinical_learning_system
./scripts/backup_db.sh          # 任何 schema 变更前的强制步骤
cd /home/jcshi/workspace/clinical_learning_system/frontend
npm run build
systemctl --user restart clinical-backend.service clinical-frontend.service
```

后端启动脚本会在检测到待执行迁移时自动先备份数据库，再 `alembic upgrade head`。
禁止用删除数据库 / `seed_data --reset` 的方式演进生产 schema。

后端默认以 4 个 worker 启动（`CLINPATH_BACKEND_WORKERS`）。读接口是同步函数，
单进程一次只能执行一个请求的 Python 工作：100 并发读实测单进程 p95 6–10s、4 worker
p95 ≈0.19s。代价是进程内的限流窗口与 `ai_runtime` 计数变为 per-process
（`docs/ARCH.md` §12、§16；测量与复现在 `docs/PILOT_READINESS_REPORT.md`）。

试点前请先跑一遍容量与页面前后对比（只读脚本，不写生产数据）：

```bash
python3 scripts/measure_page_latency.py --samples 3    # 认证后的页面延迟
./scripts/start_staging_8200.sh                        # 一次性 staging 后端（生产库副本）
k6 run -e BASE_URL=http://127.0.0.1:8200 loadtest/k6_navigation.js
```

查看状态和日志：

```bash
systemctl --user status clinical-backend.service clinical-frontend.service
journalctl --user -u clinical-backend.service -f
journalctl --user -u clinical-frontend.service -f
```

如果需要开机后用户未登录也自动恢复，需要管理员执行：

```bash
sudo loginctl enable-linger jcshi
```

Oracle Cloud 和实例防火墙需要至少放行 8101：

```bash
sudo iptables -I INPUT 1 -p tcp --dport 8101 -j ACCEPT
sudo netfilter-persistent save
```

如果仍希望公网直接访问后端文档 `/docs`，再放行 8100：

```bash
sudo iptables -I INPUT 1 -p tcp --dport 8100 -j ACCEPT
sudo netfilter-persistent save
```

验证命令：

```bash
ss -ltnp | grep -E ':8100|:8101'
./scripts/verify_deploy.sh          # 只读：HEAD/指纹/schema/systemd/公网入口 一次核对
curl http://127.0.0.1:8100/api/health
curl http://127.0.0.1:8100/api/system/version
curl http://127.0.0.1:8101/api/students
curl -I http://129.153.118.58:8101/
curl http://129.153.118.58:8101/api/students
curl http://129.153.118.58:8101/api/knowledge
```

## 环境变量与真实 AI 接入

默认不需要任何 AI Key，系统使用规则版追问、评分和推荐。

### Canonical LLM 配置（推荐，唯一事实源）

```bash
export LLM_PROVIDER=deepseek            # deepseek | openai | openai-compatible
export LLM_API_KEY=your_api_key
export LLM_BASE_URL=https://api.deepseek.com
export LLM_MODEL=deepseek-flash          # 当前官方默认模型
export LLM_TIMEOUT_SECONDS=60            # 实测单次思考评测约 17–31 秒
export LLM_MAX_RETRIES=1                 # 有界重试：最坏约 2 次尝试
export LLM_THINKING_ENABLED=true         # DeepSeek Thinking Mode（显式声明，不依赖默认值）
export LLM_REASONING_EFFORT=high         # none 表示关闭思考；也接受 low | max
export LLM_MAX_TOKENS=8192               # 思考轨迹约 3k tokens；4096 会截断 JSON 正文
```

兼容别名（deprecated，请尽快迁移）：`DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` /
`DEEPSEEK_MODEL` 以及 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`。
canonical 变量优先；`app/core/llm_config.py` 是唯一解析实现，
`llm_config_summary()` 会在教师 Runtime 页面提示仍在使用的旧变量名。

DeepSeek 走 OpenAI 兼容的 Chat Completions（`https://api.deepseek.com`，
`POST /chat/completions`）。生产默认模型是 `deepseek-flash`；`deepseek-chat` /
`deepseek-reasoner` 已不在官方当前模型列表中，不再作为默认值。开启 Thinking Mode 时
请求显式携带 `thinking.type=enabled` 与 `reasoning_effort`，并且不发送 `temperature`
（官方文档：思考模式忽略该参数）；`reasoning_content` 只留在传输层，绝不落库、回传学生
或写进审计。链路细节见 `docs/ARCH.md` §5.1.1。

### 其它运行开关

```bash
export CLINPATH_ENV=production          # production 时 JWT_SECRET 必填
export JWT_SECRET=change-me             # 后端与前端 proxy 共用（前端只做粗粒度路由校验）
export COOKIE_SECURE=true               # 走 HTTPS 时必须为 true
export ACCESS_TOKEN_EXPIRE_HOURS=12
export ALLOW_PUBLIC_REGISTRATION=false  # 生产默认关闭匿名注册
export MAX_COACH_TURNS_PER_SESSION=20
export MAX_SP_MESSAGES_PER_SESSION=40
export MAX_TUTOR_TURNS_PER_STEP=6
export REQUIRE_CASE_DEIDENTIFICATION=false  # true 时拒绝入库含明显身份信息的病例文本
# 可选：按端点的每小时限额覆盖，例如 RATE_LIMIT_LOGIN_PER_HOUR=60
```

教师录入病例时（`POST/PUT /api/teacher/cases`、AI 病例生成）系统会检测手机号、
邮箱、身份证、住院号以及带标签的姓名，返回 `deidentification.findings` 并在教师端
显示提示。提交给模型的内容始终在 `llm_service` 出境前强制脱敏；默认只提示不阻断，
`REQUIRE_CASE_DEIDENTIFICATION=true` 时改为拒绝入库。系统不会静默改写教师输入。

教师 / 管理员账号不在公开页面展示，也不允许自助注册，只能由服务器端开通：

```bash
cd backend
uv run --python 3.11 --with-requirements requirements.txt python -m app.manage_users create-teacher teacher --name "教师姓名" --teacher-no T001
```

### AI 调用入口

统一入口位于 `backend/app/services/llm_service.py`：

- `chat_json(system_prompt, user_prompt, fallback)`
- `chat_completion(system_prompt, user_prompt, fallback)`
- `generate_reasoning_question(case, step, student_answer)`
- `score_student_answer(case, answers, rubric)`
- `generate_learning_recommendation(profile, recent_scores, cases)`
- `probe()`：一次性最小真实请求，用于运行状态探测

没有配置 `LLM_API_KEY` 或 provider 调用失败时会自动回退到本地规则逻辑，不影响系统运行，
但结果会被标记为 `evaluation_mode=rule_fallback` / `degraded=true`，前端会明确显示
「规则降级评价」，不会伪装成 AI 评分。

### 运行状态与版本

```text
GET  /api/system/version          当前 git SHA、schema revision、环境、AI 是否配置
GET  /api/system/ai-status        教师可见的 AI runtime 状态（不含任何 key）
POST /api/system/ai-probe         真实探测 provider 连通性与延迟
GET  /api/system/ai-invocations   最近 AI 调用审计（元数据 + 证据引用，无 prompt 正文）
GET  /api/system/reasoning-steps  后端 canonical 推理步骤（前端共用）
```

教师端页面 `/teacher/runtime` 展示部署版本与 AI Runtime，用于快速判断
「浏览器里跑的到底是哪一版」以及 AI 是否真的可用。

无 API Key smoke test：

```bash
cd /home/jcshi/workspace/clinical_learning_system
uv run --with-requirements backend/requirements.txt python scripts/smoke_no_api_key.py
```

### 端到端验收

```bash
cd frontend && npx playwright test                     # 非破坏性
E2E_RUN_MUTATING=1 E2E_TEACHER_USERNAME=<staff> E2E_TEACHER_PASSWORD=<secret> npx playwright test

# 两个环境门禁默认跳过，只在对应环境里运行，跳过数必须如实上报：
E2E_EXPECT_FALLBACK=1 npx playwright test -g fallback      # 无 provider key 的部署：结果页必须显示「规则降级评价」
E2E_EXPECT_NO_JWT_SECRET=1 npx playwright test -g "no JWT_SECRET"   # 未配置 JWT_SECRET 的前端：受保护路由返回 503
# 生产真实 AI 门禁：DeepSeek 不可用时必须失败，不允许静默回退成规则分
E2E_RUN_MUTATING=1 E2E_EXPECT_REAL_AI=1 E2E_TEACHER_USERNAME=<staff> E2E_TEACHER_PASSWORD=<secret> npx playwright test
```

生产 AI 验收看元数据而不是文风：`POST /api/system/ai-probe` 必须
`reachable=true`；一次真实五步训练的分数必须是 `evaluation_mode=ai`、`degraded=false`、
`provider/model` 与 `ai_score` 非空；导师调用在 `ai_invocations` 里
`calls>0 / success=true / fallback_used=false`。细节见 `docs/ARCH.md` §14。

## 核心页面

- `/`：角色入口，选择展示模式、学生端或教师端
- `/demo`：ClinPath 展示模式，支持课题申报截图方案切换
- `/student/dashboard`：学生首页
- `/student/knowledge`：基础知识学习列表
- `/student/knowledge/[unitId]`：知识单元详情和测验
- `/student/skills`：临床技能训练列表
- `/student/skills/[skillId]`：技能步骤练习和评分
- `/student/guidelines`：循证指南学习列表
- `/student/guidelines/[guidelineId]`：指南详情和 PICO 练习
- `/student/sp`：标准化病人 SP 病例列表
- `/student/sp/[caseId]`：SP 聊天问诊考核
- `/student/sp/result/[sessionId]`：SP 考核评分反馈
- `/student/case/[caseId]`：病例训练页
- `/student/result/[sessionId]`：评分反馈页
- `/student/pathway`：自适应学习路径页，展示混合式学习任务
- `/teacher/dashboard`：教师驾驶舱
- `/teacher/cases`：病例管理页
- `/teacher/case-generator`：AI 病例生成器

## 主要 API

- `GET /api/students`
- `GET /api/students/{student_id}`
- `GET /api/cases`
- `GET /api/cases/{case_id}`
- `GET /api/students/{student_id}/competency`
- `GET /api/students/{student_id}/dashboard`
- `GET /api/students/{student_id}/pathway`
- `GET /api/students/{student_id}/knowledge-progress`
- `GET /api/knowledge`
- `GET /api/knowledge/{unit_id}`
- `POST /api/knowledge/{unit_id}/quiz`
- `GET /api/skills`
- `GET /api/skills/{skill_id}`
- `POST /api/skills/{skill_id}/sessions/start`
- `POST /api/skill-sessions/{session_id}/submit`
- `GET /api/guidelines`
- `GET /api/guidelines/{guideline_id}`
- `POST /api/guidelines/{guideline_id}/pico`
- `GET /api/sp-cases`
- `GET /api/sp-cases/{sp_case_id}`
- `POST /api/sp-sessions/start`
- `POST /api/sp-sessions/{session_id}/message`
- `POST /api/sp-sessions/{session_id}/submit`
- `GET /api/sp-sessions/{session_id}/result`
- `POST /api/sessions/start`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/answers`
- `POST /api/sessions/{session_id}/coach`
- `POST /api/sessions/{session_id}/tutor`
- `GET /api/sessions/{session_id}/tutor?step=...`
- `POST /api/sessions/{session_id}/submit`
- `GET /api/sessions/{session_id}/result`
- `GET /api/teacher/dashboard`
- `GET /api/teacher/cases`
- `POST /api/teacher/cases`
- `PUT /api/teacher/cases/{case_id}`
- `DELETE /api/teacher/cases/{case_id}`
- `POST /api/teacher/case-generator/generate`
- `POST /api/teacher/case-generator/{draft_id}/approve`
- `GET /api/system/version`
- `GET /api/system/ai-status`
- `POST /api/system/ai-probe`
- `GET /api/system/reasoning-steps`
- `GET /api/health`

## MVP 跑通路径

1. 打开 `/student/dashboard`，选择学生。
2. 点击推荐病例，系统自动创建训练 session。
3. 在病例训练页完成 5 个阶段回答。
4. 每个阶段点击“获取追问”，系统写入 AIMessage。
5. 点击“提交病例并生成反馈”。
6. 查看结果页的评分、反馈、能力画像和推荐病例。
7. 进入 `/student/pathway` 查看自适应学习路径。
8. 进入 `/teacher/dashboard` 查看班级表现和教学建议。

## 后续开发路线

- 把带 step 级状态的 Socratic tutor 扩展到 SP 问诊、技能训练与指南 PICO 练习。
- 为 coach / SP / 推荐 / 教师洞察 / 病例生成统一落库 AI 调用审计（`AIInvocation`）。
- 让教师在编辑界面显式维护学习材料的 tags（abilities / difficulty / prerequisites），
  替代当前由内容字段启发式推导的方式，并加入标签校验。
- 增加教师对评分 rubric 的可视化编辑。
- 增加学生训练历史、详情页和同伴互评。
- 增加班级权限模型与教师-学生绑定。
- 接入域名 + HTTPS 反向代理，并打开 `COOKIE_SECURE`（见 `docs/ARCH.md` §11）。
