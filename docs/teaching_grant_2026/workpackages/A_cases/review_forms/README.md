# 真实教师审核材料包（可直接签署）

> **全部条目状态：`PENDING_REAL_REVIEW`；review_origin：`REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED`。**
> 本目录由 AI 准备，**不含任何教师姓名、日期、签字或审核结论**。AI 的检查一律标注为“AI technical/medical DRAFT re-check（非真实教师审定）”。
> 由 `scripts/grant/build_case_review_forms.py` 生成（`--check` 可检测与磁盘文件的漂移）。

## 内容

| 文件 | 用途 | 给谁 |
| --- | --- | --- |
| `CASE_REVIEW_FORM_T01.md` … `T04.md` | 4 份训练病例（SLE / RA / ANCA 血管炎 / 炎性肌病）审核表 | 两位教师各自独立填写 |
| `CASE_REVIEW_FORM_A01.md`、`CASE_REVIEW_FORM_A02.md` | 2 份独立考核病例审核表（含学生可见内容摘录、考核专项核对） | 同上 |
| `RUBRIC_REVIEW_FORM.md` | 六维量表：权重（10/20/25/15/20/10 待确认；训练权重 20/20/20/15/15/10 不变）、A01/A02 锚点、裁决阈值 | 同上 |
| `DIFFICULTY_MATCH_A01_A02.md` | A01/A02 难度匹配表（AI 估计 + 载荷字符数 + 教师判断） | 同上 |
| `DISPUTE_LIST.md` | 诊断及检查策略争议项（含沿用的 v1 未决问题） | 同上 |
| `ANCHOR_CONSISTENCY_TABLE.md` | 评分锚点一致性表 | 同上 |
| `REVISION_REREVIEW_LOG.md` | AI 草案复核记录（非审定）+ 教师意见与复审登记（空白） | 教师/课题组 |
| `REVIEW_ITEMS_MASTER_BLANK.csv` | 全部核对项的机器可读空白清单 | 课题组统计用 |

## 使用流程

1. 把本目录整体（含 `../A01_*.md` 病例卡与 `../A01_assessment_payload_DRAFT.json`、`../A02_assessment_payload_DRAFT.json`）分别发给两位真实风湿科教师。
2. 两位教师**独立**填写，不互相讨论、不参考对方结论（每份表有独立性声明与利益冲突栏）。
3. 收回后由课题组录入 `REVIEW_ITEMS_MASTER_BLANK.csv`（另存为新文件，不覆盖空白模板），任一指标 ≤2 分或结论冲突的病例进入修订；冲突由第三位教师/教研室仲裁。
4. 修订按 `REVISION_REREVIEW_LOG.md` 登记并复审；医学内容修改必须创建新版本。
5. 独立考核病例（A01、A02）还须两位教师在系统内各自提交表单审核，管理员核验后才能发布；本材料包**不能**代替系统内审核，更**不能**由管理员或 AI 代签。

## 状态图例

| 状态 | 含义 |
| --- | --- |
| `PENDING_REAL_REVIEW` | 尚无真实教师审核（当前全部条目） |
| `REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED` | 真实人工审核尚未进行；审核教师完成后改为 `REAL_HUMAN_REVIEW_CONDUCTED` |

## 诚实声明

- 没有任何一份病例、量表、难度匹配或争议项在此材料包中被审定。
- AI 修订只代表技术/医学草案复核；不得在申报材料中表述为“已通过专家审核”。
