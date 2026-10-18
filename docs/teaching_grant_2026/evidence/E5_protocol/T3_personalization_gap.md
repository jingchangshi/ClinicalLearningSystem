# 个性化闭环缺口记录（T3 交付物）

> **状态：记录 1 处真实缺口，未修改后端应用代码。** 第四轮，2026-10-18。
> 基线 `teaching-grant-2026-wpd` @ `072ebb3`。
>
> 研究方案 §5.3 声称的四步个性化闭环**全部接通**（见 `T3_personalization_validation.md` §1）。
> 本文件记录的是闭环**外围**的一处缺口：平台无法把"独立考核"与"训练"区分开。

## 缺口：平台没有"独立考核模式"

### 事实（`file:line`）

1. `backend/app/models.py:88-111` —— `CaseSession` 只有 `student_id / case_id / status / started_at /
   completed_at`，**没有** `mode`、`type`、`is_assessment` 之类的字段。
2. `backend/app/routes/sessions.py:185-271` —— `POST /api/sessions/{id}/submit` 对**任何**会话：
   - 第 219 行：调用评分；
   - 第 245 行：**无条件** `update_competency_from_case(...)`；
   - 第 258-265 行：**无条件**写入 `LearningRecommendation`。
3. 因此平台在提交这一层**无法区分** D2/D3 的"训练病例"与 D1/D6 的"独立考核病例"。

### 为什么这是缺口（与研究方案的关系）

研究方案（`E5_01_research_protocol.md`）规定（行号：基线 `072ebb3` 为 482/487/494/557，
核验时因并发编辑现为 437/442/449/512，请以文本定位）：

- D1（T0）/D6（T1）是**独立闭卷标准化病例考核**，教师"不参与评分"；
- **D6 结束后**，两位盲评教师**统一**对 D1 与 D6 的全部作答评分；
- §5.3 第 1 行（**待更正**）：D4–D5 的个性化应基于能力画像。

若按平台现状把 T0/T1 提交进 `POST /sessions/{id}/submit`，则：

- T0 的分数会在 D1 当天进入形成性画像（`competency_profiles`），
- 并触发一条 `LearningRecommendation`，

这与"T0 独立、D6 后统一盲评、**不进入**形成性画像"的设计**冲突**，也会污染驱动 D4–D5 的最弱维度。

### 复现（测试）

`backend/tests/test_7day_personalization_loop.py::
test_an_assessment_session_does_not_enter_the_formative_profile`（标记 `xfail`）。
其期望行为是"独立考核不改变形成性画像"，但实际运行后画像被改动：

```console
$ uv run --python 3.11 --with-requirements requirements.txt \
    pytest -q tests/test_7day_personalization_loop.py::test_an_assessment_session_does_not_enter_the_formative_profile --runxfail
>       assert profile.medical_knowledge == BASELINE
E       assert 63.9 == 60.0
tests/test_7day_personalization_loop.py:369: AssertionError
```

（`medical_knowledge` 由基线 60.0 变为 63.9，即被本次提交更新了。）

## 最小修复（提案，未实施）

**方案（最小）**：给 `CaseSession` 增加一个 `mode` 字段（默认 `training`，另一取值 `assessment`），
并在 `submit_session` 中，当 `session.mode == "assessment"` 时：

- 仍然落 `Score`（评分留档）；
- **跳过** `update_competency_from_case`（`sessions.py:245`）；
- **跳过** `LearningRecommendation` 写入（`sessions.py:258-265`）。

改动面：1 处模型列 + 1 次 Alembic 迁移（含时间戳备份，遵循不变式 5）+ `submit_session` 内 1 个分支。
不改变任何训练路径的现有行为。

**方案（零代码，当前协议下即可执行）**：明确"T0/T1 不经过平台提交路由"——即与研究方案 §7.1
（D1 行"仅提交入口"）一致，T0/T1 以纸笔/线下方式完成，作答由盲评教师统一评分，平台只用于 D2–D5 训练。
若采用此方案，`T2_7day_teaching_plan.md` D1/D6 行的"病例训练（仅考核模式）"表述需相应澄清为"不进入平台形成性画像"。

> **建议**：在当前协议下优先采用**零代码方案**（T0/T1 本就不进平台形成性画像）；
> 若教研室希望 T0/T1 也走平台提交入口，再实施带 `mode` 字段的最小修复。
> 两条路都必须保证：**D4–D5 的最弱维度只来自 D2/D3 训练**，不能来自 T0。
