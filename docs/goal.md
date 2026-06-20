请帮我开发一个医学教育MVP系统，名称为“诊途：临床推理与自适应学习系统”。

系统定位：
这是一个面向临床医学本科生的病例推理训练平台，不是普通问答机器人。系统围绕“病例训练—临床推理追问—推理链分析—自动评分—能力画像—自适应学习路径推荐—教师驾驶舱”形成完整教学闭环。

技术栈要求：

1. 前端使用 Next.js + React + Tailwind CSS。
2. 后端使用 FastAPI。
3. 数据库使用 SQLite。
4. 前后端分离。
5. 图表使用 Recharts。
6. AI接口预留为兼容 OpenAI API 的调用方式。
7. MVP阶段允许使用内置模拟学生、模拟病例和模拟评分数据，但代码结构必须支持后续接入真实大模型API。
8. 不需要复杂登录系统，MVP阶段用角色切换实现学生端和教师端。

项目结构建议：

* frontend/
* backend/
* backend/app/main.py
* backend/app/database.py
* backend/app/models.py
* backend/app/schemas.py
* backend/app/routes/
* backend/app/services/
* backend/app/seed_data.py
* README.md

核心页面：

1. /student/dashboard：学生首页，显示能力画像、推荐病例、学习进度。
2. /student/case/[caseId]：病例训练页，显示病例资料、分阶段作答、临床推理追问。
3. /student/result/[sessionId]：评分反馈页，显示总分、分项评分、形成性反馈、能力画像变化、下一步推荐。
4. /student/pathway：自适应学习路径页。
5. /teacher/dashboard：教师驾驶舱，显示班级总体表现、能力短板、学生列表、教学建议。
6. /teacher/cases：病例管理页，支持查看和新增病例。

核心后端功能：

1. 返回学生首页数据。
2. 返回病例详情。
3. 保存学生分阶段回答。
4. 根据学生回答生成临床推理追问。
5. 学生提交病例后生成评分。
6. 根据评分更新能力画像。
7. 根据能力画像推荐下一步学习路径。
8. 返回教师端班级分析数据。

请先搭建完整项目骨架，并确保前端和后端能够本地运行。
要求提供：

1. 完整代码。
2. 后端启动命令。
3. 前端启动命令。
4. 数据库初始化方法。
5. README说明。

阶段1任务：请先完成“诊思径”MVP项目骨架、数据库模型和种子数据。

具体要求：

一、后端
使用 FastAPI + SQLite + SQLAlchemy。

请创建以下数据模型：

1. Student
   字段：

* id
* name
* student_no
* class_name
* current_stage

2. Case
   字段：

* id
* title
* disease_category
* difficulty
* learning_objectives
* chief_complaint
* history
* physical_exam
* lab_results
* imaging
* standard_diagnosis
* differential_diagnosis
* treatment_plan
* rubric

3. CaseSession
   字段：

* id
* student_id
* case_id
* status
* started_at
* completed_at

4. StudentAnswer
   字段：

* id
* session_id
* step
* answer_text
* created_at

5. AIMessage
   字段：

* id
* session_id
* role
* message
* reasoning_step
* created_at

6. Score
   字段：

* id
* session_id
* total_score
* medical_knowledge
* key_information
* differential_diagnosis
* evidence_integration
* clinical_decision
* evidence_based_medicine
* feedback
* strengths
* weaknesses
* created_at

7. CompetencyProfile
   字段：

* id
* student_id
* medical_knowledge
* key_information
* differential_diagnosis
* evidence_integration
* clinical_decision
* evidence_based_medicine
* learning_engagement
* updated_at

8. LearningRecommendation
   字段：

* id
* student_id
* recommended_case_id
* recommendation_reason
* pathway_stage
* created_at

二、种子数据
请写 seed_data.py，初始化：

1. 3个学生。
2. 5个风湿免疫病例：

   * SLE基础病例
   * SLE与感染鉴别病例
   * 成人Still病病例
   * ANCA相关血管炎病例
   * 皮肌炎/抗合成酶综合征病例
3. 每个学生一份初始能力画像。
4. 每个病例包含完整病例资料、标准诊断、鉴别诊断、治疗方案和评分rubric。

三、API
请实现：

* GET /api/students
* GET /api/students/{student_id}
* GET /api/cases
* GET /api/cases/{case_id}
* GET /api/students/{student_id}/competency
* GET /api/students/{student_id}/dashboard

四、前端
请创建基础页面：

1. 首页 / ，可以选择学生端或教师端。
2. /student/dashboard 页面，允许选择一个学生，并显示：

   * 学生基本信息
   * 当前能力画像
   * 推荐病例卡片
   * 最近学习建议
3. 使用 Recharts 画能力雷达图。

五、验收标准

1. 后端启动后可以访问 OpenAPI 文档。
2. seed_data.py 可以成功初始化数据库。
3. 前端可以显示学生首页和能力雷达图。
4. 所有数据可以先使用真实SQLite数据，不要只写死在前端。

阶段2任务：请完成病例训练页和临床推理追问功能。

一、后端新增接口
请实现以下API：

1. POST /api/sessions/start
   输入：

* student_id
* case_id
  功能：
  创建一个 CaseSession，状态为 in_progress。

2. GET /api/sessions/{session_id}
   功能：
   返回当前训练session、病例详情、学生已提交的回答、AI追问记录。

3. POST /api/sessions/{session_id}/answers
   输入：

* step
* answer_text
  功能：
  保存学生在某个阶段的回答。

4. POST /api/sessions/{session_id}/coach
   输入：

* step
* answer_text
  功能：
  根据病例内容、当前阶段和学生回答，返回一个临床推理追问。

二、临床推理追问逻辑
请先实现规则版，不依赖真实大模型API，但要保留 llm_client.py，方便后续接入OpenAI兼容API。

追问规则示例：

step = key_information：
如果学生回答太短，则追问：
“请进一步提取本病例中的关键阳性表现、关键阴性表现和异常检查结果。”

step = initial_diagnosis：
追问：
“你为什么首先考虑这个诊断？请分别从症状、实验室检查和器官受累三个方面说明证据。”

step = differential_diagnosis：
如果没有提到感染、AOSD、HLH、淋巴瘤等关键词，则追问：
“你的鉴别诊断还不够完整。除当前诊断外，还需要考虑感染、成人Still病、HLH或血液系统疾病吗？请说明如何排除。”

step = examination：
追问：
“为了验证你的诊断和评估疾病活动度，还需要补充哪些检查？这些检查分别解决什么临床问题？”

step = treatment：
追问：
“请说明治疗方案的依据、风险评估和需要监测的不良反应。”

三、前端病例训练页
请实现 /student/case/[caseId] 页面。

页面布局：
左侧：病例资料卡片，包括主诉、现病史、体格检查、实验室检查、影像资料。
右侧：临床推理训练区。

训练区分为5个步骤：

1. 关键信息提取
2. 初步诊断及依据
3. 鉴别诊断
4. 进一步检查
5. 治疗方案

每一步包括：

* 问题提示
* 学生输入框
* 保存回答按钮
* 获取追问按钮
* 显示系统追问内容

四、前端交互要求

1. 从学生首页点击推荐病例后，自动创建session并进入病例训练页。
2. 每一步回答都能保存到后端。
3. 点击“获取追问”后，显示系统追问。
4. 页面顶部显示当前病例标题、难度和训练目标。
5. 页面底部有“提交病例并生成反馈”按钮，先预留跳转到结果页。

五、验收标准

1. 可以从学生首页进入病例训练。
2. 可以完成5个阶段的回答。
3. 每个阶段都可以生成追问。
4. 刷新页面后，已保存回答仍然存在。
5. 后端数据库中能看到 StudentAnswer 和 AIMessage 记录。

阶段3任务：请完成病例提交、自动评分、形成性反馈和能力画像更新。

一、后端新增接口

1. POST /api/sessions/{session_id}/submit
功能：
- 读取该session下所有学生回答
- 根据规则生成分项评分
- 生成形成性反馈
- 写入 Score 表
- 更新 CompetencyProfile
- 生成 LearningRecommendation
- 将 CaseSession 状态改为 completed
- 返回 score_id 和 result summary

2. GET /api/sessions/{session_id}/result
功能：
返回：
- 病例信息
- 学生所有回答
- Score评分
- 更新后的能力画像
- 下一步学习推荐

二、评分规则

请先用规则评分，不依赖真实LLM，但保留 scoring_llm.py 以便未来替换。

评分维度：
1. medical_knowledge，医学知识，满分100
2. key_information，关键信息提取，满分100
3. differential_diagnosis，鉴别诊断，满分100
4. evidence_integration，证据整合，满分100
5. clinical_decision，临床决策，满分100
6. evidence_based_medicine，循证医学，满分100

总分计算：
total_score =
medical_knowledge * 0.20 +
key_information * 0.20 +
differential_diagnosis * 0.20 +
evidence_integration * 0.15 +
clinical_decision * 0.15 +
evidence_based_medicine * 0.10

规则示例：
- 如果回答中包含病例标准诊断关键词，medical_knowledge 提高。
- 如果关键信息提取中包含“发热、皮疹、蛋白尿、ANA、血细胞减少”等关键词，key_information 提高。
- 如果鉴别诊断中提到“感染、AOSD、HLH、淋巴瘤、MCTD、APS”等，differential_diagnosis 提高。
- 如果学生能说明“支持证据”和“反对证据”，evidence_integration 提高。
- 如果治疗方案中提到“激素、免疫抑制剂、感染筛查、器官受累评估、随访监测”，clinical_decision 提高。
- 如果提到“指南、证据、文献、推荐级别”，evidence_based_medicine 提高。

三、形成性反馈
根据分项评分生成：
1. 总体评价
2. 主要优点
3. 主要不足
4. 下一步学习建议

示例：
“你的初步诊断方向较准确，能够识别SLE的核心表现。但鉴别诊断仍偏窄，对感染、成人Still病和HLH的排除逻辑不足。建议下一步完成‘发热+皮疹+血细胞减少’专题训练。”

四、能力画像更新
更新方式：
新画像分数 = 旧分数 * 0.7 + 本次分项分数 * 0.3

learning_engagement 根据完成病例次数略微提高。

五、学习路径推荐规则
如果 differential_diagnosis < 60：
推荐“SLE与感染鉴别病例”或“成人Still病病例”。

如果 medical_knowledge < 60：
推荐“SLE基础病例”。

如果 clinical_decision < 60：
推荐“ANCA相关血管炎病例”或治疗决策相关病例。

如果 total_score > 85：
推荐更高难度病例，如“皮肌炎/抗合成酶综合征病例”。

六、前端结果页
请实现 /student/result/[sessionId] 页面。

页面显示：
1. 病例标题
2. 总分
3. 六个分项评分
4. 能力雷达图
5. 主要优点
6. 主要不足
7. 形成性反馈
8. 下一步推荐病例
9. 返回学习路径按钮

七、验收标准
1. 学生在病例训练页点击提交后，可以生成评分。
2. 评分写入数据库。
3. 能力画像被更新。
4. 系统生成下一步推荐病例。
5. 前端结果页完整显示评分、反馈、雷达图和推荐路径。

阶段4任务：请完成学生端自适应学习路径页面。

一、后端接口

1. GET /api/students/{student_id}/pathway
返回：
- 学生基本信息
- 当前能力画像
- 已完成病例列表
- 当前推荐病例
- 推荐理由
- 学习阶段
- 下一阶段目标

二、路径阶段设计

请将学习路径分为4个阶段：

stage_1_basic_recognition：
基础疾病识别

stage_2_differential_reasoning：
复杂症状鉴别

stage_3_clinical_decision：
治疗决策训练

stage_4_evidence_based_learning：
循证医学与文献训练

三、路径推荐逻辑

如果学生医学知识或关键信息提取薄弱：
当前阶段为 stage_1_basic_recognition。

如果学生鉴别诊断薄弱：
当前阶段为 stage_2_differential_reasoning。

如果学生治疗决策薄弱：
当前阶段为 stage_3_clinical_decision。

如果学生各项能力较高：
当前阶段为 stage_4_evidence_based_learning。

四、前端页面
请实现 /student/pathway。

页面内容：
1. 学习路径时间线
2. 当前所在阶段高亮
3. 已完成病例卡片
4. 当前推荐病例卡片
5. 推荐理由
6. 需要提升的能力
7. “开始推荐病例”按钮

五、视觉要求
使用卡片式布局。
学习路径用横向或纵向Step Timeline展示。
当前阶段用明显样式标识。
能力短板用标签显示，例如：
- 鉴别诊断不足
- 证据整合不足
- 治疗决策不足

六、验收标准
1. 学生可以看到自己的完整学习路径。
2. 当前阶段能根据能力画像变化。
3. 点击推荐病例可以进入病例训练。
4. 页面能体现“自适应学习路径”概念，而不是简单病例列表。

阶段5任务：请完成教师驾驶舱页面。

一、后端接口

1. GET /api/teacher/dashboard

返回：
- 学生总数
- 已完成训练次数
- 班级平均总分
- 班级平均能力画像
- 六个能力维度的平均分
- 班级共性短板
- 推荐教学重点
- 学生列表及每名学生的能力短板
- 最近病例完成记录

二、班级共性短板规则
计算班级六个能力维度平均分。
低于60的维度列为明显短板。
60-70的维度列为需要加强。
根据最低的2个维度生成教学建议。

示例：
如果 differential_diagnosis 最低：
教学建议：
“本班学生鉴别诊断能力相对薄弱，建议下一次课堂增加SLE、感染、AOSD、HLH的对比式病例讨论。”

如果 evidence_based_medicine 最低：
教学建议：
“本班学生循证医学意识不足，建议增加指南阅读和治疗证据分级训练。”

三、前端页面
请实现 /teacher/dashboard。

页面内容：
1. 顶部统计卡片：
   - 学生人数
   - 完成病例数
   - 平均分
   - 平均能力提升，可用模拟值
2. 班级能力雷达图
3. 共性短板列表
4. 推荐教学重点
5. 学生表现表格
6. 最近训练记录

四、学生表格字段
- 学生姓名
- 当前阶段
- 最近得分
- 最弱能力
- 推荐训练方向
- 查看详情按钮，可以先不实现详情页

五、验收标准
1. 教师端能看到班级整体数据。
2. 教师端能看到共性短板和教学建议。
3. 数据来自后端计算，不要完全写死在前端。
4. 页面适合用于课题申报书截图展示。

阶段6任务：请完成病例管理页、整体UI优化和README文档。

一、病例管理后端接口
请实现：
1. GET /api/teacher/cases
2. POST /api/teacher/cases
3. PUT /api/teacher/cases/{case_id}
4. DELETE /api/teacher/cases/{case_id}，可以软删除或直接删除

二、病例管理前端页面
请实现 /teacher/cases。

功能：
1. 显示病例列表
2. 查看病例详情
3. 新增病例
4. 编辑病例
5. 删除病例

病例表单字段：
- 病例标题
- 疾病类别
- 难度
- 学习目标
- 主诉
- 现病史
- 体格检查
- 实验室检查
- 影像资料
- 标准诊断
- 鉴别诊断
- 治疗方案
- 评分Rubric

三、整体UI优化
请统一：
1. 顶部导航栏
2. 学生端和教师端入口
3. 卡片样式
4. 按钮样式
5. 页面留白
6. 中文字体显示
7. 移动端基本适配

四、README
请补充README，内容包括：
1. 项目名称
2. 系统简介
3. 核心功能
4. 技术栈
5. 后端启动方法
6. 前端启动方法
7. 数据库初始化方法
8. 环境变量配置方法
9. 如何接入真实OpenAI兼容API
10. MVP功能说明
11. 后续开发路线

五、AI接口预留
请在 backend/app/services/llm_client.py 中预留函数：

generate_reasoning_question(case, step, student_answer)
score_student_answer(case, answers, rubric)
generate_learning_recommendation(profile, recent_scores, cases)

默认使用规则逻辑。
如果环境变量 OPENAI_API_KEY 存在，则可以走OpenAI兼容接口。
如果没有API KEY，则自动使用本地规则版，不影响系统运行。

六、验收标准
1. 前后端均可独立启动。
2. 初始化数据库后可完整跑通：
   学生首页 → 推荐病例 → 病例训练 → AI追问 → 提交 → 评分反馈 → 能力画像更新 → 路径推荐 → 教师驾驶舱。
3. README清楚说明如何运行。
4. 页面可以用于课题申报书截图。
5. 代码结构清晰，方便后续扩展为正式系统。

