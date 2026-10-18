# 六维评分量表审核表（独立考核研究量表）

> **状态：`PENDING_REAL_REVIEW`　review_origin：`REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED`**。研究权重 **10/20/25/15/20/10 为待教师确认的草案**；平台训练（形成性）权重 **20/20/20/15/15/10 保持不变，不在本表审核范围内，也不得被本表结论覆盖**。

## 1. 审核人

**REAL_TEACHER_1**（请审核教师本人填写；不得由他人代填）

| 项 | 内容 |
| --- | --- |
| 姓名 / 工号 | |
| 职称 / 单位 | |
| 是否参与过本病例起草或本批次学生带教（利益冲突） | ☐ 否　☐ 是，说明： |
| 声明：本人独立完成审核，未参考另一位教师的意见 | ☐ 已确认 |
| 审核日期（YYYY-MM-DD） | ____-__-__ |
| 签字 | |

**REAL_TEACHER_2**（请审核教师本人填写；不得由他人代填）

| 项 | 内容 |
| --- | --- |
| 姓名 / 工号 | |
| 职称 / 单位 | |
| 是否参与过本病例起草或本批次学生带教（利益冲突） | ☐ 否　☐ 是，说明： |
| 声明：本人独立完成审核，未参考另一位教师的意见 | ☐ 已确认 |
| 审核日期（YYYY-MM-DD） | ____-__-__ |
| 签字 | |

## 2. 权重确认

| 维度（key） | 研究权重（待确认） | 训练权重（不变） | 教师1：同意/修改为 | 教师2：同意/修改为 | 理由 | 状态 |
| --- | ---: | ---: | --- | --- | --- | --- |
| 医学知识（medical_knowledge） | 10（待教师确认） | 20 | | | | PENDING_REAL_REVIEW |
| 关键信息提取（key_information） | 20（待教师确认） | 20 | | | | PENDING_REAL_REVIEW |
| 鉴别诊断（differential_diagnosis） | 25（待教师确认） | 20 | | | | PENDING_REAL_REVIEW |
| 证据整合（evidence_integration） | 15（待教师确认） | 15 | | | | PENDING_REAL_REVIEW |
| 临床决策（clinical_decision） | 20（待教师确认） | 15 | | | | PENDING_REAL_REVIEW |
| 循证安全（evidence_based_medicine） | 10（待教师确认） | 10 | | | | PENDING_REAL_REVIEW |
| **合计** | **100** | **100** | | | | PENDING_REAL_REVIEW |

总分公式（系统实现）：总分 = Σ(维度分 × 权重) / 100，维度分 0–100。示例（纯算术演示，非任何学生数据）：各维度分均为 80 → 总分 80；医学知识 100、其余 0 → 总分 10。

## 3. 锚点审核（A01 与 A02 草案各一套；每维度 高/中/低 三档）

### 医学知识（medical_knowledge，研究权重 10，待确认）

| 档位 | CASE-A01 锚点（AI 草案） | CASE-A02 锚点（AI 草案） | 教师1 | 教师2 |
| --- | --- | --- | --- | --- |
| 高（80–100） | States what undifferentiated arthritis means, the entry condition and four scored items of the 2010 ACR/EULAR RA criteria, and that duration under 6 weeks scores 0. | Lists the five 2016 ACR/EULAR items with weights (3/3/1/1/1, threshold 4), the entry and exclusion conditions, notes that ANA/RF/IgG/ultrasound are not scored items, and states that classification criteria are not a clinical diagnosis. | | |
| 中（50–79） | Knows the criteria exist and some items but not the entry condition or the scoring ranges. | Knows the criteria exist and some items, but omits weights or exclusion conditions, or blurs classification and diagnosis. | | |
| 低（0–49） | Cannot describe the criteria, or equates a weakly positive RF/ANA with a diagnosis. | Cannot name the criteria, or treats dryness symptoms or a positive ANA/RF as diagnostic. | | |

### 关键信息提取（key_information，研究权重 20，待确认）

| 档位 | CASE-A01 锚点（AI 草案） | CASE-A02 锚点（AI 草案） | 教师1 | 教师2 |
| --- | --- | --- | --- | --- |
| 高（80–100） | At least 4 key positives (asymmetry, 15-20 min morning stiffness, 2 swollen small joints, 5-week course, anti-CCP negative, normal uric acid) and at least 3 key negatives, and explains why anti-CCP negativity and a duration under 6 weeks matter for scoring and prognosis. | At least 4 key positives (8-month daily course, no improvement 3 months after stopping the antihistamine, abnormal ocular staining, Schirmer 3/4 mm, new caries, hand joint aches without synovitis) and at least 4 key negatives (no radiation, HCV/HIV negative, no gland swelling, no purpura, no proteinuria), and explains what the 3-month washout and the negative anti-SSA mean. | | |
| 中（50–79） | Extracts most positives but omits negatives or does not interpret them. | Extracts most positives but few negatives, or does not interpret the washout or the negative anti-SSA. | | |
| 低（0–49） | Restates the case without selecting key points, or misses asymmetry and duration. | Restates the case without selecting key points, or misses the medication history entirely. | | |

### 鉴别诊断（differential_diagnosis，研究权重 25，待确认）

| 档位 | CASE-A01 锚点（AI 草案） | CASE-A02 锚点（AI 草案） | 教师1 | 教师2 |
| --- | --- | --- | --- | --- |
| 高（80–100） | At least 6 differentials, each with case-specific supporting and opposing evidence and the evidence needed to exclude it. | At least 6 differentials covering medication effect, other dry-eye types, metabolic/endocrine causes, infection or infiltrative disease, secondary Sjogren (with SLE/RA), and lymphoproliferative disease, each with case-specific supporting and opposing evidence and the test needed to exclude it. | | |
| 中（50–79） | Several correct differentials but generic reasoning or missing exclusion evidence. | Several correctly ranked differentials but evidence is generic, or the exclusion tests are missing. | | |
| 低（0–49） | A bare list of disease names, or treats 'undifferentiated' as 'no need to differentiate'. | Names primary Sjogren only, or a bare list of diagnoses without case-level evidence. | | |

### 证据整合（evidence_integration，研究权重 15，待确认）

| 档位 | CASE-A01 锚点（AI 草案） | CASE-A02 锚点（AI 草案） | 教师1 | 教师2 |
| --- | --- | --- | --- | --- |
| 高（80–100） | Shows the scoring 2 + 2 + 1 + 0 = 5, below 6, so RA classification is not met, and weighs asymmetry and negative anti-CCP as further lowering the likelihood of RA. | Scores the known results (Schirmer 1 + ocular staining 1 + anti-SSA 0 = 2, below 4), marks salivary flow and labial biopsy as not assessed, explains that non-invasive testing can reach at most 3 points so biopsy or repeat serology is needed, and that a negative anti-SSA does not exclude disease. | | |
| 中（50–79） | Concludes criteria are not met but cannot show the item-by-item arithmetic. | Recognises the score is below threshold but cannot show the item-by-item arithmetic or the unassessed items. | | |
| 低（0–49） | Diagnoses RA or SLE from a weakly positive RF or ANA 1:80, or does not weigh evidence. | Concludes a definite diagnosis from symptoms or ANA/RF, or excludes disease because anti-SSA is negative, or treats the unperformed biopsy as a result. | | |

### 临床决策（clinical_decision，研究权重 20，待确认）

| 档位 | CASE-A01 锚点（AI 草案） | CASE-A02 锚点（AI 草案） | 教师1 | 教师2 |
| --- | --- | --- | --- | --- |
| 高（80–100） | Gives a provisional diagnosis, a 1-3 month follow-up with named re-assessment items, and explicit triggers for reclassification or starting a DMARD. | Prioritises salivary flow then labial gland biopsy (indication, consent, timing before any steroid), gives topical and symptomatic management, does not start systemic immunosuppression, and names a follow-up interval with escalation triggers. | | |
| 中（50–79） | Provisional diagnosis with a vague follow-up. | Reasonable tests and symptomatic care but no priority order, no follow-up interval, or vague about immunosuppression. | | |
| 低（0–49） | No follow-up plan, or starts prolonged glucocorticoid without a diagnosis. | Starts steroids or immunosuppressants without indication, orders an undirected battery of tests, or gives no plan. | | |

### 循证安全（evidence_based_medicine，研究权重 10，待确认）

| 档位 | CASE-A01 锚点（AI 草案） | CASE-A02 锚点（AI 草案） | 教师1 | 教师2 |
| --- | --- | --- | --- | --- |
| 高（80–100） | Cites the 2010 ACR/EULAR criteria and early arthritis recommendations, avoids prolonged glucocorticoid while the diagnosis is unclear, and writes pre-treatment hepatitis B and tuberculosis screening. | Cites the 2016 ACR/EULAR criteria and the EULAR 2020 management recommendations, states biopsy risks, avoids unindicated immunosuppression, and names lymphoma-risk markers to monitor (persistent gland swelling, purpura, low C4, cryoglobulin, M protein). | | |
| 中（50–79） | Mentions guidelines in general terms or covers only some safety points. | Mentions guidelines in general terms or covers only some safety points. | | |
| 低（0–49） | No evidence basis or unsafe treatment advice. | No evidence basis, or recommends unsafe or unindicated treatment. | | |

## 4. 评分操作规则审核

| ID | 事项 | 教师1 | 教师2 | 状态 |
| --- | --- | --- | --- | --- |
| R-01 | 三档分段（80–100 / 50–79 / 0–49）是否合适；档内如何细分（锚点只给档位，不给逐分规则） | | | PENDING_REAL_REVIEW |
| R-02 | 两位评分者总分差/维度差的**裁决阈值**（系统可配置；阈值须在正式研究前由教师确认，AI 不预设）：建议值：______ | | | PENDING_REAL_REVIEW |
| R-03 | “万能不确定”答案（只写不能确诊并随访）的上限分数规则 | | | PENDING_REAL_REVIEW |
| R-04 | 答案遗漏“必须项”时是否有封顶规则（例如出现无指征使用免疫抑制则循证安全≤49） | | | PENDING_REAL_REVIEW |
| R-05 | 是否同意各维度由评分者独立打分、不得看到对方分数、不得看到批次/组别/时点 | | | PENDING_REAL_REVIEW |
| R-06 | 评分者校准：正式评分前是否需要用 B 工作包样例答案做一次校准会（已用于培训的样例不得出自 A01/A02 的真实学生答卷） | | | PENDING_REAL_REVIEW |

## 5. 声明

- 本表不含任何真实教师姓名、签名或日期；权重与锚点在两位教师签字前均为草案（`PENDING_REAL_REVIEW`）。
- 独立考核应从**已批准的 rubric 版本**读取权重与锚点；批准动作只能由教师在系统内或经此表签字后由管理员核验完成。
