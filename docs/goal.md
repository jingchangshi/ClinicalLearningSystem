# 一、现有系统与目标系统的差距

## 1. 已完成的能力

现有系统已经覆盖目标系统中的三大核心：

| 目标模块    | 当前完成情况             |
| ------- | ------------------ |
| 临床思维训练  | 已有病例训练、5步临床推理、AI追问 |
| 自适应学习路径 | 已有能力画像、阶段判断、病例推荐   |
| 教师驾驶舱   | 已有班级表现、短板分析、教学重点   |

数据库中已有 Student、Case、CaseSession、StudentAnswer、AIMessage、Score、CompetencyProfile、LearningRecommendation 等核心模型。

评分维度已包括医学知识、关键信息提取、鉴别诊断、证据整合、临床决策、循证医学六项。

---

## 2. 距离完整“AI辅助临床教学系统”的差距

| 模块        | 当前状态            | 差距                                 |
| --------- | --------------- | ---------------------------------- |
| 基础知识学习    | 尚未独立模块化         | 缺知识点、微课、错题、知识测验                    |
| 临床技能训练    | 尚未实现            | 缺查体/操作步骤、技能评分、OSCE操作站              |
| 临床思维      | 已有 MVP          | 需增强多轮病例演化、诊断树、反证训练                 |
| 循证指南学习    | 评分维度中已有，但无独立学习流 | 缺 PICO、指南条文、推荐等级、文献证据库             |
| 标准化病人 SP  | 尚未实现            | 缺虚拟病人、多轮问诊、沟通评分、OSCE考核             |
| AI病例生成    | 尚未实现为功能         | 当前病例来自 seed_data 固定种子数据            |
| 真实 LLM 评分 | 预留接口，但默认规则评分    | 需结构化 LLM rubric 评分和 JSON 输出校验      |
| 数据库演进     | SQLite 单文件      | 需 Alembic、PostgreSQL 准备、模块化 schema |

当前 AI 追问接口在有 `OPENAI_API_KEY` 时调用 OpenAI 兼容接口，否则回退到规则追问。 当前评分仍主要是规则关键词评分。

---

# 二、建议开发目标：从“诊途 MVP”升级为“五模块临床教学系统”

建议保留现有项目名“诊途”，系统定位升级为：

> 诊途 Clinical Learning System：面向临床医学本科生的 AI 辅助临床能力训练平台，覆盖基础知识、临床技能、临床思维、循证指南学习和标准化病人考核。

新增模块优先级：

1. **SP标准化病人模拟考核**
2. **AI病例生成器**
3. **循证指南学习模块**
4. **基础知识学习模块**
5. **临床技能训练模块**
6. **统一 OSCE / mini-CEX 评分体系**

---

# 三、Codex 可执行 MVP Prompt：逐模块开发指令

下面这些可以直接逐条交给 Codex。建议不要一次性提交全部，而是按阶段执行。

---

## Prompt 0：先整理仓库并建立开发基线

```text
你正在开发仓库 jingchangshi/ClinicalLearningSystem。

请先阅读 README.md、backend/app/main.py、backend/app/models.py、backend/app/schemas.py、backend/app/routes、backend/app/services、frontend/lib/api.ts、frontend/app 下所有页面，理解现有架构。

目标：在不破坏现有功能的前提下，将当前“诊途：临床推理与自适应学习系统”扩展为 AI 辅助临床教学系统，覆盖：
1. 基础知识学习
2. 临床技能训练
3. 临床思维训练
4. 循证指南学习
5. 标准化病人 SP 考核
6. AI 病例生成

要求：
- 保持 FastAPI + SQLAlchemy + SQLite 当前开发模式。
- 保持 Next.js + React + Tailwind 当前前端模式。
- 所有新增 API 放在 /api 下。
- 所有新增页面保持中文医学教育风格。
- 不引入复杂权限系统。
- 保留现有学生端、教师端、病例训练和路径推荐功能。
- 每完成一个阶段，运行后端导入检查、前端 typecheck/lint。
```

---

## Prompt 1：数据库模型扩展

```text
请扩展 backend/app/models.py、schemas.py 和 seed_data.py，为系统增加以下数据库模型，并保持现有表不破坏：

1. KnowledgeUnit
字段：
- id
- title
- category
- level
- learning_objectives JSON string
- content
- key_points JSON string
- quiz_items JSON string
- related_case_ids JSON string
- created_at

2. KnowledgeProgress
字段：
- id
- student_id FK students.id
- knowledge_unit_id FK knowledge_units.id
- status: not_started / in_progress / completed
- quiz_score
- mastery_score
- updated_at

3. ClinicalSkill
字段：
- id
- title
- category
- difficulty
- indication
- contraindication
- steps JSON string
- common_errors JSON string
- scoring_rubric JSON string
- created_at

4. SkillSession
字段：
- id
- student_id
- skill_id
- status
- submitted_steps JSON string
- score
- feedback
- created_at
- completed_at

5. GuidelineDocument
字段：
- id
- title
- organization
- year
- disease_category
- source_type
- summary
- recommendations JSON string
- pico_examples JSON string
- created_at

6. GuidelineLearningSession
字段：
- id
- student_id
- guideline_id
- clinical_question
- pico
- answer
- score
- feedback
- created_at

7. SPCase
字段：
- id
- title
- disease_category
- difficulty
- patient_profile JSON string
- opening_statement
- hidden_history JSON string
- emotional_style
- expected_tasks JSON string
- scoring_rubric JSON string
- created_at

8. SPSession
字段：
- id
- student_id
- sp_case_id
- status
- transcript JSON string
- diagnosis_summary
- communication_score
- history_taking_score
- reasoning_score
- humanistic_care_score
- total_score
- feedback
- started_at
- completed_at

9. GeneratedCaseDraft
字段：
- id
- teacher_prompt
- generated_payload JSON string
- status: draft / approved / rejected
- created_at

要求：
- 使用当前 SQLAlchemy 2.0 mapped_column 风格。
- 添加必要 relationship。
- schemas.py 增加对应 Pydantic 读写模型。
- seed_data.py 增加最小种子数据：3个知识点、2个技能、2条指南、2个SP病例。
- 不删除现有 seed_data 中风湿免疫病例。
```

---

## Prompt 2：基础知识学习模块

```text
请实现基础知识学习模块。

后端：
新增 backend/app/routes/knowledge.py，并在 main.py 注册。
API：
- GET /api/knowledge
- GET /api/knowledge/{unit_id}
- GET /api/students/{student_id}/knowledge-progress
- POST /api/knowledge/{unit_id}/quiz
请求：student_id, answers
返回：quiz_score, mastery_score, feedback, updated_progress

评分规则 MVP：
- 根据 quiz_items 中的标准答案关键词进行规则评分。
- mastery_score = 旧 mastery_score * 0.6 + 本次 quiz_score * 0.4。
- 若 mastery_score >= 80，status = completed。

前端：
新增页面：
- /student/knowledge
- /student/knowledge/[unitId]

功能：
- 展示知识单元列表
- 按 category、level 显示
- 进入详情页显示学习目标、正文、关键点、测验
- 提交测验后展示掌握度与反馈
- 与学生选择状态复用当前学生端逻辑

要求：
- 在学生 dashboard 增加“基础知识学习”入口。
- 在 pathway 页面中显示知识短板建议。
```

---

## Prompt 3：临床技能训练模块

```text
请实现临床技能训练模块。

后端：
新增 backend/app/routes/skills.py，并在 main.py 注册。
API：
- GET /api/skills
- GET /api/skills/{skill_id}
- POST /api/skills/{skill_id}/sessions/start
请求：student_id
- POST /api/skill-sessions/{session_id}/submit
请求：submitted_steps: string[]
返回：score, feedback, missed_steps, common_errors

评分规则：
- 将 submitted_steps 与 ClinicalSkill.steps 中的 expected steps 对比。
- 计算步骤完整性、顺序合理性、安全性关键词。
- 输出结构化反馈。

前端：
新增页面：
- /student/skills
- /student/skills/[skillId]

页面功能：
- 展示技能列表，例如关节查体、关节穿刺模拟
- 显示适应证、禁忌证、标准步骤、常见错误
- 学生可拖拽或填写步骤顺序
- 提交后显示评分和改进建议

要求：
- 先用普通表单实现，不必实现真实视频和图像识别。
- 保持 Tailwind UI 风格。
```

---

## Prompt 4：循证指南学习模块

```text
请实现循证指南学习模块。

后端：
新增 backend/app/routes/guidelines.py，并在 main.py 注册。
API：
- GET /api/guidelines
- GET /api/guidelines/{guideline_id}
- POST /api/guidelines/{guideline_id}/pico
请求：student_id, clinical_question, pico, answer
返回：score, feedback, recommended_answer

评分维度：
1. PICO 完整性
2. 指南推荐匹配
3. 推荐等级理解
4. 临床适用性
5. 风险与个体化说明

前端：
新增页面：
- /student/guidelines
- /student/guidelines/[guidelineId]

页面功能：
- 指南列表
- 指南摘要
- 推荐意见卡片
- PICO 练习表单
- 提交后显示循证反馈

要求：
- 在学生 dashboard 增加“循证指南学习”入口。
- 与现有 evidence_based_medicine 能力画像联动：
  - 完成一次指南学习后，按得分更新 CompetencyProfile.evidence_based_medicine。
```

---

## Prompt 5：标准化病人 SP 对话模块

```text
请实现标准化病人 SP 模拟考核模块。

后端：
新增 backend/app/routes/sp.py，并在 main.py 注册。
API：
- GET /api/sp-cases
- GET /api/sp-cases/{sp_case_id}
- POST /api/sp-sessions/start
请求：student_id, sp_case_id
返回：session_id, opening_statement
- POST /api/sp-sessions/{session_id}/message
请求：message
返回：patient_reply, transcript
- POST /api/sp-sessions/{session_id}/submit
请求：diagnosis_summary
返回：total_score, communication_score, history_taking_score, reasoning_score, humanistic_care_score, feedback

AI逻辑：
- 在 backend/app/services/sp_patient.py 中实现：
  - generate_patient_reply(sp_case, transcript, student_message)
  - score_sp_session(sp_case, transcript, diagnosis_summary)
- 若 OPENAI_API_KEY 存在，使用 OpenAI 兼容接口。
- 若无 API Key，使用规则回复：
  - 根据 hidden_history 中关键词回答
  - 对开放式问题给较完整回答
  - 对封闭式问题给简短回答
  - 对共情表达给积极回应

前端：
新增页面：
- /student/sp
- /student/sp/[caseId]
- /student/sp/result/[sessionId]

功能：
- 选择 SP 病例
- 显示患者开场白
- 学生以聊天形式问诊
- 系统回复患者回答
- 学生提交初步诊断、鉴别诊断、处理计划
- 显示 SP 考核评分

评分维度：
- 问诊完整性
- 沟通表达
- 临床推理
- 人文关怀
```

---

## Prompt 6：AI病例生成器

```text
请实现教师端 AI 病例生成器。

后端：
新增 backend/app/routes/case_generation.py，并在 main.py 注册。
API：
- POST /api/teacher/case-generator/generate
请求：
{
  disease_category,
  difficulty,
  teaching_goal,
  required_elements,
  target_abilities
}
返回：
{
  draft_id,
  generated_payload
}

- POST /api/teacher/case-generator/{draft_id}/approve
功能：
将 generated_payload 转换为 Case 并写入 cases 表。

服务：
新增 backend/app/services/case_generator.py：
- generate_case_payload(prompt)
- validate_case_payload(payload)
- fallback_rule_case(payload)

要求：
- 若 OPENAI_API_KEY 存在，调用 LLM 生成结构化 JSON。
- 若无 API Key，用模板生成病例草稿。
- validate_case_payload 必须检查字段完整性：
  title, disease_category, difficulty, learning_objectives, chief_complaint, history, physical_exam, lab_results, imaging, standard_diagnosis, differential_diagnosis, treatment_plan, rubric

前端：
新增教师页面：
- /teacher/case-generator

功能：
- 教师输入疾病类别、难度、教学目标、能力维度
- 点击生成病例
- 展示病例草稿
- 教师可编辑 JSON 或表单字段
- 点击批准后写入病例库
```

---

## Prompt 7：统一学习路径引擎升级

```text
请升级 backend/app/services/recommendation_service.py。

目标：
学习路径不再只推荐 case，而是能推荐：
- knowledge_unit
- clinical_skill
- case
- guideline
- sp_case

新增函数：
- build_learning_pathway(student_profile, recent_activity)
返回：
{
  current_stage,
  weak_abilities,
  recommended_tasks: [
    {type, id, title, reason, priority}
  ]
}

规则：
- medical_knowledge 低：推荐 KnowledgeUnit + 基础 Case
- key_information 低：推荐 SP 问诊 + 基础病例
- differential_diagnosis 低：推荐复杂 Case + SP
- evidence_integration 低：推荐 Case + Guideline PICO
- clinical_decision 低：推荐 Guideline + 高阶 Case
- evidence_based_medicine 低：推荐 GuidelineLearningSession
- communication 或 humanistic_care 低：推荐 SPCase

后端：
- 修改 /api/students/{student_id}/pathway 返回 recommended_tasks。
- 保留原 recommended_case 字段以兼容旧前端。

前端：
- 修改 /student/pathway 页面，显示混合式学习任务：
  基础知识、技能、病例、指南、SP。
```

---

## Prompt 8：LLM JSON 输出与安全校验

```text
请增强 backend/app/services/llm_client.py。

目标：
增加统一 LLM 调用函数：
- chat_json(system_prompt, user_prompt, fallback)
- chat_text(system_prompt, user_prompt, fallback)

要求：
- 支持 OPENAI_API_KEY、OPENAI_BASE_URL、OPENAI_MODEL。
- 对 JSON 输出进行 json.loads 校验。
- 若解析失败，返回 fallback。
- 不让 LLM 直接写数据库。
- 所有病例生成、SP回复、SP评分、指南评分都通过结构化 service 函数调用。
- 增加最小单元测试或 smoke test 脚本，验证无 API Key 时系统仍可运行。
```

---

# 四、数据库 Schema 建议

下面是面向 MVP 的简化数据库结构。当前项目可先用 SQLite，后续再迁移 PostgreSQL。

## 1. 现有核心表保留

```sql
students (
  id integer primary key,
  name varchar(100),
  student_no varchar(50) unique,
  class_name varchar(100),
  current_stage varchar(100)
);

cases (
  id integer primary key,
  title varchar(200),
  disease_category varchar(100),
  difficulty varchar(50),
  learning_objectives text,
  chief_complaint text,
  history text,
  physical_exam text,
  lab_results text,
  imaging text,
  standard_diagnosis text,
  differential_diagnosis text,
  treatment_plan text,
  rubric text
);

case_sessions (
  id integer primary key,
  student_id integer references students(id),
  case_id integer references cases(id),
  status varchar(50),
  started_at datetime,
  completed_at datetime
);

student_answers (
  id integer primary key,
  session_id integer references case_sessions(id),
  step varchar(100),
  answer_text text,
  created_at datetime
);

ai_messages (
  id integer primary key,
  session_id integer references case_sessions(id),
  role varchar(50),
  message text,
  reasoning_step varchar(100),
  created_at datetime
);

scores (
  id integer primary key,
  session_id integer references case_sessions(id),
  total_score float,
  medical_knowledge float,
  key_information float,
  differential_diagnosis float,
  evidence_integration float,
  clinical_decision float,
  evidence_based_medicine float,
  feedback text,
  strengths text,
  weaknesses text,
  created_at datetime
);

competency_profiles (
  id integer primary key,
  student_id integer references students(id),
  medical_knowledge float,
  key_information float,
  differential_diagnosis float,
  evidence_integration float,
  clinical_decision float,
  evidence_based_medicine float,
  learning_engagement float,
  updated_at datetime
);
```

现有能力画像更新公式为：旧分数 * 0.7 + 本次分数 * 0.3。

---

## 2. 新增基础知识表

```sql
knowledge_units (
  id integer primary key,
  title varchar(200) not null,
  category varchar(100) not null,
  level varchar(50) not null,
  learning_objectives text not null,
  content text not null,
  key_points text not null,
  quiz_items text not null,
  related_case_ids text not null,
  created_at datetime
);

knowledge_progress (
  id integer primary key,
  student_id integer not null references students(id),
  knowledge_unit_id integer not null references knowledge_units(id),
  status varchar(50) default 'not_started',
  quiz_score float default 0,
  mastery_score float default 0,
  updated_at datetime
);
```

---

## 3. 新增临床技能表

```sql
clinical_skills (
  id integer primary key,
  title varchar(200) not null,
  category varchar(100) not null,
  difficulty varchar(50) not null,
  indication text not null,
  contraindication text not null,
  steps text not null,
  common_errors text not null,
  scoring_rubric text not null,
  created_at datetime
);

skill_sessions (
  id integer primary key,
  student_id integer not null references students(id),
  skill_id integer not null references clinical_skills(id),
  status varchar(50) default 'in_progress',
  submitted_steps text,
  score float,
  feedback text,
  created_at datetime,
  completed_at datetime
);
```

---

## 4. 新增循证指南表

```sql
guideline_documents (
  id integer primary key,
  title varchar(300) not null,
  organization varchar(100) not null,
  year integer not null,
  disease_category varchar(100) not null,
  source_type varchar(100) not null,
  summary text not null,
  recommendations text not null,
  pico_examples text not null,
  created_at datetime
);

guideline_learning_sessions (
  id integer primary key,
  student_id integer not null references students(id),
  guideline_id integer not null references guideline_documents(id),
  clinical_question text not null,
  pico text not null,
  answer text not null,
  score float,
  feedback text,
  created_at datetime
);
```

---

## 5. 新增 SP 表

```sql
sp_cases (
  id integer primary key,
  title varchar(200) not null,
  disease_category varchar(100) not null,
  difficulty varchar(50) not null,
  patient_profile text not null,
  opening_statement text not null,
  hidden_history text not null,
  emotional_style varchar(100) not null,
  expected_tasks text not null,
  scoring_rubric text not null,
  created_at datetime
);

sp_sessions (
  id integer primary key,
  student_id integer not null references students(id),
  sp_case_id integer not null references sp_cases(id),
  status varchar(50) default 'in_progress',
  transcript text not null,
  diagnosis_summary text,
  communication_score float,
  history_taking_score float,
  reasoning_score float,
  humanistic_care_score float,
  total_score float,
  feedback text,
  started_at datetime,
  completed_at datetime
);
```

---

## 6. 新增病例生成草稿表

```sql
generated_case_drafts (
  id integer primary key,
  teacher_prompt text not null,
  generated_payload text not null,
  status varchar(50) default 'draft',
  created_at datetime
);
```

---

# 五、后端代码骨架

## 1. main.py 注册新增路由

```python
from app.routes import (
    cases,
    sessions,
    students,
    teacher,
    knowledge,
    skills,
    guidelines,
    sp,
    case_generation,
)

app.include_router(students.router)
app.include_router(cases.router)
app.include_router(sessions.router)
app.include_router(teacher.router)
app.include_router(knowledge.router)
app.include_router(skills.router)
app.include_router(guidelines.router)
app.include_router(sp.router)
app.include_router(case_generation.router)
```

---

## 2. SP service 骨架

```python
# backend/app/services/sp_patient.py

import json
import os
from datetime import datetime

from app.services.llm_client import chat_json, chat_text


def generate_patient_reply(sp_case: dict, transcript: list[dict], student_message: str) -> str:
    fallback = rule_patient_reply(sp_case, transcript, student_message)

    if not os.getenv("OPENAI_API_KEY"):
        return fallback

    system_prompt = build_sp_system_prompt(sp_case)
    user_prompt = json.dumps(
        {
            "transcript": transcript,
            "student_message": student_message,
        },
        ensure_ascii=False,
    )

    return chat_text(system_prompt, user_prompt, fallback=fallback)


def score_sp_session(sp_case: dict, transcript: list[dict], diagnosis_summary: str) -> dict:
    fallback = rule_score_sp_session(sp_case, transcript, diagnosis_summary)

    system_prompt = build_sp_scoring_prompt(sp_case)
    user_prompt = json.dumps(
        {
            "transcript": transcript,
            "diagnosis_summary": diagnosis_summary,
        },
        ensure_ascii=False,
    )

    return chat_json(system_prompt, user_prompt, fallback=fallback)


def rule_patient_reply(sp_case: dict, transcript: list[dict], student_message: str) -> str:
    hidden = sp_case.get("hidden_history", {})
    text = student_message.lower()

    if any(key in text for key in ["哪里不舒服", "怎么了", "主要问题", "主诉"]):
        return sp_case["opening_statement"]

    if any(key in text for key in ["多久", "时间", "几天", "几个月"]):
        return hidden.get("duration", "大概有一段时间了，最近更明显。")

    if any(key in text for key in ["发热", "体温"]):
        return hidden.get("fever", "有发热，最高体温记不太清。")

    if any(key in text for key in ["疼", "关节", "肌肉"]):
        return hidden.get("pain", "有关节或肌肉不适，活动后更明显。")

    if any(key in text for key in ["担心", "害怕", "理解", "别紧张"]):
        return "谢谢医生，我确实有点担心，您这样解释我安心一些。"

    return "这个我不太确定，您可以再问得具体一点。"


def rule_score_sp_session(sp_case: dict, transcript: list[dict], diagnosis_summary: str) -> dict:
    all_text = " ".join([item.get("content", "") for item in transcript]) + diagnosis_summary

    history_score = keyword_score(all_text, ["主诉", "现病史", "既往史", "用药", "过敏", "家族史"], 50, 8)
    communication_score = keyword_score(all_text, ["您好", "理解", "担心", "解释", "可以吗"], 50, 8)
    reasoning_score = keyword_score(all_text, ["诊断", "鉴别", "支持", "排除", "检查", "治疗"], 50, 8)
    humanistic_score = keyword_score(all_text, ["担心", "焦虑", "疼痛", "隐私", "配合"], 50, 8)

    total = round(
        history_score * 0.3
        + communication_score * 0.25
        + reasoning_score * 0.3
        + humanistic_score * 0.15,
        1,
    )

    return {
        "history_taking_score": history_score,
        "communication_score": communication_score,
        "reasoning_score": reasoning_score,
        "humanistic_care_score": humanistic_score,
        "total_score": total,
        "feedback": f"SP考核总分 {total}。建议继续强化结构化问诊、共情表达和诊断总结。",
    }


def keyword_score(text: str, keywords: list[str], base: int, step: int) -> float:
    hits = sum(1 for keyword in keywords if keyword in text)
    return float(min(95, base + hits * step))
```

---

## 3. AI 病例生成 service 骨架

```python
# backend/app/services/case_generator.py

import json
import os

from app.services.llm_client import chat_json


REQUIRED_CASE_FIELDS = [
    "title",
    "disease_category",
    "difficulty",
    "learning_objectives",
    "chief_complaint",
    "history",
    "physical_exam",
    "lab_results",
    "imaging",
    "standard_diagnosis",
    "differential_diagnosis",
    "treatment_plan",
    "rubric",
]


def generate_case_payload(request: dict) -> dict:
    fallback = fallback_rule_case(request)

    if not os.getenv("OPENAI_API_KEY"):
        return fallback

    system_prompt = CASE_GENERATION_SYSTEM_PROMPT
    user_prompt = json.dumps(request, ensure_ascii=False)

    payload = chat_json(system_prompt, user_prompt, fallback=fallback)
    return validate_case_payload(payload, fallback)


def validate_case_payload(payload: dict, fallback: dict) -> dict:
    if not isinstance(payload, dict):
        return fallback

    for field in REQUIRED_CASE_FIELDS:
        if field not in payload or payload[field] in [None, "", []]:
            return fallback

    return payload


def fallback_rule_case(request: dict) -> dict:
    disease = request.get("disease_category", "系统性红斑狼疮")
    difficulty = request.get("difficulty", "基础")
    teaching_goal = request.get("teaching_goal", "训练临床推理")

    return {
        "title": f"{disease}{difficulty}训练病例",
        "disease_category": disease,
        "difficulty": difficulty,
        "learning_objectives": [
            teaching_goal,
            "提取关键临床信息",
            "建立鉴别诊断和初步处理方案",
        ],
        "chief_complaint": "患者因反复发热、乏力及关节不适就诊。",
        "history": "症状逐渐进展，伴有皮疹或实验室异常，既往史待进一步询问。",
        "physical_exam": "生命体征基本平稳，可见皮疹或关节压痛。",
        "lab_results": "炎症指标升高，自身抗体或免疫学指标异常。",
        "imaging": "影像学检查未见明确特异性改变，需结合临床判断。",
        "standard_diagnosis": disease,
        "differential_diagnosis": ["感染", "肿瘤", "其他结缔组织病"],
        "treatment_plan": "完善检查，评估疾病活动度和器官受累，结合指南制定治疗方案。",
        "rubric": {
            "medical_knowledge": "能识别疾病核心表现和诊断标准。",
            "key_information": "能提取关键阳性和阴性信息。",
            "differential_diagnosis": "能建立合理鉴别诊断。",
            "evidence_integration": "能整合支持证据和反对证据。",
            "clinical_decision": "能制定初步治疗和监测计划。",
            "evidence_based_medicine": "能引用指南或证据等级。",
        },
    }


CASE_GENERATION_SYSTEM_PROMPT = """
你是风湿免疫科临床教学病例设计专家。
请生成适合临床医学本科生训练的结构化病例。
必须只输出 JSON，不要输出 markdown。
JSON 字段必须包括：
title, disease_category, difficulty, learning_objectives, chief_complaint,
history, physical_exam, lab_results, imaging, standard_diagnosis,
differential_diagnosis, treatment_plan, rubric。
病例必须真实、教学性强、避免虚构不合理检查结果。
"""
```

---

# 六、前端代码骨架

## 1. lib/api.ts 新增方法

```ts
export type KnowledgeUnit = {
  id: number;
  title: string;
  category: string;
  level: string;
  learning_objectives: string[];
  content: string;
  key_points: string[];
  quiz_items: Record<string, unknown>[];
};

export function listKnowledgeUnits() {
  return request<KnowledgeUnit[]>("/api/knowledge");
}

export function getKnowledgeUnit(unitId: string | number) {
  return request<KnowledgeUnit>(`/api/knowledge/${unitId}`);
}

export function submitKnowledgeQuiz(unitId: number, studentId: number, answers: string[]) {
  return request(`/api/knowledge/${unitId}/quiz`, {
    method: "POST",
    body: JSON.stringify({ student_id: studentId, answers }),
  });
}

export type ClinicalSkill = {
  id: number;
  title: string;
  category: string;
  difficulty: string;
  indication: string;
  contraindication: string;
  steps: string[];
  common_errors: string[];
};

export function listSkills() {
  return request<ClinicalSkill[]>("/api/skills");
}

export function getSkill(skillId: string | number) {
  return request<ClinicalSkill>(`/api/skills/${skillId}`);
}

export function submitSkillSession(sessionId: number, submittedSteps: string[]) {
  return request(`/api/skill-sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({ submitted_steps: submittedSteps }),
  });
}

export type GuidelineDocument = {
  id: number;
  title: string;
  organization: string;
  year: number;
  disease_category: string;
  summary: string;
  recommendations: Record<string, unknown>[];
};

export function listGuidelines() {
  return request<GuidelineDocument[]>("/api/guidelines");
}

export function getGuideline(guidelineId: string | number) {
  return request<GuidelineDocument>(`/api/guidelines/${guidelineId}`);
}

export function submitPico(guidelineId: number, payload: Record<string, unknown>) {
  return request(`/api/guidelines/${guidelineId}/pico`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export type SPCase = {
  id: number;
  title: string;
  disease_category: string;
  difficulty: string;
  opening_statement: string;
  emotional_style: string;
};

export function listSPCases() {
  return request<SPCase[]>("/api/sp-cases");
}

export function startSPSession(studentId: number, spCaseId: number) {
  return request<{ session_id: number; opening_statement: string }>("/api/sp-sessions/start", {
    method: "POST",
    body: JSON.stringify({ student_id: studentId, sp_case_id: spCaseId }),
  });
}

export function sendSPMessage(sessionId: number, message: string) {
  return request(`/api/sp-sessions/${sessionId}/message`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function submitSPSession(sessionId: number, diagnosisSummary: string) {
  return request(`/api/sp-sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({ diagnosis_summary: diagnosisSummary }),
  });
}
```

---

## 2. 页面结构建议

```text
frontend/app/
  student/
    knowledge/
      page.tsx
      [unitId]/
        page.tsx
    skills/
      page.tsx
      [skillId]/
        page.tsx
    guidelines/
      page.tsx
      [guidelineId]/
        page.tsx
    sp/
      page.tsx
      [caseId]/
        page.tsx
      result/
        [sessionId]/
          page.tsx
  teacher/
    case-generator/
      page.tsx
```

---

## 3. 学生端 dashboard 新增入口

```tsx
const learningModules = [
  {
    title: "基础知识学习",
    description: "围绕疾病概念、诊断标准和基础机制进行微课与测验。",
    href: "/student/knowledge",
  },
  {
    title: "临床技能训练",
    description: "训练查体、操作步骤和安全意识。",
    href: "/student/skills",
  },
  {
    title: "循证指南学习",
    description: "通过 PICO 和指南推荐训练循证决策。",
    href: "/student/guidelines",
  },
  {
    title: "标准化病人考核",
    description: "通过虚拟患者问诊训练沟通、问诊和临床推理。",
    href: "/student/sp",
  },
];
```

---

# 七、SP 对话 Prompt 模板

## 1. SP 病人模拟 system prompt

```text
你正在扮演一名标准化病人，用于临床医学本科生问诊训练。

你必须严格遵守以下规则：

1. 你只能以患者身份回答，不要扮演医生。
2. 不要主动透露所有病史，只有当学生问到相关问题时才逐步透露。
3. 回答应符合患者语言，避免医学术语过多。
4. 如果学生问开放式问题，可以回答稍完整。
5. 如果学生问封闭式问题，只回答对应信息。
6. 如果学生表达共情，你可以表现出信任或缓解焦虑。
7. 如果学生问到病例中没有的信息，可以回答“不太清楚”或“没有注意到”。
8. 不要直接告诉学生最终诊断。
9. 不要评价学生表现。
10. 每次回复不超过120字。

病例设定：
{sp_case}

历史对话：
{transcript}

学生刚刚问：
{student_message}

请输出患者回复。
```

---

## 2. SP 评分 prompt

```text
你是临床医学 OSCE 标准化病人考核评分员。

请根据以下 SP 病例、学生问诊对话和学生最后总结进行评分。

评分维度：
1. history_taking_score：问诊完整性，0-100分
2. communication_score：沟通表达，0-100分
3. reasoning_score：临床推理，0-100分
4. humanistic_care_score：人文关怀，0-100分
5. total_score：总分，0-100分

评分标准：
- 问诊完整性：是否覆盖主诉、现病史、伴随症状、既往史、用药史、过敏史、家族史、危险因素。
- 沟通表达：是否语言清晰、结构合理、避免压迫式提问。
- 临床推理：是否能总结关键信息、提出合理诊断和鉴别诊断。
- 人文关怀：是否回应患者焦虑、疼痛、隐私和治疗担忧。

必须只输出 JSON：
{
  "history_taking_score": number,
  "communication_score": number,
  "reasoning_score": number,
  "humanistic_care_score": number,
  "total_score": number,
  "strengths": "string",
  "weaknesses": "string",
  "feedback": "string"
}

SP病例：
{sp_case}

问诊记录：
{transcript}

学生总结：
{diagnosis_summary}
```

---

# 八、病例生成 Prompt 体系

## 1. 病例生成总 prompt

```text
你是风湿免疫科临床教学病例设计专家。

请根据教师输入生成一个适合临床医学本科生训练的结构化病例。

教师输入：
- 疾病类别：{disease_category}
- 难度：{difficulty}
- 教学目标：{teaching_goal}
- 必须包含的临床元素：{required_elements}
- 目标能力维度：{target_abilities}

要求：
1. 病例必须医学合理。
2. 病例信息应适合分步释放。
3. 必须包含关键阳性信息和关键阴性信息。
4. 必须包含至少3个鉴别诊断。
5. 治疗方案应体现安全性、感染筛查、随访监测。
6. 若涉及指南，说明推荐依据，但不要编造具体不存在的文献。
7. 不要输出 markdown。
8. 只输出 JSON。

JSON 格式：
{
  "title": "",
  "disease_category": "",
  "difficulty": "",
  "learning_objectives": [],
  "chief_complaint": "",
  "history": "",
  "physical_exam": "",
  "lab_results": "",
  "imaging": "",
  "standard_diagnosis": "",
  "differential_diagnosis": [],
  "treatment_plan": "",
  "rubric": {
    "medical_knowledge": "",
    "key_information": "",
    "differential_diagnosis": "",
    "evidence_integration": "",
    "clinical_decision": "",
    "evidence_based_medicine": ""
  }
}
```

---

## 2. 基础病例生成 prompt

```text
生成一个基础难度风湿免疫病例。

重点：
- 诊断线索明确
- 干扰项少
- 适合训练疾病识别和关键信息提取
- 病例长度适中
- 不设置过多复杂合并症

疾病：{disease_category}
教学目标：{teaching_goal}

只输出符合系统 CaseCreate schema 的 JSON。
```

---

## 3. 进阶鉴别诊断病例 prompt

```text
生成一个进阶难度病例，用于训练鉴别诊断。

要求：
- 主诉可以是发热、皮疹、关节痛、肺肾综合征、肌无力等症状群。
- 至少设置3类鉴别诊断：
  1. 感染
  2. 肿瘤或血液系统疾病
  3. 自身免疫病或炎症性疾病
- 必须包含支持诊断的证据和反对其他诊断的证据。
- treatment_plan 需要体现进一步检查和初步处理策略。
- rubric 要重点强调 differential_diagnosis 和 evidence_integration。

只输出 JSON。
```

---

## 4. 高阶循证病例 prompt

```text
生成一个高阶病例，用于训练循证医学和治疗决策。

要求：
- 病例应涉及治疗选择、风险评估或指南推荐。
- 必须包含至少一个需要学生结合指南判断的问题。
- 必须体现个体化因素，例如感染风险、妊娠、肾功能、肺间质病变、老年患者、多病共存或既往治疗失败。
- treatment_plan 需包含：
  1. 治疗选择
  2. 选择依据
  3. 风险筛查
  4. 疗效监测
  5. 不良反应监测
- rubric 要突出 clinical_decision 和 evidence_based_medicine。

只输出 JSON。
```

---

## 5. SP病例生成 prompt

```text
你是 OSCE 标准化病人病例设计专家。

请生成一个 SP 问诊考核病例。

教师输入：
- 疾病类别：{disease_category}
- 难度：{difficulty}
- 考核重点：{assessment_focus}

只输出 JSON：
{
  "title": "",
  "disease_category": "",
  "difficulty": "",
  "patient_profile": {
    "name": "",
    "age": "",
    "gender": "",
    "occupation": "",
    "background": ""
  },
  "opening_statement": "",
  "hidden_history": {
    "duration": "",
    "main_symptoms": "",
    "associated_symptoms": "",
    "negative_symptoms": "",
    "past_history": "",
    "medication_history": "",
    "allergy_history": "",
    "family_history": "",
    "social_history": "",
    "concerns": ""
  },
  "emotional_style": "",
  "expected_tasks": [],
  "scoring_rubric": {
    "history_taking": "",
    "communication": "",
    "clinical_reasoning": "",
    "humanistic_care": ""
  }
}
```

---

# 九、建议最终 MVP 验收标准

完成后，系统应能跑通以下完整链条：

```text
学生登录/选择
→ 查看能力画像
→ 进入基础知识学习并完成测验
→ 完成临床技能步骤训练
→ 完成病例临床推理训练
→ 完成指南 PICO 练习
→ 完成 SP 问诊考核
→ 系统生成多维评分
→ 更新能力画像
→ 推荐下一阶段学习任务
→ 教师端查看班级短板和病例生成器
```

优先验收 5 个页面：

1. `/student/knowledge`
2. `/student/skills`
3. `/student/guidelines`
4. `/student/sp`
5. `/teacher/case-generator`

优先验收 5 个后端路由：

1. `knowledge.py`
2. `skills.py`
3. `guidelines.py`
4. `sp.py`
5. `case_generation.py`

