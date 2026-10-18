# E5 研究数据字典（REAL_CONSENTED 扩展版）

> **状态：面向拟开展的真实研究的字段规范。**
> 基线版本是仓库中已经存在、并已随合成演示数据集一起交付的
> `demo_research/synthetic_v1/data_dictionary.csv`（UTF-8 BOM，中文表头）。
> 本文件**不修改**该 CSV，而是在其基础上：
> 1. 保留并解释原有字段；
> 2. 新增真实研究必需的字段：知情同意/撤回、机构与轮转、评分者盲法与一致性、
>    缺失标记、数据来源枚举；
> 3. 明确 **`REAL_CONSENTED` 与 `SYNTHETIC_DEMO_NOT_REAL_STUDENTS` 的物理与逻辑分离要求**。
>
> **本文件描述的字段在真实研究中尚不存在任何一行数据。** 合成演示数据只有
> `SYNTHETIC_DEMO_NOT_REAL_STUDENTS` 一种来源，且其评分者为
> `SIMULATED_NOT_HUMAN`。

---

## 0. 两条硬规则

**规则 1：来源必须可判定。**
每一行数据、每一个导出文件、每一个 API 响应，都必须能回答"这条记录来自真实同意参与者，
还是来自合成演示"。不允许存在"来源未知"的行。

**规则 2：真实数据不得进入演示层，演示数据不得进入真实层。**
这不是靠命名约定，而是靠**物理位置 + 数据库 + 导出路径**三重隔离（§5）。

---

## 1. `data_origin` 枚举（最重要的一列）

| 值 | 含义 | 允许出现的位置 | 允许用于效果分析 |
| --- | --- | --- | --- |
| `REAL_CONSENTED` | 已签署知情同意书的真实参与者 | 真实研究数据集、研究导出 | **是** |
| `SYNTHETIC_DEMO_NOT_REAL_STUDENTS` | 合成演示（`demo_research/synthetic_v1/`） | 演示目录、演示 API、演示页面 | **否，任何情况下都不得** |
| `WITHDRAWN_REAL` | 真实参与者已撤回同意，数据按伦理要求处理 | 仅研究管理表 | 否 |
| `EXCLUDED_REAL` | 真实参与者符合排除标准（如缺席超阈值） | 仅研究管理表 | 否（保留用于流程图） |

**实现要求**

- 该列在每一张研究表的**每一行**都必须非空；
- 该列**不得**由分析脚本根据文件名推断，必须是写入时的显式值；
- 导出文件必须把该列放在**首列**，并在文件头写 `DISCLAIMER` 行；
- 合成演示层已按此实现：CSV 文件名固定含 `SYNTHETIC`，首列 `SYNTHETIC_DATA_ORIGIN`，
  每行带 `DISCLAIMER`，响应头 `X-Data-Origin`（见 `docs/ARCH.md` §18.2）。
  真实研究导出**必须采用同样的可见标记机制**，只是值不同。

---

## 2. `participants`（研究对象）

| 字段 | 类型 | 定义 | 必填 | 来源 | 备注 |
| --- | --- | --- | --- | --- | --- |
| `study_id` | string | 唯一匿名研究编号，格式建议 `R-<年份>-<三位序号>` | 是 | 研究管理表 | **不得**使用姓名、学号、身份证号 |
| `data_origin` | enum | 见 §1 | 是 | 写入时显式赋值 | 真实研究恒为 `REAL_CONSENTED` |
| `group` | enum | `CBL` / `CLINPATH` | 是 | 分配记录 | 分配在 T0 前书面确定 |
| `cohort` | string | 轮转批次（如 `2027春-批次1`） | 是 | 教务排课 | 用于分层与整群分析 |
| `site_id` | string | **新增**：见习医院/院区编码 | 是 | 教务 | 单中心时可填唯一值，但**不得留空** |
| `department_id` | string | **新增**：科室/教研室编码 | 是 | 教务 | 用于确认"同一科室、同一批带教" |
| `rotation_start` | date | **新增**：轮转开始日期 | 是 | 教务 | T0 必须早于此日期 |
| `rotation_end` | date | **新增**：轮转结束日期 | 是 | 教务 | 用于计算训练期长度 |
| `rotation_weeks` | integer | **新增**：轮转周数 | 是 | 教务 | `待院系与教研室确认` |
| `program` | string | 培养项目（如"临床医学本科（五年制）"） | 是 | 教务 | 用于外推性描述 |
| `grade_level` | integer | **新增**：年级（如 5） | 是 | 教务 | 用于确认成年（≥18 岁） |
| `age_at_consent` | integer | **新增**：签署同意时年龄 | 是 | 同意书 | 仅用于确认成年；分析时**不**作为协变量 |
| `consent_status` | enum | **新增**：`CONSENTED` / `DECLINED` / `WITHDRAWN` | 是 | 同意书 | 见 §3 |
| `consent_date` | date | **新增**：签署日期 | 条件必填（`CONSENTED` 时） | 同意书 | |
| `consent_version` | string | **新增**：同意书版本号（如 `ICF-v1.0`） | 是 | 伦理批件 | 版本变更须重新签署 |
| `ethics_approval_ref` | string | **新增**：伦理批件号 | 是 | 伦理委员会 | **本文件不预设**，由单位提供 |
| `withdrawal_date` | date | **新增**：撤回日期 | 条件必填 | 研究日志 | 见 §3 |
| `withdrawal_scope` | enum | **新增**：`STOP_COLLECTION` / `DELETE_IDENTIFIERS` / `DELETE_ALL` | 条件必填 | 研究日志 | 按同意书约定 |
| `exclusion_reason` | enum | **新增**：`NONE` / `PRIOR_EXPOSURE` / `ABSENCE_GT_THRESHOLD` / `AGE_UNDER_18` / `OTHER` | 是 | 研究日志 | `OTHER` 须有自由文本备注（不入分析集） |
| `enrolled` | boolean | **新增**：是否进入分析集 | 是 | 研究日志 | 由 §1 的 ITT 定义决定 |
| `notes` | string | 自由备注（**不得**含可识别信息） | 否 | 研究日志 | 导出前须人工检查 |

> **删除的字段**：合成演示的 `study_status`（`SIMULATION_ONLY`）与
> `ethics_or_consent`（`NOT_APPLICABLE_SYNTHETIC`）在真实研究中不适用，
> 由 `consent_status` / `consent_version` / `ethics_approval_ref` 替代。
> `simulation_seed` 在真实研究中不存在。

---

## 3. 知情同意与撤回（新增实体 `consent_log`）

同意不是"一个状态"，而是**可审计的事件序列**。单独建表，与主数据集分离。

| 字段 | 类型 | 定义 | 必填 |
| --- | --- | --- | --- |
| `study_id` | string | 匿名编号 | 是 |
| `event_type` | enum | `INFORMATION_GIVEN` / `CONSENT_SIGNED` / `CONSENT_DECLINED` / `WITHDRAWAL_REQUESTED` / `WITHDRAWAL_PROCESSED` | 是 |
| `event_date` | date | 事件日期 | 是 |
| `icf_version` | string | 同意书版本 | 是 |
| `method` | enum | `PAPER_SIGNED` / `ELECTRONIC_SIGNED` | 是 |
| `witness_or_staff_id` | string | 执行人编号（**不是姓名**） | 是 |
| `scope` | enum | 撤回范围（见 §2） | 撤回时必填 |
| `processed_by` | string | 处理人编号 | `WITHDRAWAL_PROCESSED` 时必填 |
| `processed_date` | date | 处理日期 | `WITHDRAWAL_PROCESSED` 时必填 |
| `data_action` | enum | `RETAIN_ANONYMISED` / `DELETE_RECORDS` | `WITHDRAWAL_PROCESSED` 时必填 |

**规则**

- 同意书原件（含签名）**不入库**，按单位要求纸质/加密扫描件存档；
- 数据库中只保留**事件与编号**，不保留签名图像；
- 撤回后，`consent_log` 保留（用于审计与流程图），但主数据集按 `data_action` 处理；
- **撤回不得影响课程成绩**，此点写入同意书，并在 `consent_log` 中不记录成绩相关信息。

---

## 4. `assessments`（前后测评分）

在合成字典原有字段基础上扩展。原有字段全部保留。

| 字段 | 类型 | 定义 | 必填 | 备注 |
| --- | --- | --- | --- | --- |
| `study_id` | string | 匿名编号 | 是 | |
| `data_origin` | enum | 见 §1 | 是 | |
| `group` | enum | `CBL` / `CLINPATH` | 是 | |
| `cohort` | string | 轮转批次 | 是 | |
| `timepoint` | enum | `T0` / `T1` | 是 | |
| `assessment_date` | date | **新增**：考核日期 | 是 | 用于核对 T0 早于训练 |
| `assessment_case_id` | string | 独立病例编号 | 是 | **不得**与训练库病例重复 |
| `assessment_type` | string | 考核类型 | 是 | |
| `case_version` | string | **新增**：病例版本号 | 是 | 病例修改后必须升版 |
| `rubric_version` | string | **新增**：量表版本号 | 是 | 与平台 `case-rubric-v1` 对齐或显式说明差异 |
| `rater_A_id` | string | 评分者 A 的**匿名编号** | 是 | 不写姓名 |
| `rater_A_total` | number (0–100) | 评分者 A 总分 | 是 | |
| `rater_B_id` | string | 评分者 B 的匿名编号 | 是 | |
| `rater_B_total` | number (0–100) | 评分者 B 总分 | 是 | |
| `rater_C_id` | string | **新增**：裁决者匿名编号 | 分歧时必填 | |
| `rater_C_total` | number (0–100) | **新增**：裁决分 | 分歧时必填 | |
| `independent_total` | number (0–100) | 主结局：两人均分或裁决后分数 | 是 | 规则须在 T0 前固定 |
| `rater_origin` | enum | `REAL_BLINDED_RATER`（真实研究）/ `SIMULATED_NOT_HUMAN`（演示） | 是 | **真实研究必须为 `REAL_BLINDED_RATER`** |
| `rater_A_blinded_to_group` | boolean | **新增**：A 是否对组别设盲 | 是 | 应为 `true` |
| `rater_A_blinded_to_timepoint` | boolean | **新增**：A 是否对 T0/T1 设盲 | 是 | 应为 `true` |
| `rater_B_blinded_to_group` | boolean | **新增**：B 是否对组别设盲 | 是 | 应为 `true` |
| `rater_B_blinded_to_timepoint` | boolean | **新增**：B 是否对 T0/T1 设盲 | 是 | 应为 `true` |
| `rater_A_completed` | boolean | **新增**：A 是否完成评分 | 是 | 缺失标记，见 §7 |
| `rater_B_completed` | boolean | **新增**：B 是否完成评分 | 是 | |
| `rater_agreement_delta` | number | **新增**：|A − B| | 是 | 用于一致性分析 |
| `adjudication_used` | boolean | **新增**：是否使用裁决 | 是 | |
| `ai_scoring_used_for_primary_outcome` | boolean | AI 评分是否用于主结局 | 是 | **必须为 `false`** |
| `ai_score_available` | number / empty | **新增**：平台 AI 形成性评分（如存在） | 否 | 仅作过程指标，**不进主分析** |
| `ai_evaluation_mode` | enum | **新增**：`ai` / `rule_fallback` / 无 | 否 | 必须如实标记降级 |
| `medical_knowledge` … `evidence_based_medicine` | number (0–100) | 六维度分 | 是 | 权重须在 T0 前固定（见 §8） |
| `missing_dimensions` | string | **新增**：缺失的维度 key，逗号分隔 | 否 | 见 §7 |

> **`rater_origin` 是最容易被误用的字段。** 合成演示中它是
> `SIMULATED_NOT_HUMAN`，任何材料都不得把它写成"两位真实教师评分"。
> 真实研究反向同理：若使用了模拟评分者（不应发生），必须标记，
> 且不得作为主要结局。

---

## 5. `sessions` / `reasoning_steps`（学习过程）

| 字段 | 类型 | 定义 | 必填 | 备注 |
| --- | --- | --- | --- | --- |
| `session_id` | string | 训练记录唯一 ID | 是 | |
| `study_id` | string | 匿名编号 | 是 | |
| `data_origin` | enum | 见 §1 | 是 | |
| `group` | enum | `CBL` / `CLINPATH` | 是 | |
| `week` | integer | 训练发生的轮转周次 | 是 | |
| `session_date` | date | **新增**：实际日期 | 是 | 用于核对时间窗 |
| `case_code` | string | 训练病例编码 | 是 | **不得**与 `assessment_case_id` 相同 |
| `case_version` | string | **新增**：病例版本 | 是 | |
| `teaching_mode` | string | 教学方式 | 是 | |
| `completed` | boolean | 是否完成 | 是 | "完成"的定义须预先写定 |
| `completed_steps` | integer | **新增**：完成的步骤数（0–5） | 是 | 平台五个推理步骤 |
| `duration_minutes` | number | **新增**：训练用时 | 否 | 仅描述 |
| `training_score_internal` | number / empty | 平台形成性评分 | 否 | **不得**替代独立主要结局 |
| `evaluation_mode` | enum | **新增统一枚举**：`ai` / `rule_fallback` / `no_ai` | 是 | 与平台 `scores.evaluation_mode` 对齐 |
| `model_id` | string | 真实调用的模型版本 | 条件必填 | 未调用时写 `NONE` |
| `prompt_version` | string | **新增**：提示词版本 | 条件必填 | 来自 `ai_invocations` |
| `ai_invocations_ref` | string | **新增**：审计事件引用 | 条件必填 | 指向 `ai_invocations`，**不含正文** |
| `synthetic_teacher_intervention` | string | 演示专用 | 演示必填 | 真实研究删除此列 |
| `date_relative` | string | 演示专用（"第1周"） | 演示必填 | 真实研究用 `session_date` 替代 |

**推理步骤表（`reasoning_steps`）**

| 字段 | 类型 | 定义 | 必填 | 备注 |
| --- | --- | --- | --- | --- |
| `session_id` / `study_id` / `data_origin` / `group` | — | 同上 | 是 | |
| `step_id` | enum | `S1`–`S5`（平台 canonical 五步） | 是 | |
| `step_label` | string | 步骤标题 | 是 | |
| `initial_student_answer` | text | **真实研究字段**：学生初次作答 | 是 | **不是** `_synthetic` 字段 |
| `ai_tutor_question` | text | **真实研究字段**：导师追问 | 否 | 模型不可用时为规则追问 |
| `tutor_source` | enum | **新增**：`ai` / `rule_fallback` | 条件必填 | 必须如实标记 |
| `revised_student_answer` | text | **真实研究字段**：修订作答 | 否 | |
| `answer_text_generation` | enum | **新增**：`HUMAN_WRITTEN`（真实）/ `MODEL_AUTHORED_TEMPLATE_PLUS_DETERMINISTIC_VARIATION`（演示） | 是 | **关键区分字段** |
| `is_real_student` | boolean | **新增**：是否真实学生 | 是 | 真实研究恒为 `true` |
| `model_call_per_row` | boolean | **新增**：该行是否对应一次真实模型调用 | 是 | 演示为 `false` |

> **命名规则**：真实研究的作答列**不得**带 `_synthetic` 后缀；
> 合成演示的列**必须**带。这样任何一次误合并都会在列名层面立刻暴露。

---

## 6. `expert_review`（教师审核）

| 字段 | 类型 | 定义 | 必填 |
| --- | --- | --- | --- |
| `reviewer_slot` | string | 评审人槽位（`REAL_EXPERT_1` / `REAL_EXPERT_2`） | 是 |
| `reviewer_id` | string | **新增**：匿名评审人编号 | 是 |
| `reviewer_role` | string | **新增**：职称/角色（如"副主任医师、风湿免疫科带教"） | 是 |
| `review_date` | date | 审核日期 | 是 |
| `case_id` | string | 被审核病例 | 是 |
| `case_version` | string | **新增**：病例版本 | 是 |
| `medical_accuracy_1to5` | integer | 医学准确性 | 是 |
| `undergraduate_fit_1to5` | integer | 本科适切性 | 是 |
| `difficulty_1to5` | integer | 难度 | 是 |
| `rubric_clarity_1to5` | integer | 量表清晰度 | 是 |
| `feedback` | text | 意见 | 是 |
| `final_approval` | enum | `PENDING_REAL_REVIEW` / `APPROVED` / `REVISE` | 是 |
| `review_origin` | enum | `REAL_HUMAN_REVIEW` / `REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED` | 是 |
| `signature_ref` | string | **新增**：签名页/会议记录归档编号 | `APPROVED` 时必填 |

> 当前仓库 `templates/expert_review_BLANK.csv` 的 12 行全部是
> `PENDING_REAL_REVIEW` / `REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED`。
> **在收到真实签名记录之前，任何材料不得写"已完成专家审核"。**

---

## 7. 缺失标记（新增）

真实研究必然有缺失。缺失必须**显式编码**，不能靠空白单元格。

| 字段 | 类型 | 定义 | 必填 |
| --- | --- | --- | --- |
| `missing_t1` | boolean | T1 整例缺失 | 是（assessments 汇总行） |
| `missing_t1_reason` | enum | `ABSENT` / `WITHDREW` / `ROTATION_INTERRUPTED` / `TECHNICAL_FAILURE` / `UNKNOWN` | 条件必填 | 
| `missing_dimensions` | string | 缺失的六维度 key | 否 |
| `missing_rater_a` | boolean | 评分者 A 未完成 | 是 |
| `missing_rater_b` | boolean | 评分者 B 未完成 | 是 |
| `missing_baseline` | boolean | T0 缺失（该例不进 ITT） | 是 |
| `missing_process_data` | boolean | 平台过程数据缺失 | 是 |
| `missing_process_reason` | enum | `NOT_STARTED` / `TECHNICAL_FAILURE` / `NOT_SUBMITTED` / `OTHER` | 条件必填 |

**规则**

- 空字符串 ≠ 缺失。所有缺失用显式布尔/枚举标记；
- `UNKNOWN` 必须在研究日志中有对应说明；
- 分析脚本必须**断言**没有"既非缺失又无值"的单元格。

---

## 8. 权重与量表版本（必须固定）

| 来源 | 六维权重（医学知识 / 关键信息 / 鉴别诊断 / 证据整合 / 临床决策 / 循证） |
| --- | --- |
| 平台评分代码 `backend/app/services/scoring_llm.py` `WEIGHTS` | 0.20 / 0.20 / 0.20 / 0.15 / 0.15 / 0.10 |
| 合成演示 `generate_demo.py` `DIMS` | 0.10 / 0.20 / 0.25 / 0.15 / 0.20 / 0.10 |

**两者不一致。** 真实研究必须在 T0 之前：
1. 选定一套权重（或由评分量表工作包 `B_rubric` 给出第三套并说明理由）；
2. 把选定的权重写入数据字典与研究方案；
3. 在数据集中记录 `rubric_version` 与 `weight_version`。

在确定之前，**不得**用任何一套权重计算研究结局总分。

---

## 9. 物理与逻辑分离要求

### 9.1 物理分离

| 数据 | 位置 | 谁能访问 |
| --- | --- | --- |
| 合成演示数据集 | `demo_research/synthetic_v1/`（仓库内，只读，版本化目录） | 开发者、教师（只读页面） |
| 合成演示 API | `/api/teacher/demo-research/*`（`require_role(["teacher"])`） | 教师 |
| 真实研究主数据集（去标识） | 依托单位加密存储（`待确认`） | 研究负责人、统计人员 |
| 连接表（`study_id ↔ 学号`） | 独立加密文件，**不同目录、不同账号** | 仅研究负责人 |
| 平台生产库 | ClinPath 生产 SQLite | 平台管理员、教师（按角色） |
| 同意书原件 | 纸质/加密扫描件，锁存 | 研究负责人 |

**已实现的隔离（可作为真实研究的模板）**

- 演示服务层 `backend/app/services/demo_research.py` **不 import** `app.models` /
  `app.database`，路由层没有 `db: Session = Depends(get_db)` 参数；
- `backend/tests/test_demo_research.py` 断言：调用全部 7 个端点前后，
  `students` / `case_sessions` / `learning_evidence_events` / `teacher_score_reviews`
  四张表行数不变；
- 真实研究导出仍走 `/api/teacher/export/research-data[.csv]`，
  与演示路径**互不引用数据**，只在页面上互相链接；
- 演示 CSV 文件名固定含 `SYNTHETIC`，首列 `SYNTHETIC_DATA_ORIGIN`，每行带 `DISCLAIMER`，
  响应头 `X-Data-Origin`；**没有**"去掉合成标记下载"的参数。

### 9.2 逻辑分离

1. **不共表**：真实研究数据**不写入**平台业务表（`students`、`case_sessions`、
   `learning_evidence_events`、`teacher_score_reviews`）。研究字段在**导出后的研究数据集**中生成。
2. **不共用 ID 空间**：`study_id`（`R-...`）与平台 `student_id`（`S0001`）是两套编号，
   连接只通过连接表。
3. **不共用导出路径**：真实导出与演示导出是两个端点、两个文件名规则。
4. **不共用图表/页面**：演示页面的任何数字都不得出现在真实研究页；
   真实研究页已声明"本页不含合成数据"。
5. **合并前必须校验**：任何把两份数据放在一起的分析，必须先断言
   `data_origin` 只有一个值，或显式按来源分层。

### 9.3 导出与传输

- 导出文件必须带**来源标记 + 生成时间 + 平台 SHA**；
- 通过加密介质或单位批准的传输方式移交，不使用个人网盘/微信；
- 接收方登记（谁、何时、哪个文件、什么用途）；
- 分析完成后，临时副本删除并记录。

---

## 10. 字段清单速查（真实研究最小集）

```
participants     : study_id, data_origin, group, cohort, site_id, department_id,
                   rotation_start, rotation_end, rotation_weeks, grade_level,
                   consent_status, consent_date, consent_version, ethics_approval_ref,
                   exclusion_reason, enrolled
consent_log      : study_id, event_type, event_date, icf_version, method,
                   witness_or_staff_id, scope, processed_by, processed_date, data_action
assessments      : study_id, data_origin, group, cohort, timepoint, assessment_date,
                   assessment_case_id, case_version, rubric_version,
                   rater_A_id, rater_A_total, rater_A_blinded_to_group,
                   rater_A_blinded_to_timepoint, rater_B_id, rater_B_total,
                   rater_B_blinded_to_group, rater_B_blinded_to_timepoint,
                   rater_agreement_delta, adjudication_used, independent_total,
                   rater_origin, ai_scoring_used_for_primary_outcome,
                   six dimensions, missing_* flags
sessions         : session_id, study_id, data_origin, group, week, session_date,
                   case_code, case_version, completed, completed_steps,
                   evaluation_mode, model_id, prompt_version, ai_invocations_ref
reasoning_steps  : session_id, study_id, data_origin, step_id, step_label,
                   initial_student_answer, ai_tutor_question, tutor_source,
                   revised_student_answer, answer_text_generation,
                   is_real_student, model_call_per_row
expert_review    : reviewer_slot, reviewer_id, reviewer_role, review_date,
                   case_id, case_version, four 1-5 ratings, feedback,
                   final_approval, review_origin, signature_ref
```

---

## 11. 与合成字典的差异一览

| 变更 | 字段/实体 | 原因 |
| --- | --- | --- |
| 新增实体 | `consent_log` | 同意是可审计事件序列，不是一个状态 |
| 新增 | `site_id`, `department_id`, `rotation_start/end/weeks` | 整群设计与批次混杂控制 |
| 新增 | `consent_status`, `consent_date`, `consent_version`, `ethics_approval_ref` | 伦理要求 |
| 新增 | `withdrawal_date`, `withdrawal_scope` | 撤回可执行 |
| 新增 | `rater_*_blinded_to_group/timepoint`, `rater_C_*`, `rater_agreement_delta`, `adjudication_used` | 盲法与一致性可核查 |
| 新增 | `missing_*` 系列 | 缺失显式编码 |
| 新增 | `answer_text_generation`, `is_real_student`, `model_call_per_row`, `tutor_source` | 区分真实与合成、AI 与规则 |
| 改名 | `initial_student_answer_synthetic` → `initial_student_answer`（真实研究） | 列名即来源声明 |
| 删除（真实研究） | `study_status`, `simulation_seed`, `synthetic_teacher_intervention`, `date_relative` | 演示专用 |
| 统一枚举 | `evaluation_mode`: `ai` / `rule_fallback` / `no_ai` | 与平台 `scores.evaluation_mode` 对齐 |
| 明确 | `rater_origin` 真实值为 `REAL_BLINDED_RATER` | 防止演示值被沿用 |
