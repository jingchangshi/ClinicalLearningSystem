# C01 · 教学闭环演示走查（SLE 病例端到端）

> 本文件描述的是**在验证栈上真实点过的路径**：后端 `http://127.0.0.1:8201`、前端
> `http://127.0.0.1:8202`，一次性数据库 `/tmp/clinpath-demo-verify/verify.db`。
> 每条路由、每个标题都是从页面实际渲染的文本抄下来的，不是设计稿。
>
> **能证明什么、不能证明什么**：这条走查证明 ClinPath 的「教学证据 → 训练 → 形成性评价
> → 学习证据 → 能力模型 → 自适应推荐 → 教师复核 → 更新学习者模型」闭环**在系统里跑得通、
> 每一步都有可追溯的数据**。它**不证明教学有效性**，也不构成任何真实课堂的观察记录。

- 验证栈运行版本：`1d4ef482`（`git_dirty: true`，工作区含未提交改动），schema `20260915_06`
- 该版本是**开发/验证栈**，不是生产环境 `clinpath.1031989.xyz`（生产为 `8100/8101`）
- 走查用例：病例 ID `1`，「SLE基础病例」，会话 ID `1`，学生账号 `student1`（李明）
- 教师账号 `verify_teacher`（验收教师，风湿免疫科）

## 0. 角色与账号

| 角色 | 账号 | 可见范围 |
| --- | --- | --- |
| 学生 | `student1`（李明，202601001，临床医学2023级1班） | 只读自己的会话、证据与路径 |
| 教师 | `verify_teacher`（验收教师） | 全班画像、复核、干预、研究导出、模拟研究页 |

学生**永远看不到** `standard_diagnosis`、`treatment_plan`、`rubric` 与 SP 隐藏病史：
`GET /api/cases/{id}` 对学生返回的字段只有主诉/现病史/体格检查/实验室/影像/学习目标
（已用 curl 核对，见 `C02_evidence/`）。学生自己的 `GET /api/sessions/{id}/result` 只返回
他自己写过的答案与评分，不返回 rubric 原文。

---

## 走查步骤

### 步骤 1 · 学生登录 → 学习首页（课前诊断入口）

| 项目 | 内容 |
| --- | --- |
| 环节 | 课前诊断：学生看到自己的当前能力画像、短板与推荐任务 |
| 账号角色 | 学生 `student1` |
| 页面路由 | `/login` → `/student/dashboard` |
| 该页面显示什么 | 一级标题「ClinPath 学生临床能力成长中心」；副标题「基于多模块训练数据形成能力画像与个性化学习路径。」；四个指标卡「综合胜任力指数 66」「八维能力画像均值」「已完成训练 1」「当前主要短板 循证医学 当前分数 53.1」；「五模块训练入口矩阵」（基础知识学习 / 临床技能训练 / 临床思维训练 / 循证指南学习 / SP模拟考核）；「能力缺口诊断」；「AI 个性化学习推荐」；「最近学习记录」 |
| 数据来源 | **真实 API**：`GET /api/student/dashboard`（确定性读，无模型调用）；推荐理由文案为缓存中的 `recommendation_explanation`，本次由 AI 生成并已入库 |
| 证据文件名 | `C04_screenshots/01_student_dashboard.png`、`C02_evidence/13_student_dashboard.json` |

### 步骤 2 · 进入病例训练 → 五阶段作答

| 项目 | 内容 |
| --- | --- |
| 环节 | 临床思维训练：SLE 基础病例，五个必答推理阶段 |
| 账号角色 | 学生 `student1` |
| 页面路由 | `/student/case/1` |
| 该页面显示什么 | 标题「SLE基础病例」，分类行「系统性红斑狼疮 · 基础」，三个学习目标（识别SLE核心表现 / 理解分类标准 / 制定初始评估计划）；病史分区「主诉」「现病史」「体格检查」「实验室检查」「影像资料」；阶段页签依次为「关键信息提取」「初步诊断及依据」「鉴别诊断」「进一步检查」「治疗方案」；当前阶段提示语（如「提取关键阳性表现、关键阴性表现和异常检查结果。」）；操作按钮「保存回答」「开始追问」「提交病例并生成反馈」 |
| 数据来源 | **真实 API**：`GET /api/cases/1`（患者资料）、`GET /api/system/reasoning-steps`（五个阶段定义）；学生输入为学生本人所写 |
| 证据文件名 | `C04_screenshots/02_case_training.png`、`C02_evidence/03_answer_S1.json` … `07_answer_S5.json` |

五个阶段的提交顺序与接口：`POST /api/sessions/start` → `POST /api/sessions/{id}/answers`
（每阶段一次，`(session, step)` 唯一，重复保存覆盖旧文本）→ 最后 `POST /api/sessions/{id}/submit`。

### 步骤 3 · AI/规则追问及其来源

| 项目 | 内容 |
| --- | --- |
| 环节 | 形成性追问：导师针对学生刚写下的鉴别诊断提出一个反问 |
| 账号角色 | 学生 `student1` |
| 页面路由 | `/student/case/1` 的「开始追问」；历史会话在 `/student/result/1` 的「我的病例推理过程」中回看 |
| 该页面显示什么 | 第 3 阶段「鉴别诊断」下的「AI 导师追问与我的回复」气泡；本次追问原文：「你提到要鉴别感染，但患者已有ANA高滴度、抗dsDNA阳性和补体下降——这些证据如何影响你把感染排在鉴别首位？」；结果页对没有追问的阶段显示「本阶段没有 AI 导师追问记录。」 |
| 数据来源 | **AI**：`POST /api/sessions/1/tutor`，`task_type=tutor_question`，`provider=deepseek`，`model=deepseek-flash`，`success=true`，`latency_ms=1330`（审计事件 id 1）；规则状态（`evidence_already_covered` / `missing_reasoning_elements` / `safety_gap`）由 `tutor_service` 确定性生成，与模型输出一并入库 |
| 证据文件名 | `C04_screenshots/03_tutor_question.png`、`C02_evidence/08_tutor_S3.json`、`C02_evidence/20_ai_invocations.json` |

> **诚实标注**：本次追问是**真实模型调用**。同一会话的**评分**是规则降级（见步骤 4），
> 两者不能混为一谈。页面用「AI 导师追问」和「规则降级评价（AI 当前不可用）」两种不同
> 措辞区分，不会把规则结果说成 AI。

### 步骤 4 · 提交并生成评分反馈

| 项目 | 内容 |
| --- | --- |
| 环节 | 形成性评价：六维评分、总分、优势/不足与改进建议 |
| 账号角色 | 学生 `student1` |
| 页面路由 | `/student/result/1` |
| 该页面显示什么 | 标题「病例训练评分反馈」；「训练时间 2026-10-18 09:28 · 用时约 1 分钟」；总分 **72.6**；评价方式徽标「**规则降级评价（AI 当前不可用）**」；「形成性评价，仅供教学参考，最终评价由教师确认。」；「教师已确认」；「六项分项评分」条形图（医学知识 91.0 / 关键信息提取 74.0 / 鉴别诊断 75.0 / 证据整合 61.0 / 临床决策 67.0 / 循证医学 54.0）；「更新后的能力画像」雷达图；「评分依据、遗漏点与安全提示」（每个维度标注「规则评价 · 置信度 N%」及命中要点、遗漏点）；「改进建议」「主要优点」「主要不足」「下一步推荐病例」；「我的病例推理过程」 |
| 数据来源 | **规则**（本次）：`evaluation_mode=rule_fallback`，`degraded=true`，`provider=null`，`model=null`，`rule_score=72.6`，`ai_score=null`，`evaluator_version=hybrid-v1`，`prompt_version=case-evaluation-v1`，`rubric_version=case-rubric-v1`。降级原因见审计：`case_evaluation` 调用 4 次全部失败，`error_type=Timeout`，累计 `latency_ms=37581`，`fallback_used=true` |
| 证据文件名 | `C04_screenshots/04_result_feedback.png`、`C04_screenshots/05_result_reasoning.png`、`C02_evidence/09_submit.json`、`C02_evidence/10_result.json`、`C02_evidence/20_ai_invocations.json` |

> 这是**必须如实呈现**的一次：AI 评分在该次提交中超时（4 次调用 / 37.6 秒），系统按
> 规则给出 72.6 分并明确标注 `rule_fallback`，审计留有 `error_type=Timeout` 记录。
> 演示时应把它当作「AI 不可用时系统仍可用且不伪装成 AI」的例子来讲，而不是隐藏。

### 步骤 5 · 学习证据与能力模型更新

| 项目 | 内容 |
| --- | --- |
| 环节 | 学习证据落库 → 能力画像重算 |
| 账号角色 | 学生 / 教师（同一份证据的两个视角） |
| 页面路由 | 学生：`/student/dashboard`、`/student/pathway`；教师：`/teacher/students/1` |
| 该页面显示什么 | 教师页标题「李明 学习画像」，副标题「临床医学2023级1班 · 当前阶段2：复杂症状鉴别 · …」；「九维能力画像」雷达；「阶段性学习表现趋势」；「学习证据事件 共 2 条，默认显示最近 2 条」，表格列为「学习活动 / 训练内容 / 训练得分 / 能力变化 / 完成时间」，其中一行显示「医学知识 58 → 67.9（+9.9）」「鉴别诊断 55 → 61（+6）」「关键信息提取 62 → 65.6（+3.6）」「另有 3 项能力更新」；「推荐训练任务」 |
| 数据来源 | **真实 API**：`GET /api/teacher/students/1/learning-profile`、`GET /api/student/competency`；能力变化来自 `learning_evidence_events.competency_updates_json`，由 `competency_projector` 确定性计算，格式化为中文由服务端 `display_labels` 完成 |
| 证据文件名 | `C04_screenshots/10_student_learning_profile.png`、`C04_screenshots/11_evidence_events.png`、`C02_evidence/12_student_pathway.json` |

一条训练不会重复计入能力：`(session, step)` 唯一，且证据事件按 `case_session_scored`
去重（`backend/tests/` 覆盖）。

### 步骤 6 · 专家复核与教师干预

| 项目 | 内容 |
| --- | --- |
| 环节 | 教师复核评分（保留 AI/规则原分）→ 记录教学干预 → 触发重算 |
| 账号角色 | 教师 `verify_teacher` |
| 页面路由 | `/teacher/score-review`、`/teacher/interventions` |
| 该页面显示什么 | 复核页标题「教师评分复核」，说明「AI形成性评价仅供教学参考，最终评价由教师确认。」；「待复核病例评分」表（学生 李明 / AI评分 72.6 / 状态 已确认 / 复核）；「复核记录」表列为「证据事件 / AI评分 / 教师评分 / 差值 / 备注」，本次一行：`1 / 72.6 / 73.7 / 1.1 / 教师复核：规则回退评分低估了循证依据维度…`。干预页标题「教学干预记录」，说明「记录教师基于班级短板采取的教学调整，用于教学质量改进闭环。」；卡片「第7周增设"指南推荐等级与PICO构建"小课」+「专题小课」+「目标能力：循证医学」 |
| 数据来源 | **真实 API**：`GET /api/teacher/reviewable-evidence`、`POST /api/teacher/reviews`（六维确认分 → `confirmed_total` 算总分 73.7）、`POST /api/teacher/interventions`、`GET /api/teacher/reviews`。复核保留了 `ai_score=72.6`、`teacher_score=73.7`、`agreement_delta=1.1` 与原始 `confirmed_dimensions` |
| 证据文件名 | `C04_screenshots/12_score_review.png`、`C04_screenshots/13_interventions.png`、`C02_evidence/14_teacher_reviewable_evidence.json`、`C02_evidence/16_teacher_review_created.json`、`C02_evidence/17_teacher_reviews.json`、`C02_evidence/18_teacher_intervention_created.json` |

### 步骤 7 · 教师驾驶舱：班级诊断与自适应推荐

| 项目 | 内容 |
| --- | --- |
| 环节 | 教师看班级短板、AI 教学建议，并回到学生画像 |
| 账号角色 | 教师 `verify_teacher` |
| 页面路由 | `/teacher/dashboard` |
| 该页面显示什么 | 标题「教师精准教学驾驶舱」；指标卡「参与学生 3」「完成训练总次数 1（知识0 / 技能0 / 病例1 / 指南0 / SP0）」「平均能力提升 +0%」「当前共性短板 循证医学」；「班级能力热力图」（9 行能力 × 3 名学生，`data-testid="class-heatmap"`）；「班级能力画像」九维雷达 + 「共性短板与建议」；「AI 教学干预建议」；「教学闭环」（学生训练数据 → 班级短板识别 → 教师教学调整 → 再训练 → 效果评价）；「教学洞察」标注「AI 生成」，附「AI 洞察仅用于教学参考；班级能力画像与评分始终由结构化证据计算。」；「学生表现」表；「最近训练记录」 |
| 数据来源 | **真实 API + AI**：`GET /api/teacher/dashboard` 的数值全部确定性计算；「教学洞察」段落来自缓存中的 `teacher_insight`（`task_type=teacher_insight`，`success=true`），页面明确标注「AI 生成」。推荐排序本身是确定性的，模型只改写措辞 |
| 证据文件名 | `C04_screenshots/08_teacher_dashboard_top.png`、`C04_screenshots/09_teacher_dashboard_profile.png`、`C02_evidence/15_teacher_dashboard.json` |

### 步骤 8 · 学生训练复盘（回到学习者模型）

| 项目 | 内容 |
| --- | --- |
| 环节 | 学生回看历史会话的完整推理、导师对话与教师确认结果 |
| 账号角色 | 学生 `student1` |
| 页面路由 | `/student/history` → `/student/result/1` → 「我的病例推理过程」 |
| 该页面显示什么 | 记录页标题「我的病例学习记录」，一行「SLE基础病例 / 2026-10-18 09:29 / 得分 72.6 · 查看复盘」；复盘页五个阶段逐条列出「我的最终回答」，第 3 阶段额外显示「AI 导师追问与我的回复」气泡；「评分依据」区首行显示「规则降级评价（AI 当前不可用）；教师确认总分：73.7」；页尾操作「返回学习记录」「返回学习路径」 |
| 数据来源 | **真实 API（历史读，不重新生成）**：`GET /api/student/history`、`GET /api/sessions/1/result`。该接口是历史读：不重新调用模型，`tutor_state_json` 不出服务器 |
| 证据文件名 | `C04_screenshots/05_result_reasoning.png`、`C04_screenshots/07_student_history.png`、`C02_evidence/11_student_history.json`、`C02_evidence/23_result_after_review.json` |

### 步骤 9 · 研究数据与合成研究演示（数据留痕，不属于教学闭环本体）

| 项目 | 内容 |
| --- | --- |
| 环节 | 教师导出匿名化研究数据；另有一页独立的**合成**研究演示，与真实数据严格分开 |
| 账号角色 | 教师 `verify_teacher` |
| 页面路由 | `/teacher/research-export`、`/teacher/research-demo` |
| 该页面显示什么 | 真实导出页标题「匿名化研究数据」，正文「本页是**真实学习记录**的匿名化导出，不包含任何合成研究数据。合成研究演示在独立页面展示。」；预览表列「匿名学生编号 / 班级 / 学习模块 / 训练得分 / 记录时间」，行为 `S0001 / 临床医学2023级1班 / 病例推理训练 / 72.6`；「下载完整匿名化 CSV」。演示页标题「合成教学研究演示」，页面顶部**吸顶**黄色横幅「合成教学研究演示｜虚拟学生、虚拟评分者｜不代表真实教学成效」，其下「数据集 synthetic_v1 · 随机种子 20261018 · 全部记录标记 SYNTHETIC_DEMO_NOT_REAL_STUDENTS」 |
| 数据来源 | 真实导出：**真实 API** `GET /api/teacher/export/research-data`。演示页：**合成**数据，由 `backend/app/services/demo_research.py` 从 `demo_research/synthetic_v1/` 只读加载，**不打开数据库会话**，学生角色请求返回 403 |
| 证据文件名 | `C04_screenshots/16_research_export.png`、`C04_screenshots/14_research_demo_top.png`、`C04_screenshots/15_research_demo_students.png` |

### 步骤 10 · 运行状态页（版本与 AI 审计）

| 项目 | 内容 |
| --- | --- |
| 环节 | 30 秒内确认「浏览器里跑的是哪一版」以及 AI 是否真的可用 |
| 账号角色 | 教师 `verify_teacher` |
| 页面路由 | `/teacher/runtime` |
| 该页面显示什么 | 标题「运行状态」；「部署版本」：Environment `development`、Backend git SHA `1d4ef482 (working tree has local changes)`、Frontend build SHA `1d4ef48-dirty`、Schema revision `20260915_06`、Backend runtime `python 3.11`；「AI Runtime」：Provider `deepseek`、Model `deepseek-flash`、Reachable「未探测」、Last error type `Timeout`、Timeout/retries `12s / 2`、Calls/failures/fallbacks `6 / 1 / 1`；「AI 调用审计」按 `task_type` 汇总，并有「最近事件」列表；页面声明「该页面不会显示任何 API Key、Authorization 头或 provider 原始返回内容。」 |
| 数据来源 | **真实 API**：`GET /api/system/version`、`GET /api/system/ai-status`、`GET /api/system/ai-invocations` |
| 证据文件名 | `C04_screenshots/17_runtime.png`、`C02_evidence/22_system_version.json`、`C02_evidence/21_ai_status.json`、`C02_evidence/20_ai_invocations.json` |

---

## 实测路由清单（Playwright 实际打开并读取标题）

### 学生端

| 路由 | 实际渲染的标题 | 状态 |
| --- | --- | --- |
| `/student/dashboard` | ClinPath 学生临床能力成长中心 | 已核实 |
| `/student/case/1` | SLE基础病例 | 已核实 |
| `/student/result/1` | 病例训练评分反馈 | 已核实 |
| `/student/history` | 我的病例学习记录 | 已核实 |
| `/student/pathway` | AI个性化学习路径 | 已核实 |
| `/student/profile` | 李明 学习档案 | 已核实 |
| `/student/skills` | OSCE 操作站练习 | 已核实 |
| `/student/knowledge` | 风湿免疫核心知识单元 | 已核实 |
| `/student/sp` | 问诊与沟通考核 | 已核实 |
| `/student/guidelines` | 指南推荐与 PICO 训练 | 已核实 |

### 教师端

| 路由 | 实际渲染的标题 | 状态 |
| --- | --- | --- |
| `/teacher/dashboard` | 教师精准教学驾驶舱 | 已核实 |
| `/teacher/students` | 学生总览 | 已核实 |
| `/teacher/students/1` | 李明 学习画像 | 已核实 |
| `/teacher/score-review` | 教师评分复核 | 已核实 |
| `/teacher/interventions` | 教学干预记录 | 已核实 |
| `/teacher/research-export` | 匿名化研究数据 | 已核实 |
| `/teacher/research-demo` | 合成教学研究演示 | 已核实 |
| `/teacher/runtime` | 运行状态 | 已核实 |
| `/teacher/cases` | 病例管理 | 已核实（仅标题） |
| `/teacher/case-generator` | AI 病例生成器 | 已核实（仅标题） |

## 未验证项

| 项目 | 原因 |
| --- | --- |
| SP 问诊（`/student/sp/{caseId}`）与技能站（`/student/skills/{skillId}`）的完整作答—评分闭环 | 本轮走查只到列表页标题，未开新会话；列表页已确认存在 |
| 知识测验（`/student/knowledge/{unitId}/quiz`）与指南 PICO 作答 | 同上，未开新会话 |
| AI 评分成功路径（`evaluation_mode=ai`） | 本次提交超时降级；未在验证栈上取得一次成功的 AI 评分 |
| 生产环境 `clinpath.1031989.xyz` 的同一条走查 | 约束禁止触碰生产；本文件只覆盖验证栈 |
| 真实课堂中教师如何使用这套页面 | 需要真实教师参与，不属于本工作包 |

## 结论

闭环的九个环节在验证栈上全部走通，且每一步都有落库证据与页面可见的标注。
**其中「评分」这一步本次走的是规则降级路径**，演示与申报材料中应如实说明，
不能把它描述为 AI 评分。系统在教学有效性上不提供任何证据，本文件也不提供。
