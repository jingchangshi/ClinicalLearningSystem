# A02 平台 schema 核对与病例卡映射说明

> 本文件只做**只读**核对：阅读 `backend/app/models.py`、`backend/app/routes/cases.py`、`backend/app/routes/teacher.py`、`backend/app/services/serializers.py`、`backend/app/seed_data.py`。未连接数据库、未执行任何写操作、未运行 seed。

## 1. 核对依据（真实代码位置）

| 内容 | 文件:行 |
| --- | --- |
| `Case` ORM 模型 | `backend/app/models.py:67-85` |
| 创建病例逻辑 | `backend/app/routes/cases.py:25-44`（`create_case_from_payload`） |
| 更新病例逻辑 | `backend/app/routes/cases.py:47-63`（`update_case_from_payload`） |
| 教师端创建接口 | `backend/app/routes/teacher.py:431-434`（`POST /api/teacher/cases`） |
| 教师端更新接口 | `backend/app/routes/teacher.py:437-443`（`PUT /api/teacher/cases/{case_id}`） |
| 教师端/学生端序列化 | `backend/app/services/serializers.py:81-124` |
| Pydantic 模型 | `backend/app/schemas.py:14-44`（`CaseRead` / `CaseCreate`） |
| 种子病例 | `backend/app/seed_data.py:539-625`（`_case_payloads`） |
| 五阶段定义 | `backend/app/core/reasoning_steps.py:11-34` |
| 六维权重（平台规则评分） | `backend/app/services/scoring_llm.py:7-14` |
| 难度词表 | `backend/app/services/catalog_tags.py:25-34` |
| 去标识化扫描 | `backend/app/core/deidentify.py:128-163`（`scan_case_payload`） |

## 2. `Case` 表真实列

| 列名 | 类型 | 可空 | 说明 |
| --- | --- | --- | --- |
| `id` | Integer, PK | 否 | 自增主键 |
| `title` | String(200) | 否 | 病例标题 |
| `disease_category` | String(100) | 否 | 疾病类别（自由文本，未做枚举约束） |
| `difficulty` | String(50) | 否 | 难度（自由文本；`catalog_tags` 识别 基础/进阶/高阶 等，未识别值按 rank=1 处理） |
| `learning_objectives` | Text | 否 | JSON 数组字符串 |
| `chief_complaint` | Text | 否 | 主诉 |
| `history` | Text | 否 | 现病史 |
| `physical_exam` | Text | 否 | 体格检查 |
| `lab_results` | Text | 否 | 实验室检查 |
| `imaging` | Text | 否 | 影像资料 |
| `standard_diagnosis` | Text | 否 | 标准诊断（**仅教师/管理员可见**） |
| `differential_diagnosis` | Text | 否 | JSON 数组字符串 |
| `treatment_plan` | Text | 否 | 治疗方案（**仅教师/管理员可见**） |
| `rubric` | Text | 否 | JSON 对象字符串 |

学生可见字段由 `serialize_case_for_student` 限定为：`id`、`title`、`disease_category`、`difficulty`、`learning_objectives`、`chief_complaint`、`history`、`physical_exam`、`lab_results`、`imaging`。`standard_diagnosis`、`treatment_plan`、`rubric`、`differential_diagnosis` 不下发学生，符合 `AGENTS.md` 第 2 条不变量。

## 3. 六份病例卡 → `Case` 列映射

| 病例卡字段 | 目标列 | 处理方式 | 备注 |
| --- | --- | --- | --- |
| 病例编号 | `title` 前缀或 `disease_category` | 建议 `title` 写成 `CASE-T01 系统性红斑狼疮（训练病例·待审）` | `Case` 无独立 `case_code` 列 |
| 类型（训练/考核） | **无对应列** | 只能写进 `title` 或 `disease_category` 文本 | 见第 4 节限制 |
| 适用学段 | **无对应列** | 可并入 `learning_objectives` 或 `title` | 见第 4 节限制 |
| 教学目标 | `learning_objectives` | JSON 数组字符串 | 平台前端按数组渲染 |
| 核心表现·主诉 | `chief_complaint` | 纯文本 | |
| 核心表现·现病史 | `history` | 纯文本 | |
| 核心表现·查体 | `physical_exam` | 纯文本 | |
| 核心表现·化验 | `lab_results` | 纯文本 | |
| 核心表现·影像 | `imaging` | 纯文本 | |
| 5 阶段逐步释放信息 | **无对应列** | 只能整段并入 `history` 或保留在文档中 | 见第 4 节限制 |
| 诊断及鉴别逻辑 | `standard_diagnosis` + `differential_diagnosis` | 诊断纯文本；鉴别为 JSON 数组 | 仅教师可见 |
| 危险信号 | **无对应列** | 可并入 `history` 或 `treatment_plan` 文本 | |
| 检查策略 | **无对应列** | 可并入 `lab_results` 或 `treatment_plan` | |
| 治疗策略 | `treatment_plan` | 纯文本 | 仅教师可见 |
| 常见错误 | `rubric` 或 `differential_diagnosis` | 建议写进 `rubric` 的自定义键 | `rubric` 是自由 JSON 对象 |
| 评分要点（六维） | `rubric` | JSON 对象，键为 `medical_knowledge` 等 | 平台会把 `rubric` 传给评分提示词 |
| 指南与文献 | **无对应列** | 可并入 `rubric` 自定义键或 `treatment_plan` | |
| 脱敏说明 / 审核状态 | **无对应列** | 只能留在 Markdown 文档 | 见第 4 节限制 |

`create_case_from_payload` 的必填键（缺失即 `KeyError` → 500）：`title`、`disease_category`、`difficulty`、`chief_complaint`、`history`、`physical_exam`、`lab_results`、`imaging`、`standard_diagnosis`、`treatment_plan`。
可选键：`learning_objectives`、`differential_diagnosis`、`rubric`（缺省为 `[]` / `[]` / `{}`）。

## 4. 平台支持 / 不支持的字段（明确结论）

| 能力 | 平台是否支持 | 依据 |
| --- | --- | --- |
| 标记“训练病例 / 独立考核病例” | **不支持** | `Case` 无 `case_type` / `is_assessment` 列；`CaseCreate` 无该字段 |
| 标记审核状态（`PENDING_REAL_REVIEW` 等） | **不支持** | `Case` 无 `review_status` 列；`GeneratedCaseDraft.status` 只属于 AI 生成草稿表，不是 `cases` 表 |
| 按 S1–S5 逐步释放信息 | **不支持** | 前端 `CaseTrainingClient.tsx` 一次性渲染 `chief_complaint` / `history` / `physical_exam` / `lab_results` / `imaging`；`Case` 无分阶段字段 |
| 训练/考核隔离 | **不支持（仅靠流程保证）** | 平台不区分病例用途；`/api/cases` 对所有已登录学生返回全部病例 |
| 六维评分权重 10/20/25/15/20/10 | **部分支持** | `rubric` 可携带任意 JSON，但 `scoring_llm.WEIGHTS` 硬编码为 20/20/20/15/15/10；规则兜底评分按硬编码权重计算 |
| 病例级“危险信号”字段 | **不支持** | 无对应列；只能写进文本 |
| 病例级“检查策略”字段 | **不支持** | 无对应列；只能写进 `lab_results` / `treatment_plan` |
| 病例级“指南与文献”字段 | **不支持** | 无对应列；只能写进 `rubric` 自定义键 |
| 教师端创建病例 | **支持** | `POST /api/teacher/cases`，需 `teacher` 角色 |
| 教师端更新病例 | **支持** | `PUT /api/teacher/cases/{case_id}` |
| 去标识化提示 | **部分支持** | `_deidentification_gate` 只**告警**，除非 `REQUIRE_CASE_DEIDENTIFICATION=true` 才 400 |
| 难度枚举 | **弱约束** | 列是自由文本；`catalog_tags.DIFFICULTY_RANK` 只识别 基础/初级/进阶/中级/高阶/高级 等，未识别值按 rank=1 |

## 5. 差异与风险（必须让审核教师知道）

1. **评分权重不一致**：任务书要求 10/20/25/15/20/10，平台规则评分硬编码 20/20/20/15/15/10。若要让平台按任务书权重计分，需要改 `backend/app/services/scoring_llm.py` 并补测试——本工作包**没有**改代码，也不建议在未与平台负责人确认前改动。
2. **训练/考核隔离只在文档层**：平台会把所有 `cases` 行都列给学生。若直接把考核病例 `POST` 进平台，学生会看到它。因此本工作包的考核病例**不导入平台**，只作为纸质/离线考核材料，直到平台增加 `case_type` 字段。
3. **五阶段释放只在文档层**：平台整例呈现，教师需按卡片中的 S1–S5 表在课堂上分段口述或分段发放纸质材料。
4. **审核状态只在文档层**：平台没有审核工作流；`PENDING_REAL_REVIEW` 只能写在 Markdown 卡片和审核表中。
5. **去标识化只告警**：默认 `REQUIRE_CASE_DEIDENTIFICATION=false`，含身份信息的病例仍可入库；作者需自行遵守脱敏规则。
6. **`differential_diagnosis` 学生不可见**：它只出现在教师序列化结果里，因此鉴别诊断的教学价值依赖教师在课堂上讲解。

## 6. 结论

- 六份卡片可以作为**标准化教学文档**提交，字段内容能完整映射到 `Case` 的文本列。
- 但“训练/考核类型”“审核状态”“五阶段释放”这三项**平台当前不支持**，只能由文档与教师流程保证。
- 因此 A04 的选择是：CASE-T01 作为审核中的标准化教学文档提交；平台 UI 路径以既有 SLE 种子病例演示。同时提供一份**未执行**的干跑 JSON 载荷，供平台负责人评估字段映射（见 `A04_CASE-T01_payload.json` 与 `A04_platform_path_status.md`）。
