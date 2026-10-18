# R8.3 数据库迁移验收（MIGRATION_ACCEPTANCE）

> 状态：**技术验收通过（存在 1 项历史遗留差异，见第 5 节）**
> 验收对象：分支 `feat/clinpath-final-2026`，后端与迁移代码提交 `2fd5558579e8d557d86bef631542688beb3383ee`
> （运行时分支 tip 为 `5214be523d60c023ea2544399877d8fe86545e69`，该提交只改前端，未触及 `backend/`）
> 执行时间：2026-10-18 15:23 UTC
> 环境：Linux 6.8.0-1049-oracle aarch64；uv 0.11.16；Python 3.11.15；SQLite（Python 标准库 `sqlite3`）
> 结论适用范围：本文件只证明**数据库迁移**。前端、浏览器、部署不在本文件范围。
> **没有对任何生产数据库执行迁移。** 本机没有经过授权的生产库副本，因此 R8.3 中「生产库副本」一项
> **未执行**，下文使用的是一个**开发数据库的只读副本**（来源见第 3 节），并如实标注。

## 0. 验收结论

| 检查项 | 结果 | 证据 |
| --- | --- | --- |
| 全新隔离库：`upgrade head` | 通过 | 附录 A 步骤 4 |
| 降至考核迁移之前的 revision（`20261018_07`） | 通过（只移除 assessment/study/research 表） | 附录 A 步骤 5 |
| 再 `upgrade head` | 通过 | 附录 A 步骤 6 |
| 表结构检查（迁移结果 vs `create_all` 全新安装） | 通过：52 个对象，规范化后 0 处差异 | 附录 A 步骤 7 |
| 历史训练数据行数与内容不变 | 通过：14 张训练表逐行字节一致（升级 / 降级 / 再升级三次比较） | 附录 A |
| 训练成绩与画像不变性 | 通过：`scores`、`competency_profiles`、`learning_evidence_events` 内容未变 | 附录 A、B |
| 真实（开发库）数据副本上的同循环 | 通过：25 张表逐行一致；07 新增的两列不改变任何历史行（该表 0 行） | 附录 B |
| 生产库 / 生产库副本迁移 | **未执行**（本机无授权副本） | 第 6 节 |

**发现并已修复的问题**：`assessment_sittings.created_at` 在「降级→再升级」后变为可空（ORM 声明为必填）。
修复提交 `d117899`，回归测试 `backend/tests/test_migration_down_up_cycle.py`（移除修复后该测试确实失败）。

## 1. 迁移链事实（执行前核实）

```
20260915_01 -> 02 -> 03 -> 04 -> 05 -> 06 -> 20261018_07 -> 20261018_08 -> 20261018_09 (head)
```

需要如实记录一个迁移链的历史约定：**根 revision `20260915_01` 在空库上调用
`Base.metadata.create_all(bind)`，按「当前 ORM 元数据」建表**（已有数据的库只逐列补加）。因此：

- 一个由 `alembic upgrade head` 从零建起的数据库，在 `20261018_07` 处**已经**存在 `assessment_*` 表，
  且是当前（加固后）的形状；`20261018_08/09` 对这类库是幂等的空操作。
- `20261018_08/09` 真正执行 DDL 的路径是：**已经处于旧形状的数据库**（例如本仓库另一个工作目录中的开发库，
  revision `20260915_06`，完全没有考核表）以及**降级之后的再升级**。
- 本文件的两次验收分别覆盖这两条路径：第 2 节（隔离库循环 → 走 08/09 的真实重建分支）与第 3 节（真实旧库副本）。

## 2. 隔离数据库上的完整循环

隔离库位于临时目录（`mktemp -d`），`DATABASE_URL` 每一步都指向它；**没有读写任何其他数据库**。
完整命令与输出见**附录 A**（`scripts/verify_migration_cycle.sh` 的原样输出）。摘要：

```text
步骤 4  upgrade head：20261018_09 (head)
        compare 升级前 -> 升级后：training tables 14/14 byte-identical；tables identical: 41
步骤 5  downgrade 20261018_07：DROPPED 16 张 assessment_*/study_*/research_* 表
        training tables 14/14 byte-identical
步骤 6  upgrade head：training tables 14/14 byte-identical
        compare 首次 head -> 再次 head：tables identical: 41
步骤 7  迁移结果 vs 全新 create_all 安装：objects 52 -> 52；differing: 0
        schema equivalent (modulo clause order, quoting and server defaults)
```

## 3. 真实开发数据库副本（只读复制）

来源：`/home/jcshi/workspace/clinical_learning_system/backend/clinical_learning.db`
——这是**另一个工作目录中的开发数据库**（revision `20260915_06`，不含任何考核表），
**不是生产库**；生产运行版本为 `1d4ef48`（见 `EVIDENCE_INDEX.md` 生成基线），其数据库不在本机。

复制方式：以 `file:...?mode=ro` 只读打开源库，用 `sqlite3.Connection.backup` 写入临时副本；
源文件未做任何写入（复制后 `mtime` 仍为 2026-09-15 16:27）。

副本中的真实数据规模（迁移前）：

```text
ai_invocations 816  case_sessions 25  student_answers 96  scores 19  tutor_turns 43
learning_evidence_events 30  learning_recommendations 23  generated_case_drafts 19
students 4  teachers 3  users 8  cases 10  competency_profiles 4
```

完整命令与输出见**附录 B**。摘要：

```text
rev 20260915_06 -> 20261018_07：仅 teacher_score_reviews 增加 baseline_score / baseline_source 两列
                               （20261018_07 的设计目的；该表 0 行，因此不改变任何历史行）
rev 20261018_07 -> head      ：training tables 14/14 byte-identical，新增 16 张考核/研究表
head -> 20261018_07 -> head  ：07 状态与 head 状态两次比较均逐行字节一致
迁移后 head 与全新 create_all 对比：52 个对象；7 处差异全部是历史遗留列定义（见第 5.3 节）
```

## 4. 表结构检查

- `assessment_sittings`：28 列（含 `data_origin`、`attempt_no`、`form_order`、`blinding_risk`、
  `allocation_id`、`created_at` 等）；`created_at` 为 `NOT NULL`（修复后）。
- 三个考核索引在循环前后完全一致：
  `ix_assess_events_sitting`、`uq_assess_live_rater`（部分唯一，`voided_at IS NULL`）、
  `uq_assess_live_student_timepoint`（部分唯一，`status != 'voided'`）。
- `uq_assess_live_student_timepoint` / `uq_assess_live_rater` 是「一名学生一个时点只能有一份有效答卷」
  和「同一评分者只能提交一次」的数据库级保证；循环后仍然存在（附录 A 步骤 6 的对象比较覆盖索引）。
- SQLite 批量重建会改变 **DDL 文本**（表名加引号、外键约束命名、子句顺序、`server_default` 显式化），
  但列集合与顺序、`NOT NULL`、`PRIMARY KEY`、`UNIQUE`、外键目标、索引均相同。
  `scripts/compare_schema_json.py` 只把这些无语义差异规范化掉，真实的丢失会被报出。

## 5. 发现与处理

### 5.1 已修复：`assessment_sittings.created_at` 在降级→再升级后变为可空

- 现象：`20261018_09` 因为 SQLite 不能对已有行的表 `ADD COLUMN ... NOT NULL`，先以可空方式加入
  `created_at` 并回填，但没有再恢复 `NOT NULL`。于是：
  - 全新 `create_all` / 首次升级：`created_at DATETIME NOT NULL`
  - 降级到 `20261018_07` 再升级：`created_at DATETIME`（弱于 ORM 声明）
- 处理：回填之后立即用一次 batch 重建把该列恢复为 `NOT NULL`（提交 `d117899`）。
- 回归：`backend/tests/test_migration_down_up_cycle.py` 在临时库上真实执行
  `upgrade 20261018_07 → head → downgrade 20261018_07 → head`，要求训练数据逐字节不变、
  考核表随迁移出现/消失、再次升级后的结构与首次升级及 `create_all` 等价，并显式断言
  `created_at DATETIME NOT NULL`。**临时移除修复后该测试确实失败**（报错行即该断言）。

### 5.2 需要知悉：根 revision 在空库上 `create_all` 的约定

如第 1 节所述，`20261018_07` 处已有考核表。这意味着：

- 对「从零升级」的库，08/09 的加列分支不会执行；真正执行它们的只有「旧库」和「降级后再升级」。
- 因此本验收必须同时覆盖两条路径，第 2、3 节分别覆盖。
- 这不是本轮引入的问题，也不阻塞交付；但它决定了「某个 revision 的历史形状」不能仅凭 revision 号推断。

### 5.3 未修复的历史遗留差异（与本次考核迁移无关，需申请人/后续决定）

真实开发库副本升级到 head 后，与全新 `create_all` 相比有 7 张**训练域**表存在定义差异：

| 表 | 差异 | 影响 |
| --- | --- | --- |
| `ai_enrichments`、`ai_invocations`、`scores`、`student_answers`、`tutor_turns`、`competency_profiles` | 旧库保留 `DEFAULT (0)` / `DEFAULT CURRENT_TIMESTAMP` / `DEFAULT 75` 等 `server_default`，新模型只声明 Python 端默认值 | 无语义损失（列、约束、索引一致） |
| `teacher_score_reviews` | 旧库 `reviewer_user_id` 可空（`20260915_02` 为兼容历史行而如此声明），当前 ORM 声明 `nullable=False` | 数据库不强制该列非空；应用层（`app/routes/teacher.py`）始终写入评审人 |

本轮**没有**修改这些历史迁移：修改会让已有历史行（该列可能为 NULL 的旧评审）无法满足约束，
超出本次考核迁移的验收范围。建议后续单独评估（例如新增一条迁移，先回填再收紧，或修正模型声明）。

## 6. 未执行与限制

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 生产数据库迁移 | **未执行** | 本轮不合并、不部署（R8.4）；生产运行 `1d4ef48` |
| 生产数据库**副本**迁移 | **未执行** | 本机无经授权的生产库副本；第 3 节使用的是开发库副本，不得表述为生产验收 |
| 降级后再降级到根 revision | 未执行 | 08 的 downgrade 会直接删除考核表；无数据的新库上可行，但对有考核数据的库无意义（`20261018_09` 的 downgrade 会在存在 voided 记录/题本多版本时拒绝） |
| 前端 / 浏览器 / 部署验收 | 不在本文件范围 | 见 E2 其他条目 |

另：降级到 `20261018_07` 会**删除** `assessment_*` / `study_*` / `research_*` 表（这是回到该 revision 的定义）。
`20261018_09` 的 downgrade 在存在 voided 答卷/评审或题本版本 >1 时会**拒绝**执行，提示先导出处理。
任何降级前都必须按 AGENTS.md 第 5 条先生成带时间戳的 SQLite 备份。

## 7. 复现方法

```bash
# 隔离库上的完整 ups/down/up 循环（自建临时库，不触碰任何已有数据库）
cd /home/jcshi/workspace/clinpath-final
./scripts/verify_migration_cycle.sh

# 同一循环的自动化回归（含 created_at 回归断言与 create_all 等价性）
cd backend
uv run --python 3.11 --with-requirements requirements.txt \
    pytest -q tests/test_migration_down_up_cycle.py
```

辅助工具：

- `backend/tools/migration_acceptance.py`：`seed` / `dump` / `tables` / `schema` / `compare`；
  `dump` 只用标准库 `sqlite3`，因此可在任意 revision 上读；`compare` 对训练表逐行比对，任一内容变化即非零退出。
- `scripts/compare_schema_json.py`：比较两份结构快照，只报告真实的结构变化。

## 附录 A：隔离数据库循环（`scripts/verify_migration_cycle.sh` 原样输出）

```text

=== isolated database: /tmp/clinpath-migration-acceptance.ISl5kB/acceptance.db (temporary; no other database is read or written) ===

=== 1. upgrade to 20261018_07 (before the assessment revisions) ===

$ uv run --python 3.11 --with-requirements requirements.txt alembic upgrade 20261018_07

$ uv run --python 3.11 --with-requirements requirements.txt alembic current
20261018_07

=== 2. seed the pre-existing training rows ===

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py seed --db /tmp/clinpath-migration-acceptance.ISl5kB/acceptance.db
seeded the training fixture rows

=== 3. dump the training data BEFORE the assessment migrations ===

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py dump --db /tmp/clinpath-migration-acceptance.ISl5kB/acceptance.db --out /tmp/clinpath-migration-acceptance.ISl5kB/dump_pre_assessment.json
dumped 41 tables (revision 20261018_07) to /tmp/clinpath-migration-acceptance.ISl5kB/dump_pre_assessment.json

=== 4. upgrade head ===

$ uv run --python 3.11 --with-requirements requirements.txt alembic upgrade head

$ uv run --python 3.11 --with-requirements requirements.txt alembic current
20261018_09 (head)

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py schema --db /tmp/clinpath-migration-acceptance.ISl5kB/acceptance.db --out /tmp/clinpath-migration-acceptance.ISl5kB/schema_after_upgrade.json
wrote 52 schema objects to /tmp/clinpath-migration-acceptance.ISl5kB/schema_after_upgrade.json

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py dump --db /tmp/clinpath-migration-acceptance.ISl5kB/acceptance.db --out /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_upgrade.json
dumped 41 tables (revision 20261018_09) to /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_upgrade.json

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py compare --before /tmp/clinpath-migration-acceptance.ISl5kB/dump_pre_assessment.json --after /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_upgrade.json
same    ai_enrichments (0 rows)
same    ai_invocations (1 rows)
same    ai_messages (0 rows)
same    assessment_adjudications (0 rows)
same    assessment_answer_revisions (0 rows)
same    assessment_answers (0 rows)
same    assessment_audit_log (0 rows)
same    assessment_dataset_locks (0 rows)
same    assessment_events (0 rows)
same    assessment_final_scores (0 rows)
same    assessment_form_reviewers (0 rows)
same    assessment_form_reviews (0 rows)
same    assessment_forms (0 rows)
same    assessment_reviews (0 rows)
same    assessment_sittings (0 rows)
same    case_sessions (1 rows)
same    cases (1 rows)
same    clinical_skills (0 rows)
same    competency_profiles (1 rows)
same    generated_case_drafts (0 rows)
same    guideline_documents (0 rows)
same    guideline_learning_sessions (0 rows)
same    knowledge_progress (0 rows)
same    knowledge_units (0 rows)
same    learning_evidence_events (1 rows)
same    learning_recommendations (1 rows)
same    research_codes (0 rows)
same    scores (1 rows)
same    skill_sessions (0 rows)
same    sp_cases (0 rows)
same    sp_sessions (0 rows)
same    student_answers (1 rows)
same    students (1 rows)
same    study_allocations (0 rows)
same    study_cohorts (0 rows)
same    study_enrollments (0 rows)
same    teacher_score_reviews (1 rows)
same    teachers (1 rows)
same    teaching_interventions (0 rows)
same    tutor_turns (1 rows)
same    users (2 rows)

training tables seeded and compared: 14; byte-identical: 14
tables identical: 41, revision 20261018_07 -> 20261018_09

=== 5. downgrade to 20261018_07 ===

$ uv run --python 3.11 --with-requirements requirements.txt alembic downgrade 20261018_07

$ uv run --python 3.11 --with-requirements requirements.txt alembic current
20261018_07

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py tables --db /tmp/clinpath-migration-acceptance.ISl5kB/acceptance.db
ai_enrichments	rows=0	columns=11
ai_invocations	rows=1	columns=15
ai_messages	rows=0	columns=6
case_sessions	rows=1	columns=6
cases	rows=1	columns=14
clinical_skills	rows=0	columns=10
competency_profiles	rows=1	columns=13
generated_case_drafts	rows=0	columns=5
guideline_documents	rows=0	columns=10
guideline_learning_sessions	rows=0	columns=9
knowledge_progress	rows=0	columns=7
knowledge_units	rows=0	columns=10
learning_evidence_events	rows=1	columns=12
learning_recommendations	rows=1	columns=6
scores	rows=1	columns=25
skill_sessions	rows=0	columns=9
sp_cases	rows=0	columns=11
sp_sessions	rows=0	columns=14
student_answers	rows=1	columns=6
students	rows=1	columns=5
teacher_score_reviews	rows=1	columns=12
teachers	rows=1	columns=5
teaching_interventions	rows=0	columns=7
tutor_turns	rows=1	columns=8
users	rows=2	columns=7

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py dump --db /tmp/clinpath-migration-acceptance.ISl5kB/acceptance.db --out /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_downgrade.json
dumped 25 tables (revision 20261018_07) to /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_downgrade.json

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py compare --before /tmp/clinpath-migration-acceptance.ISl5kB/dump_pre_assessment.json --after /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_downgrade.json
same    ai_enrichments (0 rows)
same    ai_invocations (1 rows)
same    ai_messages (0 rows)
DROPPED assessment_adjudications (0 rows)
DROPPED assessment_answer_revisions (0 rows)
DROPPED assessment_answers (0 rows)
DROPPED assessment_audit_log (0 rows)
DROPPED assessment_dataset_locks (0 rows)
DROPPED assessment_events (0 rows)
DROPPED assessment_final_scores (0 rows)
DROPPED assessment_form_reviewers (0 rows)
DROPPED assessment_form_reviews (0 rows)
DROPPED assessment_forms (0 rows)
DROPPED assessment_reviews (0 rows)
DROPPED assessment_sittings (0 rows)
same    case_sessions (1 rows)
same    cases (1 rows)
same    clinical_skills (0 rows)
same    competency_profiles (1 rows)
same    generated_case_drafts (0 rows)
same    guideline_documents (0 rows)
same    guideline_learning_sessions (0 rows)
same    knowledge_progress (0 rows)
same    knowledge_units (0 rows)
same    learning_evidence_events (1 rows)
same    learning_recommendations (1 rows)
DROPPED research_codes (0 rows)
same    scores (1 rows)
same    skill_sessions (0 rows)
same    sp_cases (0 rows)
same    sp_sessions (0 rows)
same    student_answers (1 rows)
same    students (1 rows)
DROPPED study_allocations (0 rows)
DROPPED study_cohorts (0 rows)
DROPPED study_enrollments (0 rows)
same    teacher_score_reviews (1 rows)
same    teachers (1 rows)
same    teaching_interventions (0 rows)
same    tutor_turns (1 rows)
same    users (2 rows)

training tables seeded and compared: 14; byte-identical: 14
tables identical: 25, revision 20261018_07 -> 20261018_07

=== 6. upgrade head again ===

$ uv run --python 3.11 --with-requirements requirements.txt alembic upgrade head

$ uv run --python 3.11 --with-requirements requirements.txt alembic current
20261018_09 (head)

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py schema --db /tmp/clinpath-migration-acceptance.ISl5kB/acceptance.db --out /tmp/clinpath-migration-acceptance.ISl5kB/schema_after_reupgrade.json
wrote 52 schema objects to /tmp/clinpath-migration-acceptance.ISl5kB/schema_after_reupgrade.json

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py dump --db /tmp/clinpath-migration-acceptance.ISl5kB/acceptance.db --out /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_reupgrade.json
dumped 41 tables (revision 20261018_09) to /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_reupgrade.json

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py compare --before /tmp/clinpath-migration-acceptance.ISl5kB/dump_pre_assessment.json --after /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_reupgrade.json
same    ai_enrichments (0 rows)
same    ai_invocations (1 rows)
same    ai_messages (0 rows)
same    assessment_adjudications (0 rows)
same    assessment_answer_revisions (0 rows)
same    assessment_answers (0 rows)
same    assessment_audit_log (0 rows)
same    assessment_dataset_locks (0 rows)
same    assessment_events (0 rows)
same    assessment_final_scores (0 rows)
same    assessment_form_reviewers (0 rows)
same    assessment_form_reviews (0 rows)
same    assessment_forms (0 rows)
same    assessment_reviews (0 rows)
same    assessment_sittings (0 rows)
same    case_sessions (1 rows)
same    cases (1 rows)
same    clinical_skills (0 rows)
same    competency_profiles (1 rows)
same    generated_case_drafts (0 rows)
same    guideline_documents (0 rows)
same    guideline_learning_sessions (0 rows)
same    knowledge_progress (0 rows)
same    knowledge_units (0 rows)
same    learning_evidence_events (1 rows)
same    learning_recommendations (1 rows)
same    research_codes (0 rows)
same    scores (1 rows)
same    skill_sessions (0 rows)
same    sp_cases (0 rows)
same    sp_sessions (0 rows)
same    student_answers (1 rows)
same    students (1 rows)
same    study_allocations (0 rows)
same    study_cohorts (0 rows)
same    study_enrollments (0 rows)
same    teacher_score_reviews (1 rows)
same    teachers (1 rows)
same    teaching_interventions (0 rows)
same    tutor_turns (1 rows)
same    users (2 rows)

training tables seeded and compared: 14; byte-identical: 14
tables identical: 41, revision 20261018_07 -> 20261018_09

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py compare --before /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_upgrade.json --after /tmp/clinpath-migration-acceptance.ISl5kB/dump_after_reupgrade.json
same    ai_enrichments (0 rows)
same    ai_invocations (1 rows)
same    ai_messages (0 rows)
same    assessment_adjudications (0 rows)
same    assessment_answer_revisions (0 rows)
same    assessment_answers (0 rows)
same    assessment_audit_log (0 rows)
same    assessment_dataset_locks (0 rows)
same    assessment_events (0 rows)
same    assessment_final_scores (0 rows)
same    assessment_form_reviewers (0 rows)
same    assessment_form_reviews (0 rows)
same    assessment_forms (0 rows)
same    assessment_reviews (0 rows)
same    assessment_sittings (0 rows)
same    case_sessions (1 rows)
same    cases (1 rows)
same    clinical_skills (0 rows)
same    competency_profiles (1 rows)
same    generated_case_drafts (0 rows)
same    guideline_documents (0 rows)
same    guideline_learning_sessions (0 rows)
same    knowledge_progress (0 rows)
same    knowledge_units (0 rows)
same    learning_evidence_events (1 rows)
same    learning_recommendations (1 rows)
same    research_codes (0 rows)
same    scores (1 rows)
same    skill_sessions (0 rows)
same    sp_cases (0 rows)
same    sp_sessions (0 rows)
same    student_answers (1 rows)
same    students (1 rows)
same    study_allocations (0 rows)
same    study_cohorts (0 rows)
same    study_enrollments (0 rows)
same    teacher_score_reviews (1 rows)
same    teachers (1 rows)
same    teaching_interventions (0 rows)
same    tutor_turns (1 rows)
same    users (2 rows)

training tables seeded and compared: 14; byte-identical: 14
tables identical: 41, revision 20261018_09 -> 20261018_09

=== 7. migrated schema vs a fresh create_all install of the same models ===

$ env DATABASE_URL=sqlite:////tmp/clinpath-migration-acceptance.ISl5kB/fresh_create_all.db uv run --python 3.11 --with-requirements requirements.txt python -c from app.database import Base, engine; import app.models, app.assessment_models; Base.metadata.create_all(engine)

$ uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py schema --db /tmp/clinpath-migration-acceptance.ISl5kB/fresh_create_all.db --out /tmp/clinpath-migration-acceptance.ISl5kB/schema_fresh_install.json
wrote 52 schema objects to /tmp/clinpath-migration-acceptance.ISl5kB/schema_fresh_install.json

$ python3 /home/jcshi/workspace/clinpath-final/scripts/compare_schema_json.py /tmp/clinpath-migration-acceptance.ISl5kB/schema_after_reupgrade.json /tmp/clinpath-migration-acceptance.ISl5kB/schema_fresh_install.json
same    index:ix_ai_enrichments_kind
same    index:ix_ai_invocations_task_type
same    index:ix_assess_events_sitting
same    index:ix_case_sessions_id
same    index:ix_cases_id
same    index:ix_students_id
same    index:ix_teachers_id
same    index:ix_users_id
same    index:ix_users_username
same    index:uq_assess_live_rater
same    index:uq_assess_live_student_timepoint
same    table:ai_enrichments
same    table:ai_invocations
same    table:ai_messages
same    table:assessment_adjudications
same    table:assessment_answer_revisions
same    table:assessment_answers
same    table:assessment_audit_log
same    table:assessment_dataset_locks
same    table:assessment_events
same    table:assessment_final_scores
same    table:assessment_form_reviewers
same    table:assessment_form_reviews
same    table:assessment_forms
same    table:assessment_reviews
same    table:assessment_sittings
same    table:case_sessions
same    table:cases
same    table:clinical_skills
same    table:competency_profiles
same    table:generated_case_drafts
same    table:guideline_documents
same    table:guideline_learning_sessions
same    table:knowledge_progress
same    table:knowledge_units
same    table:learning_evidence_events
same    table:learning_recommendations
same    table:research_codes
same    table:scores
same    table:skill_sessions
same    table:sp_cases
same    table:sp_sessions
same    table:student_answers
same    table:students
same    table:study_allocations
same    table:study_cohorts
same    table:study_enrollments
same    table:teacher_score_reviews
same    table:teachers
same    table:teaching_interventions
same    table:tutor_turns
same    table:users

objects: 52 -> 52; differing: 0
schema equivalent (modulo clause order, quoting and server defaults)

=== acceptance complete: artifacts kept in /tmp/clinpath-migration-acceptance.ISl5kB ===

$ echo log: /tmp/clinpath-migration-acceptance.ISl5kB/migration_cycle.log
log: /tmp/clinpath-migration-acceptance.ISl5kB/migration_cycle.log
```

## 附录 B：真实开发数据库副本（只读复制）原样输出

```text
=== R8.3 legacy-path acceptance on a read-only COPY of a real development database ===
source: /home/jcshi/workspace/clinical_learning_system/backend/clinical_learning.db
copy  : /tmp/clinpath-legacy-final.GB3J7d/dev_db_copy.db (written via the sqlite3 backup API; the source was opened read-only)

--- 0. copy and record the pre-migration state ---
copy written
20260915_06
ai_enrichments	rows=5	columns=11
ai_invocations	rows=816	columns=15
case_sessions	rows=25	columns=6
cases	rows=10	columns=14
clinical_skills	rows=2	columns=10
competency_profiles	rows=4	columns=13
generated_case_drafts	rows=19	columns=5
guideline_documents	rows=2	columns=10
guideline_learning_sessions	rows=2	columns=9
knowledge_progress	rows=7	columns=7
knowledge_units	rows=3	columns=10
learning_evidence_events	rows=30	columns=12
learning_recommendations	rows=23	columns=6
scores	rows=19	columns=25
skill_sessions	rows=2	columns=9
sp_cases	rows=2	columns=11
sp_sessions	rows=1	columns=14
student_answers	rows=96	columns=6
students	rows=4	columns=5
teachers	rows=3	columns=5
tutor_turns	rows=43	columns=8
users	rows=8	columns=7
dumped 25 tables (revision 20260915_06) to /tmp/clinpath-legacy-final.GB3J7d/dump_rev06.json

--- 1. upgrade to 20261018_07 ---
20261018_07
dumped 25 tables (revision 20261018_07) to /tmp/clinpath-legacy-final.GB3J7d/dump_07.json
compare rev06 -> rev07 (teacher_score_reviews gains two provenance columns by design)
CHANGED teacher_score_reviews: columns ['id', 'evidence_event_id', 'ai_score', 'teacher_score', 'comment', 'agreement_delta', 'created_at', 'reviewer_user_id', 'confirmed_dimensions_json', 'projector_version'] -> ['id', 'evidence_event_id', 'ai_score', 'teacher_score', 'comment', 'agreement_delta', 'created_at', 'reviewer_user_id', 'confirmed_dimensions_json', 'projector_version', 'baseline_score', 'baseline_source']

training tables seeded and compared: 14; byte-identical: 13
NOT EQUIVALENT:
  teacher_score_reviews: columns changed
  training tables were not all identical

--- 2. upgrade to head ---
20261018_09 (head)
dumped 41 tables (revision 20261018_09) to /tmp/clinpath-legacy-final.GB3J7d/dump_head_1.json
wrote 52 schema objects to /tmp/clinpath-legacy-final.GB3J7d/schema_head_1.json
compare rev07 -> head (training data must be identical; assessment tables are added)

training tables seeded and compared: 14; byte-identical: 14
tables identical: 41, revision 20261018_07 -> 20261018_09
assessment_adjudications	rows=0	columns=10
assessment_answer_revisions	rows=0	columns=8
assessment_answers	rows=0	columns=6
assessment_audit_log	rows=0	columns=8
assessment_dataset_locks	rows=0	columns=9
assessment_events	rows=0	columns=5
assessment_final_scores	rows=0	columns=13
assessment_form_reviewers	rows=0	columns=5
assessment_form_reviews	rows=0	columns=7
assessment_forms	rows=0	columns=14
assessment_reviews	rows=0	columns=13
assessment_sittings	rows=0	columns=28
research_codes	rows=0	columns=4
study_allocations	rows=0	columns=10
study_cohorts	rows=0	columns=13
study_enrollments	rows=0	columns=6

--- 3. downgrade to 20261018_07 and upgrade head again ---
20261018_07
dumped 25 tables (revision 20261018_07) to /tmp/clinpath-legacy-final.GB3J7d/dump_07_again.json
20261018_09 (head)
dumped 41 tables (revision 20261018_09) to /tmp/clinpath-legacy-final.GB3J7d/dump_head_2.json
wrote 52 schema objects to /tmp/clinpath-legacy-final.GB3J7d/schema_head_2.json
compare rev07 -> rev07 after the cycle (must be byte-identical)

training tables seeded and compared: 14; byte-identical: 14
tables identical: 25, revision 20261018_07 -> 20261018_07
compare head -> head after the cycle (must be byte-identical)

training tables seeded and compared: 14; byte-identical: 14
tables identical: 41, revision 20261018_09 -> 20261018_09

--- 4. migrated head vs a fresh create_all install of the same models ---
wrote 52 schema objects to /tmp/clinpath-legacy-final.GB3J7d/schema_fresh.json
same    table:users

objects: 52 -> 52; differing: 7
SCHEMA MISMATCH: table:ai_enrichments, table:ai_invocations, table:competency_profiles, table:scores, table:student_answers, table:teacher_score_reviews, table:tutor_turns

```
