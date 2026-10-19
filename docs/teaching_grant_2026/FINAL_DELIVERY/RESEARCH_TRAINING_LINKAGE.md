# Research ↔ Training 过程证据关联（R9 §4）

> 状态：**只读关联已实现并通过测试**。Training 与 Assessment 的业务与写入仍严格分离。
> 实现：`backend/app/research/linkage.py`、`backend/app/research/teaching_log.py`；
> 接入：`backend/app/assessment/dataset.py`；统计适配：
> `backend/app/research/cohort_stats.py::student_scores_from_export`；
> 测试：`backend/tests/test_research_training_linkage.py`（13 项，全部通过）。

## 1. 修复的缺口

`assessment/dataset.py` 的导出此前对每行直接写入 `training_exposure = None`、
`intervention_count = None`，Research 成绩管理与训练过程管理之间没有数据闭环。

现在这两个字段由 **Research 层的只读关联**填充：只查询已写入的数据库行与受控的
教学登记文件，不调用 Training 的评分、导师、画像或推荐服务，不写入任何 Training 行。

## 2. 字段映射（全部来自真实行）

`linkage.clinpath_process`（窗口内）：

| 指标 | 来源 | 说明 |
| --- | --- | --- |
| `completed_formative_cases` | `case_sessions` + `student_answers` | 完成且五阶段齐备的**不同病例**数；同一病例重复训练不重复计 |
| `completed_five_stage_runs` | 同上 | 完成的五阶段训练**次数**（含重复训练） |
| `sessions_started` | `case_sessions.started_at` | 窗口内开始的会话数 |
| `tutor_questions_shown` | `tutor_turns.role="tutor"` | 学生实际看到的追问条数 |
| `ai_tutor_invocations` | `ai_invocations.task_type="tutor_question"` | **每次学习事件一行审计**，与上一项是不同的量，两者不相加 |
| `ai_tutor_provider_calls` / `ai_tutor_successful` | 同上 | 供应商调用次数 / 成功次数 |
| `rule_fallback_count`、`rule_fallback_by_task` | `ai_invocations.fallback_used` | 规则降级次数，按任务分类 |
| `training_scores[]` | `scores` | 每次五阶段训练的六维分、`evaluation_mode`、`degraded`、时间 |
| `profile_evidence` | `learning_evidence_events`、`competency_profiles` | 证据事件数、关联到会话的事件数、评分来源分布、是否有画像行 |
| `d4_d5_recommendations` | `learning_recommendations` | 推荐任务（病例、阶段、时间）及完成情况（推荐之后完成的会话） |
| `teacher_interventions` | `teaching_interventions` | 目标学生包含该生且窗口内的干预条数，按类型计数 |
| `actual_training_window` | `case_sessions` | 首次开始与最后完成时间 |

导出列：

- `training_exposure`：ClinPath 行为 `clinpath_cases=…;five_stage_runs=…;ai_tutor_invocations=…`；
  CBL 行为 `cbl_logged_sessions=…;minutes=…`（教学登记）；无法判定时为 `None`。
- `intervention_count`：窗口内教师干预条数；无法判定时为 `None`。
- `cbl_case_topics`：仅 CBL 行，来自教学登记，`;` 分隔。
- `batch_index`：批次实际时间顺序，仅当该来源的全部批次都登记了开始日期时给出。
- `assessment_form_slot`：本次考核实际使用的题本槽位（`A01`/`A02`），由冻结题本顺序
  `FORM_BY_ORDER[form_order][timepoint]` 推出；**冻结 CSV 的题本顺序校验以此列为准**。
  `assessment_form_id` 仍是题本记录 id，只用于回溯，两者不再混用
  （见 §8.1 的修复记录）。

## 3. CBL 教学过程登记（最小结构化）

`teaching_log.py` 读取一个受控 JSON 文件（默认 `~/.config/clinpath/cbl_teaching_log.json`，
可用 `CLINPATH_CBL_TEACHING_LOG` 指定）。该文件含真实教师姓名与真实病例主题，
**不得进入公开仓库**；仓库中只有读取代码与格式说明。

字段（`teaching_log_version: cbl-teaching-log-v1`）：批次、日期、实际 CBL 病例主题、
教学时长（分钟）、指导教师、是否完成、**是否与独立考核病例主题相似（由教师登记）**、
备注。相似性不做推断——推断必须读取保密考核题本。

诚实性规则：

- 文件不存在 → `not_registered`，导出标 `missing`，附原因；**不表示“没有教学”**。
- 文件存在但格式错误 → `invalid`，整份拒绝，不做部分采用（丢一条记录会被误读为
  未发生教学）。
- 文件 `data_origin` 与导出不一致 → `origin_mismatch`，不采用（合成/预试登记不得
  描述真实研究行，反之亦然）。
- 冻结清单只保存 `version/sha256/entry_count/status`，**不保存本地文件路径**。

## 4. 来源区分与缺失语义

`export` 与冻结快照都携带 `provenance`，分为五类：
`independent_assessment` / `training` / `teaching_log` / `study_allocation` /
`research_metadata`（含 `linkage_version`）。每行的 `linkage.sources` 给出具体表名。

缺失处理：

- 批次未登记教学窗口 → `clinpath_process.status = "undetermined"`，`reason` 明确；
  同时在 `observed_all_records` 中给出全量记录（明确标注未按窗口过滤），
  `training_exposure` / `intervention_count` 为 `None`。
- 每个缺口同时进入 `linkage.missing`（指标 + 原因），供研究核对。
- **不把 `None` 转成 0，不生成训练次数，不虚构教师干预。**

## 5. 冻结与复现

- 冻结快照保存 `linkage_version` 与 `provenance`；`dataset_version` 不变则不重新生成。
- 关联载荷不含“生成时间”，同一数据库状态两次导出字节一致
  （`test_the_same_state_produces_the_same_rows`）。
- 冻结后新增训练只改变工作导出，不改变已冻结版本
  （`test_a_frozen_version_keeps_its_numbers`）。
- 导出与冻结前后对全部 Training 表做快照比对，行数与画像数值不变
  （`test_export_and_freeze_do_not_mutate_training_rows`）。

## 6. 统计函数接收真实导出格式

`cohort_stats.student_scores_from_export(records)` 把导出记录（含 linkage、
provenance 等附加键）转换为分析用的 `StudentScores`；拒绝缺少编码/批次、题本顺序
非法、重复 `(学生, 时间点)`、跨时间点不一致、混合 `data_origin` 的记录。
`test_stats_accept_the_real_export_shape` 用真实导出跑通
`per_cohort_stats` / `missingness`，并确认无配对数据时分析被阻断而不是伪造数值。

## 7. 测试清单（`tests/test_research_training_linkage.py`）

- ClinPath 指标来自真实行：完成次数、病例数、AI 调用、规则降级、推荐完成、教师
  干预、训练窗口；`training_exposure` / `intervention_count` 非空且与行一致。
- Assessment 分数与 Training 分数不混淆：`final_score` 来自双评（90），训练分为
  规则分，两者互不写入。
- CBL 教学登记进入导出；未登记 ≠ 无教学；异源登记被拒；格式错误整份拒绝。
- 未登记窗口 → `undetermined` + 原因，而不是 0。
- 只读：导出与冻结不改变 Training 表；冻结版本可复现；同状态字节一致。
- 统计适配器：真实导出形状可用；非法输入被拒。

## 8. 已修复的链路缺陷（R9 集成负责人复核后）

1. **`assessment_form_id` 与题本槽位编码混用（已修复）**：工作导出写入题本**记录 id**
   （`dataset.py`），而 `dataset_export.build_rows` 按 `A01`/`A02` **槽位编码**校验
   （`FORM_BY_ORDER`），两个组件对同一列含义不一致，真实题本 id ≠ 1/2 时
   「工作导出 → 冻结 CSV」必然失败（旧测试恰好用 id 1/2 才未暴露）。现拆分为两列：
   - `assessment_form_id`：题本记录 id，可回溯，**不参与顺序校验**；
   - `assessment_form_slot`：`A01`/`A02` 槽位，**顺序校验的唯一依据**，缺失即拒绝。

   `build_rows` 仍校验 `assessment_form_slot == FORM_BY_ORDER[form_order][timepoint]`；
   若有人把槽位编码写进 id 列（旧的歧义形状）则明确拒绝，不再给出
   “requires A01, got 3” 这类无意义报错。`COLUMNS` 与 `DATA_DICTIONARY.md` 同步更新。
   证据：`test_the_working_export_feeds_the_frozen_csv_chain` 用 id 不是 1/2、编码不是
   `A01`/`A02` 的真实导出直接跑通 `build_rows` 与 `freeze`，并断言错误槽位、缺失槽位、
   旧形状仍被拒绝。

## 9. 剩余风险 / 未完成事项

1. **教师干预的归属**：`teaching_interventions.target_students_json` 只有学生 id，
   无批次字段；窗口过滤依赖批次教学窗口，不是干预自身的批次标注。
2. **`rule_fallback_count` 覆盖全部 AI 任务**（导师与评分），分类计数另给
   `rule_fallback_by_task`；不要把总数直接当作“AI 导师降级次数”。
3. 教学登记是**文件**而非数据库表：无审计日志、无并发写保护；写入由教学管理员
   人工完成，版本由 SHA-256 记录。
4. 真实研究数据尚未产生；本文件中的所有验证均使用隔离测试库中的测试夹具。
