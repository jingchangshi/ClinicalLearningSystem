目标：将当前系统品牌名从“诊途”统一改为“ClinPath”，并新增一个“展示模式 /demo”，用于课题申报截图展示。展示模式不影响现有学生端、教师端和后端功能，只作为高质量静态/半动态展示页，集中呈现系统的教育学价值、AI个性化学习、自适应路径、数字画像、SP考核和教师驾驶舱。

仓库：jingchangshi/ClinicalLearningSystem
基于当前最新版本实现。

总体要求：
1. 全站中文名称统一改为“ClinPath”。
2. 页面副标题可使用：“AI辅助临床教学与自适应学习路径系统”。
3. 保留原系统所有功能和 API。
4. 新增 /demo 展示模式，用于申请书截图。
5. /demo 中提供多个可选择展示方案，每个方案都要有独立截图友好的页面或标签。
6. 风格要偏医学教育研究平台，不要互联网娱乐化。
7. 重点突出：
   - AI Learning Profile
   - Learner Digital Twin
   - Competency Growth Map
   - AI Adaptive Learning Recommendation
   - SP OSCE Assessment
   - Teacher Analytics Dashboard
8. 所有页面需要适配 1440px 宽度截图。
9. 使用现有 Next.js、React、Tailwind、lucide-react、Recharts。
10. 不新增复杂依赖。
11. 最终确保 npm run build、npm run typecheck 通过。

第一部分：品牌名统一替换
- 将 README、首页、导航、页面标题、FastAPI title、文案中的“诊途”替换为“ClinPath”。
- 中文描述统一为：
  ClinPath：AI辅助临床教学与自适应学习路径系统
- 若原来写“临床推理与自适应学习系统”，可改为：
  AI辅助临床教学与自适应学习路径系统
- 不要改数据库表名。
- 不要破坏 API 路径。

第二部分：新增展示模式入口
新增页面：
- frontend/app/demo/page.tsx
- 可拆分组件到 frontend/components/demo/

在首页 / 增加一个入口卡片：
标题：展示模式
副标题：用于课题申报、教学汇报和系统截图展示
按钮：进入 ClinPath 展示模式
链接：/demo

第三部分：/demo 总览页结构
/demo 页面顶部：
- ClinPath
- AI辅助临床教学与自适应学习路径系统
- 标签：Prototype v2 / Medical Education AI / Adaptive Learning / OSCE-ready

顶部右侧放一个“截图模式”提示：
“建议浏览器宽度 1440px，适合申请书截图。”

/demo 下方提供 5 个展示方案卡片或 tab：
1. Academic Medicine Dashboard
2. Learner Digital Twin
3. Bloom 2-Sigma Adaptive Pathway
4. Competency Growth Map
5. Grant Screenshot Storyboard

用户点击不同方案时，在同一页面下方切换展示内容即可。也可以使用 query 参数：
/demo?view=academic
/demo?view=digital-twin
/demo?view=bloom
/demo?view=growth-map
/demo?view=storyboard

第四部分：方案一 Academic Medicine Dashboard
做成适合截图的医学教育研究平台首页。

布局：
- 顶部：ClinPath 学生学习驾驶舱
- 左上：学生信息卡
  - 学生：李明
  - 年级：临床医学本科三年级
  - 当前阶段：基础疾病识别 → 复杂症状鉴别
- 顶部四个指标卡：
  1. Clinical Reasoning Index：78，+12%
  2. Evidence-Based Decision：72，+8%
  3. History Taking：81，+15%
  4. Learning Maturity：74，+10%
- 中部左侧：能力雷达图，使用 Recharts
  维度：
  医学知识 72
  关键信息提取 68
  鉴别诊断 61
  证据整合 70
  临床决策 66
  循证医学 58
- 中部右侧：AI Learning Profile
  显示：
  知识掌握 Level B
  临床推理 Level C+
  循证决策 Level C
  沟通问诊 Level B+
- 底部：AI Adaptive Learning Recommendation
  三张推荐任务卡：
  1. SLE与感染鉴别病例
     原因：鉴别诊断能力低于同年级均值
     预计提升：+12%
  2. EULAR风湿免疫指南PICO训练
     原因：循证医学能力为当前最低维度
     预计提升：+10%
  3. 标准化病人问诊训练
     原因：需加强病史采集与共情表达
     预计提升：+9%

视觉：
- 白底
- 蓝绿色医学色
- 轻微阴影
- 卡片化
- 数据标签醒目
- 适合截图，不要太拥挤。

第五部分：方案二 Learner Digital Twin
目标：突出“学习者数字画像”。

布局：
标题：Learner Digital Twin 学习者数字画像

左侧：
- 学生头像占位圆形
- 学生：王佳
- 学习阶段：复杂症状鉴别
- 系统判定：
  - 知识掌握：Level B
  - 临床推理：Level C
  - 循证能力：Level C
  - 沟通能力：Level B+

中间：
- 大雷达图或六边形能力图
- 显示六大能力维度

右侧：
- AI Diagnostic Summary
  文案：
  系统识别该学生在“鉴别诊断”和“循证医学”维度存在短板，建议优先完成复杂症状群病例、指南PICO训练和SP问诊任务。
- Next Best Action
  1. 完成“成人Still病与感染鉴别”病例
  2. 完成“免疫抑制治疗安全监测”知识单元
  3. 完成“发热皮疹患者SP问诊”

底部：
- Learning Evidence Timeline
  用横向时间线展示：
  知识测验 → 病例推理 → 指南PICO → SP考核 → 能力画像更新

第六部分：方案三 Bloom 2-Sigma Adaptive Pathway
目标：突出“AI一对一导师”和“自适应学习路径”。

标题：
Bloom 2-Sigma Inspired AI Tutor
副标题：
从统一教学走向一对一个性化临床能力训练

布局：
左侧一列：传统教学模式
- 同样课程
- 同样病例
- 同样考试
- 反馈滞后

中间箭头：
AI Adaptive Engine

右侧两条学生路径：
学生A：基础薄弱
路径：
基础知识单元 → SLE基础病例 → 结构化问诊SP → 标准病例 → 阶段反馈

学生B：基础较好
路径：
复杂病例 → 鉴别诊断训练 → 指南PICO → 高阶SP考核 → 科研文献训练

底部：
- One-to-One Learning Loop
  Assessment → Diagnosis of Learning Gap → Adaptive Task → AI Feedback → Competency Update

视觉：
- 用流程图卡片
- 箭头清晰
- 适合放在申请书“技术路线图”或“研究思路图”。

第七部分：方案四 Competency Growth Map
目标：突出胜任力成长路径。

标题：
Competency Growth Map 医学生胜任力成长地图

布局：
横向成长地图或阶梯式路径：
Level 1 基础知识识别
Level 2 标准病例推理
Level 3 复杂症状鉴别
Level 4 循证决策训练
Level 5 SP-OSCE 综合考核

每个 level 用卡片展示：
- 当前状态：已完成 / 进行中 / 待解锁
- 对应能力：
  医学知识、病史采集、体格检查、鉴别诊断、循证决策、医患沟通
- 对应任务：
  知识单元、病例、技能、指南、SP

右侧：
- Competency Matrix
  表格展示能力维度与训练模块的映射：
  基础知识学习
  临床技能训练
  临床思维训练
  循证指南学习
  SP考核

第八部分：方案五 Grant Screenshot Storyboard
目标：专门用于申请书截图，像产品宣传板一样展示 6 张“系统截图缩略图”。

标题：
ClinPath Grant Screenshot Storyboard
副标题：
用于课题申报书的系统原型展示图组

六个大卡片：
1. 系统总架构
   知识 → 技能 → 病例 → 指南 → SP → 能力画像 → AI推荐
2. 学生首页
   展示能力画像与推荐任务
3. 临床推理训练
   展示病例分步推理与AI追问
4. 循证指南学习
   展示PICO、推荐等级、临床适用性
5. SP标准化病人考核
   展示问诊对话和OSCE评分
6. 教师驾驶舱
   展示班级短板、教学重点、训练记录

每个卡片要像缩略截图：
- 有小标题
- 有简化 UI 框
- 有数据
- 有图表或流程
- 不需要真实路由截图，只需要高质量展示化界面。

第九部分：新增组件建议
建议创建：
frontend/components/demo/DemoShell.tsx
frontend/components/demo/MetricCard.tsx
frontend/components/demo/DemoRadar.tsx
frontend/components/demo/AcademicDashboardDemo.tsx
frontend/components/demo/LearnerDigitalTwinDemo.tsx
frontend/components/demo/BloomPathwayDemo.tsx
frontend/components/demo/CompetencyGrowthMapDemo.tsx
frontend/components/demo/GrantStoryboardDemo.tsx

要求：
- 组件数据先写死，专用于截图。
- 不要依赖后端 API，避免截图时数据加载失败。
- 使用 Tailwind 实现医学教育风格。
- 使用 lucide-react 图标增强质感。
- 使用 Recharts 绘制雷达图或折线/柱状图。
- 所有展示方案都必须在 /demo 可切换。

第十部分：UI细节要求
统一色系：
- 主色：teal / cyan / blue
- 背景：slate-50
- 卡片：white
- 强调：emerald / clinic teal
- 风险提示：rose / amber 少量使用

统一文案：
- 不要写“测试页面”
- 不要写“假数据”
- 使用“展示模式”“原型演示”“课题申报截图模式”
- 页面中可以出现：
  - AI Learning Profile
  - Learner Digital Twin
  - Adaptive Pathway
  - Competency Growth Map
  - SP-OSCE
  - Teacher Analytics

第十一部分：验收标准
完成后请确认：
1. 全站可搜索到的“诊途”已替换为“ClinPath”，除非 README 中作为历史说明出现。
2. /demo 页面可访问。
3. /demo 的五个方案可切换展示。
4. / 页面有展示模式入口。
5. 不破坏现有学生端、教师端、病例训练、知识、技能、指南、SP、病例生成器。
6. npm run typecheck 通过。
7. npm run build 通过。
8. 如有 lint 错误一并修复。

最后输出：
- 修改了哪些文件
- 新增了哪些 demo 组件
- 如何启动
- 推荐截图路径：
  /demo?view=academic
  /demo?view=digital-twin
  /demo?view=bloom
  /demo?view=growth-map
  /demo?view=storyboard
