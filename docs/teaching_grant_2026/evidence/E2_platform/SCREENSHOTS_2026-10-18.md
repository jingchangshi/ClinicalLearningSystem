# E2 截图证据：独立考核、双教师盲评、研究管理（2026-10-18）

> **这些截图对应实际运行的版本，不是设计稿。**
>
> - 运行提交：**`375e197`**（`375e19748baf499908f2b5b78217417762bababa`，分支 `feat/clinpath-final-2026`）
> - 环境：隔离 worktree `/home/jcshi/workspace/clinpath-final`；后端 `127.0.0.1:8400`；前端 `127.0.0.1:8401`；
>   构建目录 `frontend/.next-accept`（构建期烘焙 `INTERNAL_API_BASE_URL=http://127.0.0.1:8400/api`）
> - 数据库：`/tmp/clinpath-e2e/accept.db`（一次性，`alembic head = 20261018_09`）
> - 采集时间（UTC）：**2026-10-18 16:30:02—16:30:24**
> - 采集方式：`frontend/tests/e2e/evidence-screenshots.spec.ts`（Playwright，1440×900，`fullPage`）
> - 数据性质：**`SYNTHETIC / SIMULATED_NOT_HUMAN`**，`data_origin=pilot_test`；
>   账号为 `TEST 测试教师A/B（非真实教师）`、`TEST测试学生NN`。**不是真实教师审核，不是真实学生数据，不是教学效果证据。**
> - 模型密钥：刻意留空 → 训练评分走 `rule_fallback`，页面必须如实标注

## 截图清单

| 文件 | 展示内容 | 该截图能证明什么 | 不能证明什么 |
| --- | --- | --- | --- |
| `01_study_admin_sittings_overview.png` | 研究管理员「考试与评分总览」：考试总数、已提交、过期未交、完成双评、进入裁决、已锁定成绩 | 管理员视图存在且统计来自真实 sitting 记录 | 不代表任何真实考核结果 |
| `02_study_admin_cohorts_7batches_x7.png` | 「批次与入组」：7 个 `TEST-Cxx` 批次，各显示 `已入组 7 / 7` | 7 批 × 7 人的批次结构由产品记录产生 | 批次是合成批次，不是真实轮转日期 |
| `03_study_admin_frozen_form_order_and_cluster_allocation.png` | 「分配冻结」：①题本顺序已冻结（哈希 `821bc1060883`）、②整批分配已登记（`3 ClinPath + 4 CBL`）、③不可变分配记录表、④批次-学生-组别-题本顺序全表 | 先冻结题本顺序、再抽整批分配；7 批整批同臂；每批 X/Y 约 4/3 | 随机种子由服务端生成，未在页面显示（见 E4 记录 §6.1 的 API 缺口） |
| `04_study_admin_bulk_schedule_98_sittings.png` | 「批量排考（7 批 × 7 人 × T0/T1）」及每批窗口 | 排考入口与「整批全有或全无」语义 | — |
| `05_study_admin_research_export_working_dataset.png` | 「数据集与一致性」：工作数据集、评分者一致性、冻结版本 | 受控导出入口存在，工作数据集标注 `WORKING_NOT_FROZEN` | 未冻结、不是最终研究数据集 |
| `06_study_admin_audit_log.png` | 「审计日志」：谁在何时做了什么 | 管理操作留痕（只记录 id 与元数据） | — |
| `07_teacher_form_review_queue.png` | 教师「待我审核」题本队列 | 只有被指派的教师能看到待审题本 | 审核人是测试账号，不是真实医学审核 |
| `08_teacher_form_authoring_panel.png` | 题本创建面板（五阶段、参考答案、六维权重与锚点） | 教师/管理员可建草案并进入审核流程 | 草案仍需两位真实教师审核 |
| `09_blinded_rater_queue_no_identity.png` | 评分者盲评队列：`第 N 份匿名答卷` + 盲评编码前 8 位 + `待评分/已评分并锁定`，页面明示「不含姓名、学号、组别、批次与时点」 | 盲评队列**不展示**学生身份、组别、批次、时点 | 若评分者本人承担该批教学，系统另标 `blinding_risk`，不等于真正盲法 |
| `10_blinded_rater_six_dimension_form_no_identity.png` | 盲评六维评分表（医学知识/关键信息提取/鉴别诊断/证据整合/临床决策/循证安全） | 六维 0–100 独立评分界面；评分者互不可见 | 权重仍待真实教师确认 |
| `11_admin_form_review_status_and_publish_gate.png` | 管理员「题本审核状态与发布」：审核记录、审核人指派、发布按钮 | 发布前必须显示两位教师的审核记录；管理员不能代签 | 审核人是测试账号 |
| `12_adjudication_queue_flagged_disagreement.png` | 「分歧裁决」队列：`待裁决 0`，队列中 1 份答卷标记 `已裁决` | 超阈值分歧确实进入独立裁决队列，且裁决后状态为「已裁决」（截图在功能套件之后采集，故该份已裁决） | 截图中不含两名评分者的原始分数明细（该明细在裁决详情页，未单独截图） |
| `13_student_assessment_list.png` | 学生「我的独立考核」 | 学生只看到自己的考核与时点 | — |
| `14_student_submitted_confirmation_no_score.png` | 学生提交成功页：**只显示「答卷已提交」与提交时间，明确声明不显示正确答案、参考诊断、任何评分** | 提交后**无**答案、无自动评分、无形成性反馈 | — |
| `15a_student_exam_instructions.png` | 考试说明页（「不提供 AI 追问」） | 考核与训练分离的说明对学生可见 | — |
| `15b_student_exam_stage_in_progress_draft_saved.png` | 阶段作答中，草稿已保存到服务器 | 草稿服务器保存（断网/刷新恢复的基础） | 真实断网未在本轮验证 |

## 与本文件相关的其他证据

- 完整运行记录（命令、输出、通过/失败、未执行项）：`../E4_validation/RUN_RECORD_2026-10-18.md`
- 7 批不变量实测：同上 §6
- 生产隔离与 2026-10-18 误触事件：`INCIDENT_2026-10-18_production_touch.md`、`ENVIRONMENT_ISOLATION.md`

## 仍需外部确认

| 项 | 说明 |
| --- | --- |
| 截图使用授权 | 院系/单位确认可在申报材料中使用系统截图 |
| 真实教师演示反馈 | 需真实教师观摩后填写；未观摩前不得写「已完成教师观察」 |
