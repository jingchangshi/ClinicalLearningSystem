目标：读取并理解当前仓库 jingchangshi/ClinicalLearningSystem 在 commit 95d6a9156fe57705cea558b76b5b33dda7d5e0eb 的架构，将主业务系统的学生端和教师端逐步升级到 /demo 展示模式所体现的“多模块、多模态、形成性评价、自适应路径、教师精准干预”的表达效果。注意：/demo 是申请书图版系统，保留不破坏；本次目标是让真实学生端和教师端也尽量接近 demo 的视觉逻辑和教育研究表达。

一、当前已知架构

1. /demo 页面已经存在，入口文件为：
   frontend/app/demo/page.tsx

2. /demo 使用：
   frontend/components/demo/DemoShell.tsx

3. /demo 支持六个 view：
   - overview
   - competency
   - pathway
   - multimodal
   - osce
   - teacher

4. 对应组件：
   - SystemOverviewDemo
   - CompetencyAssessmentDemo
   - AdaptivePathwayDemo
   - MultimodalMatrixDemo
   - SPOSCEDemo
   - TeacherDashboardDemo

5. 主业务学生端已有：
   - /student/dashboard
   - /student/pathway
   - /student/knowledge
   - /student/skills
   - /student/guidelines
   - /student/sp
   - /student/case
   - /student/result

6. 主业务教师端已有：
   - /teacher/dashboard
   - /teacher/cases
   - /teacher/case-generator

7. 后端已有模块：
   - knowledge
   - skills
   - guidelines
   - sp
   - cases
   - sessions
   - students
   - teacher
   - case_generation

二、总体要求

1. 不破坏 /demo。
2. 不破坏现有 API。
3. 不删除现有功能。
4. 优先复用 demo 组件的设计语言，但主业务页面必须使用真实 API 数据。
5. 主业务页面要从“功能页”升级为“临床能力成长与教学闭环页面”。
6. 使用现有 Next.js、React、Tailwind、Recharts、lucide-react。
7. 不新增大型依赖。
8. 完成后 npm run typecheck 和 npm run build 必须通过。
9. 后端 Python 代码应保持 FastAPI + SQLAlchemy 当前风格。
10. 如果需要新增字段，优先以兼容方式处理，避免旧数据库启动失败。

三、第一阶段：学生 dashboard 视觉与信息架构升级

修改：
frontend/app/student/dashboard/StudentDashboardClient.tsx

目标：
将学生首页从“临床推理训练首页”升级为：
“ClinPath 学生临床能力成长中心”

新增或调整内容：

1. 顶部标题：
   ClinPath 学生临床能力成长中心
   副标题：基于多模块训练数据形成能力画像与个性化学习路径。

2. 顶部四个指标卡：
   - 综合胜任力指数：从 dashboard.competency 中六维平均值计算
   - 已完成训练：先用 completed_cases + 可用的其他模块统计，如果无其他模块统计先显示病例数并标注“病例训练”
   - 当前主要短板：从 competency 最低维度计算
   - AI推荐下一任务：显示 recent_advice 或 pathway 第一条任务

3. 增加“五模块训练入口矩阵”：
   - 基础知识学习
   - 临床技能训练
   - 临床思维训练
   - 循证指南学习
   - SP模拟考核
   每张卡显示：
   - 模块名称
   - 训练目标
   - 对应能力维度
   - 进入按钮

4. 增加“AI Learning Gap Diagnosis”卡：
   从 competency 中取最低2个维度。
   显示：
   - 当前短板
   - 推荐训练模块
   - 推荐理由

5. 当前能力画像区域改为更接近 demo 的布局：
   - 左侧：学生信息与综合胜任力指数
   - 中间：雷达图
   - 右侧：AI短板诊断和下一步建议

6. 推荐病例区域改为“AI Adaptive Learning Recommendation”
   每个推荐病例显示：
   - 病例名称
   - 推荐原因
   - 目标能力
   - 开始训练按钮

四、第二阶段：学生 pathway 页面升级为真实版 AdaptivePathwayDemo

修改：
frontend/app/student/pathway/page.tsx

目标：
让真实 pathway 页面更像 /demo?view=pathway，但使用真实数据。

新增布局：

1. 页面标题：
   AI个性化学习路径
   副标题：基于能力画像、训练表现与模块完成情况生成下一阶段学习任务。

2. 顶部区域：
   左侧：当前学生能力画像
   中间：当前阶段与下一阶段目标
   右侧：AI Learning Gap Diagnosis

3. 中间增加 Adaptive Recommendation Engine 流程：
   - 采集学习数据
   - 计算能力画像
   - 识别最低能力维度
   - 匹配训练模块
   - 生成下一阶段任务

4. recommended_tasks 卡片升级：
   每张卡显示：
   - 任务类型
   - 任务名称
   - 推荐原因
   - 目标能力
   - 优先级
   - 预计提升
   - 进入任务按钮

5. 预计提升规则：
   priority >= 95: +12%
   priority >= 90: +10%
   priority >= 85: +8%
   else: +5%

6. 目标能力规则：
   - knowledge_unit → 医学知识
   - clinical_skill → 技能操作 / 临床决策
   - case → 临床推理 / 鉴别诊断
   - guideline → 循证决策
   - sp_case → 信息采集 / 医患沟通

7. 保留 pathway_stages 和 completed_cases，但视觉弱化，放到页面下部。

五、第三阶段：教师 dashboard 升级为真实版 TeacherDashboardDemo

修改：
frontend/app/teacher/dashboard/page.tsx
backend/app/routes/teacher.py
frontend/lib/api.ts

目标：
让教师端从“班级病例表现”升级为：
“教师精准教学驾驶舱”

前端新增内容：

1. 标题：
   教师精准教学驾驶舱
   副标题：基于班级多模块训练数据进行教学诊断与干预建议。

2. 顶部四个指标卡：
   - 参与学生
   - 完成训练总次数
   - 平均能力提升
   - 当前共性短板

3. 将“完成病例数”改为“完成训练总次数”
   如果后端暂时无法统计五模块，先显示 case + guideline + sp + skill + knowledge 的总和。

4. 增加班级能力热力图：
   行：学生
   列：医学知识、关键信息、鉴别诊断、证据整合、临床决策、循证医学
   单元格按分数上色。
   可复用 demo 的 HeatmapGrid 组件。

5. 增加“AI Teaching Intervention Suggestions”区块：
   根据 weak_dimensions 生成教学建议。
   如果循证医学低：建议增加“指南推荐等级与PICO构建”小课。
   如果鉴别诊断低：建议安排“SLE活动与感染鉴别”病例讨论。
   如果临床决策低：建议增加“免疫抑制治疗安全监测”专题。
   如果医学知识低：建议推送基础知识单元。
   如果关键信息低：建议加强SP问诊训练。

6. 增加“教学闭环”流程：
   学生训练数据 → 班级短板识别 → 教师教学调整 → 再训练 → 效果评价

后端修改：
在 /api/teacher/dashboard 返回中增加字段：

training_total_count
module_counts: {
  knowledge: number,
  skill: number,
  case: number,
  guideline: number,
  sp: number
}
class_heatmap: [
  {
    student_id,
    student_name,
    medical_knowledge,
    key_information,
    differential_diagnosis,
    evidence_integration,
    clinical_decision,
    evidence_based_medicine
  }
]
current_common_weakness
teaching_interventions

如果某些模块表尚未导入 teacher.py，需要从 models 引入：
KnowledgeProgress, SkillSession, GuidelineLearningSession, SPSession

统计规则：
- knowledge: KnowledgeProgress.status == "completed"
- skill: SkillSession.status == "completed"
- case: CaseSession.status == "completed"
- guideline: count(GuidelineLearningSession)
- sp: SPSession.status == "completed"

六、第四阶段：新增学习证据服务

新增：
backend/app/services/learning_evidence_service.py

功能：
1. build_student_evidence_summary(db, student_id)
返回：
{
  student_id,
  evidence_summary: [
    {module: "knowledge", label: "知识测验", completed: n, latest_score: score},
    {module: "skill", label: "技能步骤", completed: n, latest_score: score},
    {module: "case", label: "病例推理", completed: n, latest_score: score},
    {module: "guideline", label: "指南PICO", completed: n, latest_score: score},
    {module: "sp", label: "SP问诊", completed: n, latest_score: score}
  ]
}

2. build_class_training_summary(db)
返回全班五模块训练次数。

3. build_class_heatmap(db)
返回每个学生的能力画像分数。

然后在：
backend/app/routes/students.py
backend/app/routes/teacher.py
中调用这些服务，避免在路由中写太多统计逻辑。

七、第五阶段：能力画像模型升级，先做兼容设计

当前 CompetencyProfile 主要是六维：
medical_knowledge
key_information
differential_diagnosis
evidence_integration
clinical_decision
evidence_based_medicine

未来希望扩展到：
skill_operation
communication
humanistic_care

本阶段不要强制改数据库，以免破坏旧库。
先在 serializer 中提供兼容字段：
- skill_operation：如果数据库没有字段，则用 clinical_decision 与 key_information 的均值估算
- communication：如果数据库没有字段，则从最近SP session communication_score 估算，否则默认 75
- humanistic_care：如果数据库没有字段，则从最近SP session humanistic_care_score 估算，否则默认 75

前端 radar 支持显示八维：
医学知识
技能操作
关键信息提取
鉴别诊断
证据整合
循证决策
医患沟通
人文关怀

等确认稳定后，再做正式数据库迁移。

八、第六阶段：统一组件

新增或复用：
frontend/components/
- LearningEvidenceCards.tsx
- LearningGapDiagnosisCard.tsx
- AdaptiveRecommendationEngine.tsx
- RecommendedTaskCard.tsx
- ClassHeatmap.tsx
- TeachingInterventionPanel.tsx
- TrainingLoopFlow.tsx

要求：
1. demo 页面可继续使用自己的静态组件。
2. 主业务页面使用这些真实数据组件。
3. 组件样式接近 demo：白底、蓝绿医学色、圆角卡片、清晰图表。
4. 不要引入过度动画。

九、验收标准

1. /demo 所有 view 保持可用：
   /demo?view=overview
   /demo?view=competency
   /demo?view=pathway
   /demo?view=multimodal
   /demo?view=osce
   /demo?view=teacher

2. /student/dashboard 显著接近 demo 的“能力评估 + AI短板诊断 + 多模块训练”表达。

3. /student/pathway 显著接近 demo 的“个性化路径 + 推荐引擎 + 任务卡”表达。

4. /teacher/dashboard 显著接近 demo 的“班级热力图 + 教学干预建议 + 教学闭环”表达。

5. 真实业务页面必须使用后端 API，不使用硬编码 demo 数据。

6. 不破坏：
   - 知识学习
   - 临床技能
   - 病例训练
   - 循证指南
   - SP考核
   - AI生成病例
   - 病例管理

7. 后端启动正常。
8. 前端 npm run typecheck 通过。
9. 前端 npm run build 通过。

十、完成后输出

请输出：
1. 修改了哪些文件。
2. 新增了哪些组件和服务。
3. 学生端对齐 demo 的点。
4. 教师端对齐 demo 的点。
5. 当前仍未完成但建议下一阶段做的事项。

