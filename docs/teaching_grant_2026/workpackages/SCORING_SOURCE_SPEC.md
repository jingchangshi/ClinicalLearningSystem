# 评分口径与来源：现状、修复与最小兼容迁移

> 本轮只修复**来源标注错误**，不改变任何评分权重、不改写历史分数、不改动生产数据。
> 生产形成性评分权重仍为 `20/20/20/15/15/10`（`backend/app/services/scoring_llm.py`）；
> 研究量表 `10/20/25/15/20/10` 保持「待专家确认」，二者不得混用。

## 1. 四种分数必须始终可区分

| 来源 | 字段 | 谁产生 | 可用于 |
| --- | --- | --- | --- |
| 规则 | `Score.rule_score`、`evaluation_mode="rule_fallback"` | 确定性规则引擎 | 形成性反馈、过程指标 |
| AI | `Score.ai_score`、`evaluation_mode="ai"` | 模型（有 provider/model 记录） | 形成性反馈、过程指标 |
| 教师确认 | `Score.teacher_confirmed_score`、`TeacherScoreReview.teacher_score` | 教师在平台内确认 | 教学决策；**不是盲法独立评分** |
| 独立盲评 | 离线 `B03_rating_template.csv` → `REAL_BLINDED_RATER` | 两位真实教师，互不知情 | **研究主要结局** |

硬规则：

1. 平台内「复核确认」会**回写能力画像**，因此不满足盲法条件，不得作为研究主要结局。
2. 规则分不得出现在任何名为 AI 的字段或列标题下。
3. 合成演示中的 `SIMULATED_NOT_HUMAN` 评分者不是教师，也不是 AI 调用。

## 2. 本轮修复的缺陷

**缺陷**：`POST /api/teacher/reviews` 原先写入

```python
authoritative_ai_score = score.ai_score if score.ai_score is not None else score.total_score
TeacherScoreReview(ai_score=authoritative_ai_score, agreement_delta=teacher_score - authoritative_ai_score)
```

当评分为规则回退时 `score.ai_score is None`，于是**规则总分被存进了 `ai_score` 列**。
后果：复核历史、差值统计、任何按 `ai_score` 分组的分析，都无法区分"教师与 AI 的分歧"
和"教师与规则的分歧"。`/api/teacher/reviewable-evidence` 有同样的问题，
把规则总分放在 `ai_score` 键下返回给页面，页面列标题还写着「AI评分」。

**修复**（提交见本轮 Git）：

| 位置 | 变更 |
| --- | --- |
| `app/routes/teacher.py::_review_baseline()` | 唯一判定入口：`degraded` 或 `rule_fallback` → `(total_score, "rule_fallback")`；否则有 `ai_score` → `("ai")`；否则 `legacy_ambiguous` |
| `POST /api/teacher/reviews` | 写入 `baseline_score` / `baseline_source`；`ai_score` 写**真实的** `score.ai_score`（可为 `None`），不再回填规则分 |
| `GET /api/teacher/reviewable-evidence` | 新增 `baseline_score`、`baseline_source`、`baseline_source_label`、`rule_score`、`total_score`、`evaluation_mode`、`degraded`；`ai_score` 改为真实值（可为 `null`） |
| `GET /api/teacher/reviews` | 同上新增三个字段 |
| `app/services/display_labels.py` | `BASELINE_SOURCE_LABELS`：`AI 评分` / `规则降级评分（非 AI）` / `历史记录（来源无法区分）` |
| 前端复核页与复核记录表 | 列标题由「AI评分」改为「对照评分」+「评分来源」 |

## 3. 最小兼容迁移方案

迁移：`backend/alembic/versions/20261018_07_review_score_source.py`
（`20260915_06` → `20261018_07`）

| 变更 | 说明 |
| --- | --- |
| `teacher_score_reviews.ai_score` 允许 NULL | SQLite 无法就地放宽约束，使用 `batch_alter_table` 重建；**历史值逐字保留** |
| 新增 `baseline_score FLOAT NULL` | 复核所对照的数值 |
| 新增 `baseline_source VARCHAR(30) NOT NULL DEFAULT 'legacy_ambiguous'` | 生产者标注 |
| 历史行回填 | `baseline_score = ai_score`（该列在历史行上恒非空）；`baseline_source = 'legacy_ambiguous'` |
| 回滚 | 先把 `baseline_score`（必要时 `teacher_score`）回填进 `ai_score`，再恢复 NOT NULL 并删列，**不丢数** |

**为什么历史行不猜测来源**：旧行的 `ai_score` 可能来自模型，也可能是规则总分，
且当时没有 `degraded` 快照可查。把历史一律标为 `legacy_ambiguous` 是唯一诚实的做法；
把它标成 `ai` 会伪造来源。需要区分时，用 `Score` 表按 `session_id` 回查
`evaluation_mode` / `degraded` / `provider`，但那是**当前**状态，不是当时的快照。

**兼容性**：`ai_score` 字段名保留（历史消费者不破坏），但语义收窄为「模型产生的分数，无则为 null」。
新代码应读 `baseline_score` + `baseline_source`。

## 4. 迁移实测

在**生产库副本**上验证（`cp backend/clinical_learning.db /tmp/migtest/t.db`）：

```text
upgrade 20260915_06 → 20261018_07         成功
PRAGMA table_info(teacher_score_reviews)  ai_score notnull=0；baseline_score / baseline_source 存在
插入 1 条旧式复核行 → downgrade -1        成功，ai_score=72.6 保留
→ upgrade head                            成功，baseline_score=72.6，baseline_source=legacy_ambiguous
```

**未对生产库执行迁移。** 本轮不部署；迁移会在下次部署时由
`scripts/start_backend_8100.sh` 先备份再执行。

## 5. 回归测试

`backend/tests/test_review_score_provenance.py`（7 个用例）：

1. 规则回退复核：`baseline_source=rule_fallback`、`ai_score is None`、差值正确；
2. AI 复核：`baseline_source=ai`、基线取 `ai_score` 而非 `total_score`；
3. `degraded=True` 即使存在残留 `ai_score` 也判为规则；
4. `/reviewable-evidence` 逐行暴露来源；
5. `/reviews` 逐行标注；
6. 标签映射固定（历史不得被改称 AI）；
7. 一致性统计不得把规则与 AI 基线混在一组——按 `baseline_source` 分组后两组各自独立。

## 6. 仍需专家确认

- 研究量表权重 `10/20/25/15/20/10` 与平台 `20/20/20/15/15/10` 的差异：**本轮不改**，
  由专家确认后另开变更。
- 教师确认分是否应继续回写能力画像：这是既有设计，影响"平台内复核 ≠ 盲评"的表述，
  但不属于本轮修复范围。
