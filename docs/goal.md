目标：继续完善 jingchangshi/ClinicalLearningSystem 仓库，在 commit fbf140b3891e22be99f42e0b122590df98864a78 的基础上，将 ClinPath 从“可展示原型系统”进一步升级为能够支撑课题申请、教学试点、形成性评价研究和后续结题数据产出的 AI 辅助临床教学系统。

当前课题申请书主题：
《基于多模态学习证据的人工智能辅助医学生个性化学习与自适应教学路径构建研究》

系统目标：
ClinPath 应支撑“基础知识学习、临床技能训练、临床思维训练、循证指南学习、SP-OSCE标准化病人考核”五大模块，形成“多模态学习证据采集 → 多维度能力画像 → AI短板诊断 → 自适应学习路径推荐 → 教师精准干预 → 再训练评价”的医学教育闭环。

一、当前系统状态

当前已经完成：

1. /demo 作为独立图版系统，用于课题申请书截图。
2. /student/dashboard 已升级为“ClinPath 学生临床能力成长中心”。
3. /student/pathway 已升级为真实版 AI 个性化学习路径页面。
4. /teacher/dashboard 已升级为教师精准教学驾驶舱。
5. 后端已新增 learning_evidence_service.py，可统计知识、技能、病例、指南、SP五类学习证据。
6. serializers.py 已支持 expanded_chart_data，前端可显示八维能力画像。
7. 教师端已支持 training_total_count、module_counts、class_heatmap、teaching_interventions 等字段。

二、总体开发原则

1. 保留 /demo，不破坏任何 demo view。
2. 不破坏现有 API 和前端页面。
3. 所有新功能必须服务课题申请书中提出的“多模态学习证据、形成性评价、能力画像、自适应路径、教师干预”。
4. 真实业务页面必须使用后端真实数据，不使用硬编码 demo 数据。
5. 兼容现有 SQLite 数据库，新增字段时提供自动补齐或 fallback。
6. 使用现有技术栈：FastAPI、SQLAlchemy、Next.js、React、Tailwind、Recharts、lucide-react。
7. 不引入大型新依赖。
8. 完成后确保后端可启动、前端 npm run typecheck 和 npm run build 通过。

三、第一阶段：把八维能力画像从“显示层”做成“真实能力模型”

当前问题：
expanded_chart_data 中的 skill_operation 是由 clinical_decision 和 key_information 均值估算；communication 和 humanistic_care 来自最近一次 SP 或默认值。这适合展示，但不足以支撑研究。

开发目标：
让八维能力画像真实进入 CompetencyProfile 和路径推荐逻辑。

后端修改：

1. 修改 backend/app/models.py 中 CompetencyProfile：
   新增字段：

* skill_operation: Float，默认 75
* communication: Float，默认 75
* humanistic_care: Float，默认 75

2. 兼容旧数据库：
   在应用启动或 seed/init 阶段检查 SQLite 是否缺少这些列。
   如果缺少，则执行 ALTER TABLE 自动增加列，避免旧数据库报错。
   或提供明确的迁移脚本 backend/scripts/migrate_competency_profile.py。

3. 修改 backend/app/services/serializers.py：

* 保留 ABILITY_LABELS。
* 新增 ALL_COMPETENCIES：
  medical_knowledge
  skill_operation
  key_information
  differential_diagnosis
  evidence_integration
  clinical_decision
  evidence_based_medicine
  communication
  humanistic_care
* chart_data 可继续保留六维，用于旧页面兼容。
* expanded_chart_data 使用数据库真实八维，不再用估算值。
* 如果数据库字段为空，才使用 fallback。

4. 修改 backend/app/services/recommendation_service.py：
   当前 weakest_abilities 只看 CORE_ABILITIES 六维。
   新增参数 use_expanded=True。
   路径推荐应纳入：

* skill_operation
* communication
* humanistic_care

推荐规则：

* skill_operation 低：推荐 clinical_skill
* communication 低：推荐 sp_case
* humanistic_care 低：推荐 sp_case
* evidence_based_medicine 低：推荐 guideline
* differential_diagnosis 低：推荐 case
* medical_knowledge 低：推荐 knowledge_unit

5. 修改 /api/students/{student_id}/pathway：
   weak_abilities 返回八维中的最低维度。
   recommended_tasks 使用八维规则生成。

四、第二阶段：建立统一学习证据事件表

当前问题：
learning_evidence_service.py 只是从各模块表里统计完成次数和最新分数，尚未形成统一“多模态学习证据库”。

开发目标：
新增 LearningEvidenceEvent 表，记录每次学习活动如何影响能力画像。

后端新增模型：
LearningEvidenceEvent
字段：

* id
* student_id
* module_type: knowledge / skill / case / guideline / sp
* module_id
* session_id
* event_type
* source_table
* source_id
* score
* competency_updates_json
* evidence_payload_json
* created_at

新增服务：
backend/app/services/competency_update_service.py

函数：

1. update_competency_from_knowledge(db, student_id, quiz_score, source_id)
   更新：

* medical_knowledge

2. update_competency_from_skill(db, student_id, score, detail, source_id)
   更新：

* skill_operation
* clinical_decision

3. update_competency_from_case(db, student_id, score, source_id)
   更新：

* medical_knowledge
* key_information
* differential_diagnosis
* evidence_integration
* clinical_decision
* evidence_based_medicine

4. update_competency_from_guideline(db, student_id, score, detail, source_id)
   更新：

* evidence_based_medicine
* clinical_decision

5. update_competency_from_sp(db, student_id, scoring, source_id)
   更新：

* key_information
* differential_diagnosis
* communication
* humanistic_care

统一更新公式：
new_score = old_score * 0.7 + module_score * 0.3

每次更新都写入 LearningEvidenceEvent：
competency_updates_json 记录更新前、更新后和变化值。
evidence_payload_json 记录原始评分 detail。

五、第三阶段：五大模块提交后全部反哺能力画像

修改以下路由：

1. backend/app/routes/knowledge.py
   在 submit_quiz 成功后调用：
   update_competency_from_knowledge()

2. backend/app/routes/skills.py
   在 submit_skill_session 成功后调用：
   update_competency_from_skill()

3. backend/app/routes/sessions.py
   病例提交评分后调用：
   update_competency_from_case()
   如果已有能力更新逻辑，改为统一走 competency_update_service。

4. backend/app/routes/guidelines.py
   在 submit_pico 成功后调用：
   update_competency_from_guideline()
   替代或整合现有 update_evidence_profile。

5. backend/app/routes/sp.py
   在 submit_sp_session 成功后调用：
   update_competency_from_sp()

验收：
任意一个模块完成后，学生 /dashboard 的八维雷达图应发生合理变化。

六、第四阶段：升级学习路径推荐返回结构

当前问题：
RecommendedTask 前端根据 type 推断目标能力和预计提升，后端推荐解释还不够研究化。

修改 backend/app/services/recommendation_service.py：
recommended_tasks 每项返回：

* type
* id
* title
* reason
* priority
* target_abilities: string[]
* source_evidence: string
* expected_lift: string
* difficulty_label: string
* next_step_label: string

示例：
{
type: "guideline",
id: 1,
title: "SLE治疗指南PICO训练",
reason: "循证医学得分58，为当前最低能力维度",
priority: 96,
target_abilities: ["循证医学", "临床决策"],
source_evidence: "最近指南PICO得分低于70，且病例治疗方案缺少推荐等级说明",
expected_lift: "+12%",
difficulty_label: "进阶",
next_step_label: "进入指南PICO训练"
}

修改 frontend/lib/api.ts 中 RecommendedTask 类型。
修改 frontend/components/RecommendedTaskCard.tsx：
优先使用后端返回的 target_abilities、expected_lift、source_evidence、difficulty_label、next_step_label。
如果后端没有，保留前端 fallback。

七、第五阶段：教师端升级为研究数据平台

当前问题：
教师端已接近 demo，但缺少学生详情、研究导出、教师复核和教学干预记录。

新增后端 API：

1. GET /api/teacher/students/{student_id}/learning-profile
   返回：

* student
* competency
* learning_evidence
* evidence_events
* recommended_tasks
* completed_sessions
* latest_sp
* latest_guideline
* growth_trend

2. GET /api/teacher/export/research-data
   返回 CSV 或 JSON：

* 匿名 student_code
* module_type
* score
* competency_before
* competency_after
* created_at
* class_name

3. POST /api/teacher/interventions
   记录教师教学干预：
   字段：

* title
* target_ability
* target_students_json
* intervention_type
* description
* created_at

4. GET /api/teacher/interventions
   返回教学干预记录。

5. POST /api/teacher/reviews
   教师复核 AI 评分：
   字段：

* evidence_event_id
* ai_score
* teacher_score
* comment
* agreement_delta
* created_at

新增模型：

* TeachingIntervention
* TeacherScoreReview

前端新增页面：

* /teacher/students/[studentId]
* /teacher/research-export
* /teacher/interventions
* /teacher/score-review

八、第六阶段：教师 dashboard 继续完善

修改 /teacher/dashboard：

1. class_heatmap 升级为八维。
2. class_competency 雷达图使用 expanded 八维。
3. 增加模块完成分布图：

* 知识测验
* 技能训练
* 病例推理
* 指南PICO
* SP问诊

4. 增加“研究数据入口”按钮：

* 导出研究数据
* 教师评分复核
* 教学干预记录

5. 学生表现表中“查看详情”改为可点击，进入 /teacher/students/[studentId]。

九、第七阶段：学生模块详情页提升为评价型教学页面

逐步优化：

1. /student/knowledge
   增加：

* 掌握度趋势
* 错因分析
* 关联病例推荐
* 完成后进入下一任务按钮

2. /student/skills
   增加：

* OSCE式评分卡
* 完整性、顺序、安全性三维评分条
* 常见错误高亮
* 反哺能力画像提示

3. /student/case
   增加：

* 关键信息提取面板
* 鉴别诊断表
* 支持证据 / 反证
* AI追问轨迹
* 结构化评分卡

4. /student/guidelines
   增加：

* PICO分项评分
* 推荐等级理解评分
* 临床适用性评分
* 风险个体化评分

5. /student/sp
   增加：

* 实时信息提取面板
* 待补充信息
* OSCE评分卡
* 能力画像更新提示

十、第八阶段：研究与结题支持

新增页面：

* /teacher/research-dashboard

展示：

1. 前后测能力变化
2. 各模块完成率
3. 学生能力成长曲线
4. AI评分与教师评分一致性
5. 班级共性短板变化
6. 教学干预前后对比

新增导出：

* research_dataset.csv
* competency_growth.csv
* ai_teacher_agreement.csv
* module_completion.csv

导出数据必须匿名化：

* 不导出学生姓名
* 使用 student_code
* 保留 class_name 或 group_name

十一、质量与安全要求

1. 所有 AI 评分结果必须标注“AI形成性评价，仅供教学参考，最终评价由教师确认”。
2. 教师端增加复核入口，避免 AI 评分直接替代教师。
3. 研究数据导出默认匿名化。
4. 不记录真实敏感病人信息；病例库数据必须为教学病例或匿名化病例。
5. 前后端错误提示清楚，不因某模块暂无数据导致页面崩溃。

十二、验收标准

1. /demo 六个视图保持可用。
2. /student/dashboard 显示真实八维能力画像、五模块学习证据、AI短板诊断和推荐任务。
3. /student/pathway 推荐任务由后端返回 target_abilities、source_evidence、expected_lift。
4. 任一模块完成后，能力画像有对应维度更新，并写入 LearningEvidenceEvent。
5. /teacher/dashboard 显示八维班级热力图、五模块训练总数、教学干预建议和研究入口。
6. 教师可查看单个学生学习画像。
7. 教师可导出匿名化研究数据。
8. 教师可复核 AI 评分。
9. npm run typecheck 通过。
10. npm run build 通过。
11. 后端启动正常，核心 API smoke test 通过。

十三、完成后请输出

1. 修改文件清单。
2. 新增模型清单。
3. 新增 API 清单。
4. 五模块如何反哺能力画像。
5. 推荐算法升级说明。
6. 教师端研究支持功能说明。
7. 仍待下一阶段完善的问题。


