# E3 病例与量表（草稿 + 待真实审核）

> 状态：**DRAFT_PENDING_REVIEW**。全部为 Agent 起草的草案，无任何真实教师审核记录。

| 内容 | 位置 | 状态 |
| --- | --- | --- |
| 6 例标准化病例（4 训练 + 2 考核） | `workpackages/A_cases/A01_*.md` | 草稿，`PENDING_REAL_REVIEW` |
| 病例卡自动校验 | `scripts/grant/check_case_cards.py` | 实测 88/88 PASS |
| 平台 schema 差异 | `workpackages/A_cases/A02_platform_schema_notes.md` | 已核对 |
| 空白教师审核表 | `workpackages/A_cases/A03_teacher_review_form_BLANK.{md,csv}` | 12 行，姓名/日期留空 |
| 六维量表 v0.1 | `workpackages/B_rubric/B01_rubric_v0.1.md` | 草稿 |
| 16 份模拟作答（盲评用） | `workpackages/B_rubric/B02_sample_answers.{md,csv}` | 合成，无分数列 |
| 评分导出/盲评流程 | `workpackages/B_rubric/B03_*.{md,csv}` | 空白模板 32 行 |
| 一致性分析脚本 | `scripts/grant/rubric_agreement.py` | 实跑；无真实评分时拒绝出数 |

## 阻塞

两位真实带教教师需完成：病例审核（A03）、量表权重与锚点确认（B01）、
以及可选的模拟作答独立盲评（B03）。在收到带日期与签名的原始记录前，
本目录任何内容都不得表述为"已审核"。
