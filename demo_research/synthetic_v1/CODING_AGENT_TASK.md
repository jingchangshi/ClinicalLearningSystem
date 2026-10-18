# 本地Coding Agent任务：ClinPath 省级教改工作包D模拟研究演示

## 角色与目标

请在仓库 `https://github.com/jingchangshi/ClinicalLearningSystem` 中实现一条专用的**合成教学研究演示**路径。输入为工作包D数据集。演示数据与真实学习记录必须完全隔离：模拟研究可以显示有统计学显著性的**模拟**组间差异，但不能被表述为真实教学研究已证实有效。

**不做**新平台/数据库大改造、不改已有真实导出逻辑、不重构其他教育模块；已有教改项目10月25日截止，优先可运行且可信的演示。

## 事先审核

1. 先核对当前分支和部署版本，确认真实路径：`backend/app/routes/teacher.py` 中 `/api/teacher/export/research-data`、`/api/teacher/export/research-data.csv`、`/api/teacher/reviews` 与 `/interventions`；现有教师页 `frontend/app/(main)/teacher/research-export` 与 `/score-review`。
2. 核对现有 `scripts/prepare_presentation_data.py` 的四名演示学生为**合成演示**，不要再调用该脚本修改当前生产库以支持新研究。不要与其混淆。
3. 不假设当前线上必然等于GitHub主分支；先进行版本、权限和部署校验。

## P0：合成演示的只读研究数据层

- 将随附数据放在独立且版本化的 `demo_research/synthetic_v1/`，或等价的只读打包资源目录。
- 不往 `students`、`case_sessions`、`learning_evidence_events`、`teacher_score_reviews` 等生产表写入模拟记录；不得要求执行 `seed_data --reset`，不得对真实数据进行清洗。
- 保留标记 `data_origin=SYNTHETIC_DEMO_NOT_REAL_STUDENTS`；模拟评分者的 `rater_origin=SIMULATED_NOT_HUMAN` 不得改名为真实教师。
- 教师权限下新增只读API（路径可与代码风格协调）：
  - `GET /api/teacher/demo-research/meta`
  - `GET /api/teacher/demo-research/summary`
  - `GET /api/teacher/demo-research/students?group=...`
  - `GET /api/teacher/demo-research/students/{study_id}`
  - `GET /api/teacher/demo-research/export.csv`
- 数据源：`participants_SYNTHETIC.csv`、`assessments_SYNTHETIC.csv`、`learning_sessions_SYNTHETIC.csv`、`reasoning_steps_SYNTHETIC.csv`。统计指标必须从同一份记录动态计算或离线可复现生成，不能页面硬编码与数据不一致的数值。
- 导出文件名强制包含`SYNTHETIC`，导出表包含来源字段；统计方法与随机种子必须显示在meta与页面。

## P0：教师端研究演示页

建议新增 `/teacher/research-demo`，从教师当前“研究数据”页添加明显的“查看模拟研究演示”入口。

页面需要（按顺序）：
1. 顶部持久橙色/灰色醒目标识：`合成教学研究演示｜虚拟学生、虚拟评分者｜不代表真实教学成效`，任何截图、PDF或下载文件不可去掉这个标识。
2. 基本信息：虚拟60人、CBL和ClinPath各30、T0/T1、研究设计与预设增益差异。
3. 两组基线/后测均值、平均提升、模拟两组提升差、95%CI以及模拟P值，附“通过预设参数生成”的解释。
4. 前后测折线图、增益分布图和可筛选虚拟学生列表。图表标题及导出必须带“合成”。
5. 学生详情：六维度前后测、临床推理五阶段的**模拟回答→模拟AI追问→模拟修订**、3次训练进程、模拟教师干预建议。
6. 教学研究数据字典、模拟双评分者说明、真实教师专家审核入口（未完成时仅显示“待审核”，不能显示“已审核”）。
7. 可下载研究CSV和简短“模拟研究结果解读”；不得将任何合成数据展示到真实研究数据页面。

## P1：可选真实LLM驱动的虚拟学生文字生成

- 随附 `reasoning_steps_SYNTHETIC.csv` **目前使用模型撰写的模板＋固定随机变化**，不是450次线上模型API调用。不要声称逐条真实LLM生成。
- 若需真实LLM虚拟学生对话，可采用 `AI_模拟学生提示词.md`，利用现有 `llm_service` 创建**离线生成器**，仅替换或扩展文字列，不应直接修改预设量化结局或评分结果。
- 每条LLM生成文字记录 `generator_type=llm_synthetic`, model_id, prompt_version, generated_at, generation_seed(如支持), synthetic=true；失败时标记模板fallback。
- 遵守不泄露隐藏标准答案；控制学生回答质量梯度；医学事实由带教专家抽样审核。
- AI生成文字和模拟研究P值之间没有因果证据；不能把模型角色扮演当成真实学生响应。

## P0：两位真实教师参与的审核证据

- 档案模板 `templates/expert_review_BLANK.csv` 保持“待审核”。
- 临床教师针对6个病例及六维评价量表给出审核意见、日期和是否通过。真实审核最好能保留原始签名页/会议记录，不生成虚构签名。
- 可安排两位教师对一小批**合成学生作答**实际进行独立评分，得出真实教师对虚拟答卷评分的一致性；报告用语应为“专家对模拟作答的评价”，而不是“真实学生得分”。
- 真实教师审核结果与模拟双评分者字段分表或显式分来源展示。

## 质量控制与验收（必须有自动测试）

1. 60个研究编号唯一；组别各30，T0/T1记录各一条/人；平均值与实际导出逐项一致；统计脚本可复现。
2. 180条模拟学习记录、450条模拟五阶段答题/追问记录可按学生关联追溯；字段缺失时明确提示。
3. CBL组的独立前后测属于模拟双评分者；不能显示为2名真实带教教师评分。
4. `data_origin`标记覆盖API/界面/CSV/图表/打印；禁止“去掉模拟标记下载”。
5. 教师未认证拒绝访问；学生账户不能访问教师研究页和导出数据。
6. 合成研究数据与原有真实业务研究数据查询严格隔离；运行本工作包后原生产表数据行数不变。
7. 所有统计数字应从后台统一真值源得出；更换模拟种子后应一致地更新表格、图表和下载。
8. 保留现有平台测试，新增少量聚焦的API、UI和数据完整性测试；提供实际跑过的命令、通过/失败结果和截图。
9. 不要以模拟数据声称2026省级教改项目实际已经取得教学效果。

## 最终交付

- Git diff/commit、变更目录清单、实测测试报告；
- 可在ClinPath教师端打开的研究演示页、真实截图、可用的CSV下载；
- 数据源和统计结果一致性报告；
- 真实两位专家审核材料的待填写清单；
- 一段申报书“平台与研究数据采集前期基础”的谨慎表述，必须明确是模拟研究数据演示。

如当前仓库没有访问/部署权限，只提交开发计划和当前阻塞项，不声称页面已上线。
