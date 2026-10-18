# A04 CASE-T01 平台 UI 路径状态说明

> 本文件只描述**仓库现状**与**干跑校验结果**。未连接数据库、未调用任何写接口、未执行 `POST /api/teacher/cases`、未运行 seed。

## 1. 仓库中已经存在的 SLE 病例（事实核对）

### 1.1 命令与真实输出

```console
$ grep -n '"title":' backend/app/seed_data.py | sed -n '10,20p'
548:            "title": "SLE基础病例",
563:            "title": "SLE与感染鉴别病例",
578:            "title": "成人Still病病例",
593:            "title": "ANCA相关血管炎病例",
608:            "title": "皮肌炎/抗合成酶综合征病例",
```

（`sed -n '10,20p'` 取的是 `title` 出现顺序中的第 10–14 条；前 9 条是知识单元、技能、指南、SP 病例的标题。）

### 1.2 `_case_payloads()` 中的五个病例（`backend/app/seed_data.py:539-625`）

| 行号 | 标题 | `disease_category` | `difficulty` |
| --- | --- | --- | --- |
| 548 | SLE基础病例 | 系统性红斑狼疮 | 基础 |
| 563 | SLE与感染鉴别病例 | 系统性红斑狼疮/感染鉴别 | 进阶 |
| 578 | 成人Still病病例 | 成人Still病 | 中等 |
| 593 | ANCA相关血管炎病例 | ANCA相关血管炎 | 进阶 |
| 608 | 皮肌炎/抗合成酶综合征病例 | 炎性肌病 | 高阶 |

其他模块（知识单元 / 临床技能 / 指南 / SP 病例）中与 SLE 相关的标题：`SLE核心诊断线索`（知识单元，行 351）、`SLE管理建议摘要`（指南，行 448）。

### 1.3 是否已存在等价的 SLE 训练病例？

**存在。** `SLE基础病例`（行 548）与 CASE-T01 覆盖同一疾病与同一核心线索：

| 维度 | 平台 `SLE基础病例` | 本工作包 CASE-T01 |
| --- | --- | --- |
| 主诊断 | 系统性红斑狼疮，疑似狼疮肾炎 | 系统性红斑狼疮（疑伴狼疮肾炎） |
| 核心表现 | 发热、蝶形红斑、关节痛、脱发、口腔溃疡、蛋白尿 | 同上，并补充光敏感、体重下降、血压 |
| 难度 | 基础 | 基础 |
| 五阶段教学设计 | 无（`Case` 无分阶段字段） | 有（S1–S5 表） |
| 评分要点 | 通用 `common_rubric`（六键各一句话） | 六维各含可观察评分点与满分示例 |
| 危险信号 | 未单列 | 单列 6 条 |
| 指南引用 | 未列 | 列出并标注 `版本待教师核对` |
| 审核状态 | 无（平台无该字段） | `PENDING_REAL_REVIEW` |

结论：平台**已有**可用的 SLE 训练病例，可支撑 UI 演示；CASE-T01 的增量价值在教学设计（五阶段、危险信号、评分细则、指南标注），而不是“平台缺一个 SLE 病例”。

## 2. 平台 schema 能表达什么、不能表达什么

详见 `A02_platform_schema_notes.md`。摘要：

| CASE-T01 的内容 | `Case` 是否支持 |
| --- | --- |
| 病例编号 | 否（无 `case_code` 列，只能写进 `title`） |
| 类型（训练/考核） | 否（无 `case_type` 列） |
| 审核状态 `PENDING_REAL_REVIEW` | 否（无 `review_status` 列） |
| 教学目标 / 主诉 / 现病史 / 查体 / 化验 / 影像 | 是 |
| 标准诊断 / 鉴别诊断 / 治疗方案 / 评分量规 | 是（仅教师可见） |
| 五阶段 S1–S5 分阶段释放 | 否（前端一次性渲染全部文本） |
| 危险信号 / 检查策略 / 常见错误 / 指南与文献 | 否（无独立列，只能并入文本或 `rubric`） |

## 3. 本工作包的实际选择（如实说明）

任务书给了两种可选路径。本工作包**两条都做了，但都止于“不执行”**：

### 3.1 路径一：作为审核中的标准化教学文档提交（已完成）

CASE-T01 以 Markdown 卡片形式交付（`A01_training_SLE.md`），字段完整、审核状态 `PENDING_REAL_REVIEW`。平台 UI 路径以既有 `SLE基础病例` 演示，无需新增数据。

### 3.2 路径二：干跑导入载荷（已提供，**未执行**）

- 载荷文件：`A04_CASE-T01_payload.json`
- 目标接口：`POST /api/teacher/cases`（`backend/app/routes/teacher.py:431`，前缀 `/api/teacher`，需 `teacher` 角色）
- 状态：**NOT EXECUTED**。没有发出任何 HTTP 请求，没有连接数据库，没有创建任何病例行。

精确的调用形式（**仅示例，未执行**）：

```bash
# 未执行。执行前必须：两位真实教师已完成 CASE-T01 审核，且平台已就 case_type / review_status 字段作出决定。
# TOKEN 必须是真实教师账号登录后获得的 JWT；不要把 token 写进仓库或命令行历史。
curl -sS -X POST "http://127.0.0.1:8100/api/teacher/cases" \
  -H "Authorization: Bearer $TEACHER_JWT" \
  -H "Content-Type: application/json" \
  --data-binary @docs/teaching_grant_2026/workpackages/A_cases/A04_CASE-T01_payload.json
```

### 3.3 干跑校验（只读、离线，已真实执行）

**校验 1：载荷键是否匹配 `create_case_from_payload` 的必填键**

```console
$ python3 -I -c "import json; ..."   # 读取 JSON 并比对必填键
required missing: none
optional missing: none
differential count: 8
rubric keys: ['clinical_decision', 'differential_diagnosis', 'evidence_based_medicine', 'evidence_integration', 'key_information', 'medical_knowledge']
```

**校验 2：载荷能否通过 `CaseCreate` Pydantic 校验**

```console
$ cd backend && uv run --python 3.11 --with-requirements requirements.txt python - <<'PY'
from app.schemas import CaseCreate
...
PY
CaseCreate validation: PASS
extra fields rejected? no
serialized byte size: 4516
```

（`_file_purpose`、`_status` 等下划线开头的键是文档注释，不参与 schema；若真的调用接口，需先删除这些键，否则 `CaseCreate` 虽未配置 `extra="forbid"` 而会忽略它们，但 `create_case_from_payload` 只读取已知键，不影响结果。）

**校验 3：平台自带的去标识化门禁对载荷的报告**

```console
$ cd backend && uv run --python 3.11 --with-requirements requirements.txt python - <<'PY'
from app.core.deidentify import scan_case_payload
...
PY
{
  "clean": true,
  "findings": [],
  "message": ""
}
```

说明：`scan_case_payload` 只在内存中做正则扫描，不写库；结果为 `clean: true`，即平台认为载荷中没有手机号、身份证号、病历号、姓名标签等标识形态内容。

> 以上三次执行都只读取本地文件并调用纯函数，**没有**触发数据库连接或写操作。

## 4. 为什么不建议现在导入

1. **平台不能标记训练/考核类型**：一旦导入，CASE-T01 会成为和 `SLE基础病例` 一样的普通训练病例，学生可见。这对训练病例是可接受的，但对 CASE-A01/A02 是**不可接受**的——所以考核病例一律不导入。
2. **平台不能标记审核状态**：导入后“待审”这一关键信息会丢失，后续无法从平台区分“已审核”和“未审核”的病例。
3. **会与 `SLE基础病例` 重复**：`catalog_tags` 用 `disease_category` / `learning_objectives` / `difficulty` 打标签，两个同为“系统性红斑狼疮 + 基础”的病例会被推荐器视为同类项，可能造成同一疾病被重复推荐。
4. **两位真实教师尚未审核**：在 `PENDING_REAL_REVIEW` 解除前，把内容写进平台等于把未审核材料交给学生。

## 5. 结论

| 问题 | 回答 |
| --- | --- |
| 平台是否已有等价 SLE 训练病例 | **有**，`SLE基础病例`（`backend/app/seed_data.py:548`） |
| CASE-T01 是否已导入平台 | **否** |
| 是否提供了干跑载荷 | **是**，`A04_CASE-T01_payload.json`，标记 `NOT EXECUTED` |
| 平台 UI 路径如何演示 | 用既有 `SLE基础病例` 走 学生登录 → 病例训练 → 提交 → 结果页 的流程 |
| 还缺什么 | 平台侧 `case_type` 与 `review_status` 字段；两位真实教师审核；评分权重与任务书对齐的决策 |
