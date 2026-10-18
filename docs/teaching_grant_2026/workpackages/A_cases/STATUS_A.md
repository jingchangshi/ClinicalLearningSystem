# Work package A 状态报告（STATUS_A）

- 报告日期：2026-10-18
- 运行代码版本（仓库 HEAD）：`1d4ef4823c75fb9d89a7aec734b8b84d0bfa5c41`
- 工作包目录：`docs/teaching_grant_2026/workpackages/A_cases/`
- 校验脚本：`scripts/grant/check_case_cards.py`
- 性质：**材料起草与只读校验**。无数据库连接、无 seed/reset、无接口写入、未部署、未产生任何真实教学效果数据。

## 一、逐项状态

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| A01 六份病例卡 + 索引 | **完成** | 4 训练 + 2 独立考核；全部 `PENDING_REAL_REVIEW`；字段顺序与任务书一致 |
| A02 schema 核对 + 校验脚本 | **完成** | schema 映射文档 + 只读 dry-run 校验脚本；脚本已运行，88/88 PASS，退出码 0 |
| A03 空白教师审核表 | **完成** | Markdown + CSV；12 行；姓名/日期留空；结论 `PENDING_REAL_REVIEW` |
| A04 CASE-T01 平台路径 | **完成（路径为“文档提交 + 干跑载荷”，未导入）** | 已核实平台已有等价 SLE 病例；干跑 JSON 通过 `CaseCreate` 与去标识化门禁校验；**未执行** `POST /api/teacher/cases` |

## 二、创建的文件

| 路径 | 说明 |
| --- | --- |
| `docs/teaching_grant_2026/workpackages/A_cases/A01_training_SLE.md` | CASE-T01 系统性红斑狼疮（训练） |
| `docs/teaching_grant_2026/workpackages/A_cases/A01_training_RA.md` | CASE-T02 类风湿关节炎（训练） |
| `docs/teaching_grant_2026/workpackages/A_cases/A01_training_AAV.md` | CASE-T03 ANCA 相关性血管炎（训练） |
| `docs/teaching_grant_2026/workpackages/A_cases/A01_training_IIM.md` | CASE-T04 炎性肌病（训练） |
| `docs/teaching_grant_2026/workpackages/A_cases/A01_assessment_UA.md` | CASE-A01 未分化多关节炎（独立考核） |
| `docs/teaching_grant_2026/workpackages/A_cases/A01_assessment_multisystem.md` | CASE-A02 成人 Still 病伴 MAS 风险（独立考核） |
| `docs/teaching_grant_2026/workpackages/A_cases/A01_case_index.md` | 六例索引、训练/考核隔离、六维权重表 |
| `docs/teaching_grant_2026/workpackages/A_cases/A02_platform_schema_notes.md` | `Case` 列映射、平台支持/不支持清单、差异与风险 |
| `docs/teaching_grant_2026/workpackages/A_cases/A03_teacher_review_form_BLANK.md` | 空白审核表（Markdown，含填写说明与重点核对事项） |
| `docs/teaching_grant_2026/workpackages/A_cases/A03_teacher_review_form_BLANK.csv` | 空白审核表（CSV，11 列 × 12 数据行） |
| `docs/teaching_grant_2026/workpackages/A_cases/A04_platform_path_status.md` | A04 事实核对与决策说明 |
| `docs/teaching_grant_2026/workpackages/A_cases/A04_CASE-T01_payload.json` | 干跑导入载荷，标记 `DRAFT_ONLY_NOT_IMPORTED` / `PENDING_REAL_REVIEW`，**未执行** |
| `docs/teaching_grant_2026/workpackages/A_cases/STATUS_A.md` | 本报告 |
| `scripts/grant/check_case_cards.py` | 只读 dry-run 校验脚本（Python 3.11 stdlib） |

未修改任何既有生产代码、`backend/` 源码、数据库、`docs/ARCH.md`。

## 三、实际执行的命令与真实输出

### 3.1 A04 事实核对：平台已有病例标题

```console
$ grep -n '"title":' backend/app/seed_data.py | sed -n '10,20p'
548:            "title": "SLE基础病例",
563:            "title": "SLE与感染鉴别病例",
578:            "title": "成人Still病病例",
593:            "title": "ANCA相关血管炎病例",
608:            "title": "皮肌炎/抗合成酶综合征病例",
```

结论：平台**已有**与 CASE-T01 等价的 SLE 基础训练病例（`SLE基础病例`，`backend/app/seed_data.py:548`，`disease_category=系统性红斑狼疮`，`difficulty=基础`）。

### 3.2 A02/A01 校验脚本（文本模式）

```console
$ python3 -I scripts/grant/check_case_cards.py
病例卡目录：/home/jcshi/workspace/clinical_learning_system/docs/teaching_grant_2026/workpackages/A_cases
发现 6 份卡片：A01_training_AAV.md, A01_training_IIM.md, A01_training_RA.md, A01_training_SLE.md, A01_assessment_UA.md, A01_assessment_multisystem.md
```

逐项结果表（88 行）节选如下，完整表格见脚本输出：

```console
| 病例     | 检查项                       | 结果 | 说明                                                                                                                         |
| -------- | ---------------------------- | ---- | ---------------------------------------------------------------------------------------------------------------------------- |
| CASE-T03 | 病例编号合法                 | PASS | CASE-T03                                                                                                                     |
| CASE-T03 | 编号与文件名一致             | PASS | 期望 A01_training_AAV.md，实际 A01_training_AAV.md                                                                           |
| CASE-T03 | 类型与编号一致               | PASS | 期望 训练病例，实际 '训练病例'                                                                                               |
| CASE-T03 | 必填字段齐全                 | PASS | 8/8                                                                                                                          |
| CASE-T03 | 审核状态 PENDING_REAL_REVIEW | PASS | 实际：'PENDING_REAL_REVIEW'                                                                                                  |
| CASE-T03 | 必需章节齐全                 | PASS | 12/12                                                                                                                        |
| CASE-T03 | 五阶段表 S1-S5               | PASS | 5 行 S1-S5，4 列均非空                                                                                                       |
| CASE-T03 | 五阶段表列名                 | PASS | 列名：阶段 / 本阶段向学生释放的信息 / 学生应完成的任务 / 常见错误                                                            |
| CASE-T03 | 常见错误 ≥4 条               | PASS | 8 条                                                                                                                         |
| CASE-T03 | 六维评分表 10/20/25/15/20/10 | PASS | 六维齐全，合计 100                                                                                                           |
| CASE-T03 | 指南章节含核对提示           | PASS | 含指南引用与核对提示                                                                                                         |
| CASE-T03 | 脱敏检查表                   | PASS | 8 项；真实姓名=否,使用“患者C”；真实病例=否,虚构合成                                                                          |
| CASE-T03 | 未声称已完成审核             | PASS | 无                                                                                                                           |
| CASE-T03 | 训练/考核隔离声明            | PASS | 训练病例,仅用于形成性训练,不进入独立考核题库                                                                                 |
...
| ALL      | 六个病例齐全                 | PASS | 6/6                                                                                                                          |
| ALL      | 主诊断不重复                 | PASS | 6 个不同主诊断                                                                                                               |
| ALL      | 训练/考核疾病池不重叠        | PASS | 无重叠                                                                                                                       |
| ALL      | 训练与考核各 4/2 例          | PASS | 训练 4 例，考核 2 例                                                                                                         |

合计 88 项检查：通过 88，失败 0
总体结果：PASS
```

退出码：

```console
$ echo "EXIT=$?"
EXIT=0
```

各病例的具体条目数：

| 病例 | 常见错误 | 六维合计 | 必需章节 | 脱敏检查项 |
| --- | --- | --- | --- | --- |
| CASE-T01 | 7 条 | 100 | 12/12 | 8 |
| CASE-T02 | 8 条 | 100 | 12/12 | 8 |
| CASE-T03 | 8 条 | 100 | 12/12 | 8 |
| CASE-T04 | 8 条 | 100 | 12/12 | 8 |
| CASE-A01 | 8 条 | 100 | 12/12 | 8 |
| CASE-A02 | 8 条 | 100 | 12/12 | 8 |

### 3.3 A02 校验脚本（JSON 模式）

```console
$ python3 -I scripts/grant/check_case_cards.py --json
$ echo "JSON_EXIT=$?"
JSON_EXIT=0
```

```json
{"ok": true, "total": 88, "passed": 88, "failed": 0,
 "cards": ["A01_training_AAV.md", "A01_training_IIM.md", "A01_training_RA.md", "A01_training_SLE.md", "A01_assessment_UA.md", "A01_assessment_multisystem.md"]}
```

### 3.4 A02 校验脚本的负向对照（证明它真的会 FAIL）

把六份卡片复制到 `/tmp/negcase/`，人为破坏三处后运行（未改动仓库内卡片）：

```console
$ python3 -I scripts/grant/check_case_cards.py --dir /tmp/negcase --json
$ echo "NEG_EXIT=$?"
NEG_EXIT=1
{'ok': False, 'total': 88, 'passed': 85, 'failed': 3}
 FAIL: CASE-T01 | 审核状态 PENDING_REAL_REVIEW | 实际：'已完成审核'
 FAIL: CASE-T01 | 未声称已完成审核 | 命中：已完成审核
 FAIL: ALL | 主诊断不重复 | 重复：{"类风湿关节炎": ["CASE-T02:类风湿关节炎(早期,活动期)", "CASE-T01:类风湿关节炎(早期,活动期)"]}
```

说明：脚本确实能检出“声称已审核”与“主诊断重复/训练与考核疾病池重叠”，并在失败时以退出码 1 结束。

### 3.5 A03 CSV 结构校验

```console
$ python3 -I - <<'PY'
import csv
p='docs/teaching_grant_2026/workpackages/A_cases/A03_teacher_review_form_BLANK.csv'
rows=list(csv.reader(open(p,encoding='utf-8')))
print('total lines:', len(rows), '| field counts:', {len(r) for r in rows})
d=list(csv.DictReader(open(p,encoding='utf-8')))
print('rows:', len(d))
print('decisions:', {r['final_decision'] for r in d})
print('names blank:', all(r['reviewer_name']=='' for r in d))
print('dates blank:', all(r['review_date']=='' for r in d))
print('origin:', {r['review_origin'] for r in d})
print('pairs:', len({(r['case_id'],r['reviewer_slot']) for r in d}))
PY

total lines: 13 | field counts: {11}
rows: 12
decisions: {'PENDING_REAL_REVIEW'}
names blank: True
dates blank: True
origin: {'REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED'}
pairs: 12
```

### 3.6 A04 干跑载荷校验（只读、离线）

**校验 1：必填键**

```console
required missing: none
optional missing: none
differential count: 8
rubric keys: ['clinical_decision', 'differential_diagnosis', 'evidence_based_medicine', 'evidence_integration', 'key_information', 'medical_knowledge']
```

**校验 2：`CaseCreate` Pydantic schema**

```console
$ cd backend && uv run --python 3.11 --with-requirements requirements.txt python - <<'PY'
from app.schemas import CaseCreate
...
PY
CaseCreate validation: PASS
extra fields rejected? no
serialized byte size: 4516
```

**校验 3：平台去标识化门禁**

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

说明：三次校验都只读本地文件、调用纯函数；`scan_case_payload` 不写库。**未**调用 `POST /api/teacher/cases`，**未**连接数据库。

### 3.7 脚本静态检查

```console
$ python3 -m py_compile scripts/grant/check_case_cards.py && echo "py_compile OK"
py_compile OK
```

另核对：脚本中没有 `from app...` 导入、没有 `open(..., "w")` / `write_text` / `write(` 调用（grep 无命中），符合“不导入应用、不写文件”的要求。

## 四、关键发现（需要平台侧决策）

1. **平台没有 `case_type` / `review_status` 字段**：`Case` 表（`backend/app/models.py:67-85`）只有 14 个文本列。训练/考核隔离与审核状态**只能在文档层**表达。这直接决定了 A04 不能把考核病例导入平台。
2. **平台没有分阶段释放**：前端 `CaseTrainingClient.tsx` 一次性渲染主诉/现病史/查体/化验/影像；五阶段教学只能靠教师课堂脚本或后续平台改造。
3. **评分权重不一致**：任务书要求 10/20/25/15/20/10，平台 `scoring_llm.WEIGHTS` 硬编码 20/20/20/15/15/10。本工作包按任务书权重写卡片，**未改代码**；是否对齐需平台负责人决定并补测试。
4. **平台已有等价 SLE 病例**：`SLE基础病例`（`seed_data.py:548`），可作为 UI 演示路径，无需新增数据。
5. **去标识化默认只告警**：`REQUIRE_CASE_DEIDENTIFICATION` 默认 `false`，含身份信息的病例仍可入库；本次干跑载荷扫描结果为 `clean`。

## 五、仍待真实教师完成的事项（阻塞项）

| 阻塞项 | 说明 |
| --- | --- |
| 六份卡片均未审核 | 全部为 `PENDING_REAL_REVIEW`；需两名真实教师独立填写 `A03_teacher_review_form_BLANK.csv` 并签字 |
| 指南版本核对 | 卡片中标 `版本待教师核对` 的条目需教师确认：EULAR SLE 管理推荐 2019/2023、EULAR RA 管理推荐 2019/2022、EULAR/ERA-EDTA AAV 推荐版本、KDIGO 版本、EULAR/ACR IIM 推荐 2017/2023、EULAR 早期关节炎推荐年份、EULAR/ACR AOSD 推荐是否存在 |
| 评分量规的可操作性 | 六维权重与各维“可观察评分点”需教师确认能否在见习场景落地 |
| 本科适用性 | 难度标定（基础/进阶/中等）需教师按本校见习大纲确认 |
| 考核病例的使用方式 | 平台不支持考核隔离；CASE-A01/A02 目前只能是纸质/离线考核材料，需教学管理部门确认流程 |
| 真实教学效果 | **未做，也不做**。本工作包不包含任何学生数据或教学效果结论 |

## 六、未执行的验证（如实声明）

本工作包只新增文档与一个独立脚本，未改动后端/前端源码，因此**没有**运行：

- 后端 pytest
- 前端 `npm run typecheck` / `npm run lint` / `npm run build`
- Playwright
- 部署与 `./scripts/verify_deploy.sh`
- 真实浏览器 smoke test

理由：本次变更不触及运行中的应用代码路径；`scripts/grant/check_case_cards.py` 是独立只读脚本，已用 `py_compile` 与实际运行验证。若仓库要求任何新增文件都必须走完整 DoD，请以团队决定为准——本报告不声称已通过完整 DoD。

## 七、一句话结论

A01–A04 的**文档与只读校验**已完成并可复现（校验脚本 88/88 PASS，退出码 0）；六份病例全部是待审草稿（`PENDING_REAL_REVIEW`），**没有任何一份**被声称已审核或可用于正式教学；平台导入路径已核对但**未执行**。
