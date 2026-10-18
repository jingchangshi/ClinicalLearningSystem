# E3 病例与评分工具（草稿 + 待真实审核）

> 状态：**DRAFT_PENDING_REVIEW / `PENDING_REAL_REVIEW`**。全部为 Agent 起草的草案，**没有任何真实教师审核记录**。
> 详细状态以病例负责人的 `workpackages/A_cases/CASE_REVIEW_STATUS_DRAFT.md`（若已入库）与 `STATUS_A.md` 为准；
> 总口径见 `../../FINAL_DELIVERY/CASE_REVIEW_STATUS.md`。

## 一、六份病例

| 病例 | 用途 | 主题 | 状态 |
| --- | --- | --- | --- |
| CASE-T01 | 训练 | SLE | `PENDING_REAL_REVIEW` |
| CASE-T02 | 训练 | RA | `PENDING_REAL_REVIEW` |
| CASE-T03 | 训练 | ANCA 相关性血管炎 | `PENDING_REAL_REVIEW` |
| CASE-T04 | 训练 | 炎性肌病 | `PENDING_REAL_REVIEW` |
| CASE-A01 | 独立考核 | 未分化多关节炎 | `PENDING_REAL_REVIEW` |
| CASE-A02 | 独立考核 | **原因待查的干燥症状，疑似原发性干燥综合征（未确诊）** | `PENDING_REAL_REVIEW` |

旧 AOSD 版 A02 已被取代，仅存 Git 历史，**不是现行考核题本**。

## 二、评分工具与材料

| 内容 | 位置 | 状态 |
| --- | --- | --- |
| 六维量表 v0.1（权重 10/20/25/15/20/10，低/中/高锚点） | `workpackages/B_rubric/B01_rubric_v0.1.md` | 草案；**权重与锚点待两位教师确认**；不得覆盖平台形成性权重 20/20/20/15/15/10 |
| 病例审核表（空白） | `workpackages/A_cases/A03_teacher_review_form_BLANK.{md,csv}` | 姓名/日期/签字留空 |
| A01/A02 难度校准表（空白） | `workpackages/A_cases/A04_difficulty_calibration_BLANK.{md,csv}` | 待教师填写（新 A02 需重新校准） |
| 医学问题清单 | `workpackages/A_cases/MEDICAL_REVIEW_ISSUES_v1.md` | 旧 A02 部分已作废；新 A02 的争议项见病例负责人材料 |
| 评分者一致性脚本 | `scripts/grant/rubric_agreement.py` | 无真实评分时拒绝出数 |
| 模拟作答（盲评演练） | `workpackages/B_rubric/B02_sample_answers.*` | 合成；其中旧 A02 样例已不属于现行题本 |
| 教师审核材料包 | `../../TEACHER_REVIEW_PACKET.md` | 待真实教师填写 |

## 三、阻塞（只能由真实教师完成）

两位真实教师须完成：六例病例医学审核与签字、量表权重与锚点确认、A01/A02 难度与题本可比性审核、分歧阈值确认。
在收到带日期与签名的原始记录前，本目录任何内容都不得表述为「已审核」；AI 自查只能称「技术或医学草案复核」。
