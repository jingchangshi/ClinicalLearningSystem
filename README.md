# 诊途：临床推理与自适应学习系统

“诊途”是面向临床医学本科生的医学教育 MVP 系统。它不是普通问答机器人，而是围绕风湿免疫病例训练形成教学闭环：病例训练、临床推理追问、推理链分析、自动评分、能力画像、自适应学习路径推荐和教师驾驶舱。

## 核心功能

- 学生端首页：选择学生，查看基本信息、能力画像、推荐病例和学习建议。
- 病例训练：基于真实 SQLite 病例数据完成 5 个临床推理步骤。
- 临床推理追问：规则版 AI Coach，保留 OpenAI 兼容 API 接入点。
- 自动评分：按 6 个能力维度生成分项评分、总分、优点、不足和形成性反馈。
- 能力画像更新：按“旧分数 * 0.7 + 本次分数 * 0.3”更新学生画像。
- 自适应学习路径：按能力短板进入 4 个学习阶段并推荐下一病例。
- 教师驾驶舱：展示班级整体表现、共性短板、教学重点、学生表格和最近训练记录。
- 病例管理：教师端支持病例查看、新增、编辑和删除。

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

数据库文件位于 `backend/clinical_learning.db`。种子数据包括 3 名学生、5 个风湿免疫病例、初始能力画像和学习推荐。

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

## 环境变量与真实 AI 接入

默认不需要任何 AI Key，系统使用规则版追问、评分和推荐。

如需接入 OpenAI 兼容 API：

```bash
export OPENAI_API_KEY=your_api_key
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_MODEL=gpt-4o-mini
```

预留函数位于 `backend/app/services/llm_client.py`：

- `generate_reasoning_question(case, step, student_answer)`
- `score_student_answer(case, answers, rubric)`
- `generate_learning_recommendation(profile, recent_scores, cases)`

没有 `OPENAI_API_KEY` 时会自动回退到本地规则逻辑，不影响系统运行。

## 核心页面

- `/`：角色入口，选择学生端或教师端
- `/student/dashboard`：学生首页
- `/student/case/[caseId]`：病例训练页
- `/student/result/[sessionId]`：评分反馈页
- `/student/pathway`：自适应学习路径页
- `/teacher/dashboard`：教师驾驶舱
- `/teacher/cases`：病例管理页

## 主要 API

- `GET /api/students`
- `GET /api/students/{student_id}`
- `GET /api/cases`
- `GET /api/cases/{case_id}`
- `GET /api/students/{student_id}/competency`
- `GET /api/students/{student_id}/dashboard`
- `POST /api/sessions/start`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/answers`
- `POST /api/sessions/{session_id}/coach`
- `POST /api/sessions/{session_id}/submit`
- `GET /api/sessions/{session_id}/result`
- `GET /api/students/{student_id}/pathway`
- `GET /api/teacher/dashboard`
- `GET /api/teacher/cases`
- `POST /api/teacher/cases`
- `PUT /api/teacher/cases/{case_id}`
- `DELETE /api/teacher/cases/{case_id}`

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

- 接入真实大模型评分与多轮追问。
- 增加教师对评分 rubric 的可视化编辑。
- 增加学生训练历史、详情页和同伴互评。
- 增加真实登录、班级权限和教师-学生绑定。
- 引入迁移工具 Alembic 管理数据库结构演进。
- 增加端到端测试和部署配置。
