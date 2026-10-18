# 7 天个性化闭环的代码核验（T3 交付物）

> **状态：代码核验完成（第四轮，2026-10-18）。** 本文件只核验平台**代码是否真的接通**了
> 研究方案 §5.3 声称的四步个性化闭环，并给出 `file:line` 证据与一段端到端最小验证。
> 本文件不含任何真实学生数据，也不代表任何真实训练已经发生。
>
> 基线：分支 `teaching-grant-2026-wpd`，HEAD `072ebb3`。核验对象为**训练**病例提交
> （D2/D3），不是 D1 的 T0 独立考核。

## 1. 结论概览

| # | 研究方案 §5.3 的环节 | 是否接通 | 关键 `file:line` |
| --- | --- | --- | --- |
| 1 | D2/D3 训练提交产生六维形成性分数（`ai` 与 `rule_fallback` **两条路径都产生**） | **接通** | `backend/app/routes/sessions.py:219`；`backend/app/services/scoring_llm.py:127,152,185` |
| 2 | 该分数更新能力画像（`competency_profiles`，`UPDATE_WEIGHT = 0.3`） | **接通** | `backend/app/routes/sessions.py:245`；`backend/app/services/competency_update_service.py:9,56,137,159` |
| 3 | 推荐服务按最弱能力产生**因人而异**的任务并写入 `learning_recommendations` | **接通** | `backend/app/routes/sessions.py:257,259`；`backend/app/services/recommendation_service.py:55,60,78,238,268` |
| 4 | 教师可读取画像/推荐依据并记录干预 | **接通** | `backend/app/routes/teacher.py:66,91,190,227,322,337,553` |

四条链路**全部接通**。另发现一处**与"独立考核不进入形成性画像"相关的平台缺口**，
见 §5 与 `T3_personalization_gap.md`。

## 2. T0 时序更正声明（重要）

**更正对象**：`docs/teaching_grant_2026/evidence/E5_protocol/E5_01_research_protocol.md`
§5.3 表第 1 行"基线能力识别"的"学生/系统做什么"列。

> **定位**：基线 `072ebb3` 该句在第 **557** 行；核验时该文件正被其负责人并发编辑，
> 该句现位于第 **512** 行（文本未变）。请以**句子文本**为准定位。

- **原表述（已更正，仅作历史留痕）**：
  > "学生完成 **D1/D2** 的病例后，平台按六维能力更新其能力画像"（错误引文）

- **为什么错**：D1 的 **T0 是独立闭卷标准化病例考核**，监考、收卷，
  **作答在 D6 考核结束后才由两位盲评教师统一评分**（同一文件 D1/D6 排期表与"评分时点说明"；
  基线 `072ebb3` 为第 482、487、494 行，核验时因并发编辑现为第 437、442、449 行）。
  因此 T0 的分数在 **D1 当天不可能**进入 ClinPath 的六维能力画像。
  而 D4–D5 的个性化强化恰恰依赖"当前最弱维度"，所以**驱动 D4–D5 的画像只能来自 D2/D3 训练病例**，
  不能来自 T0。

- **正确表述（建议改为）**：
  > "学生完成 **D2/D3 训练病例**后，平台按六维能力更新其能力画像
  > （D1 的 T0 为独立闭卷考核，D6 后统一盲评，**不进入**该画像）。"

- **同一问题的第二处**：`T2_7day_teaching_plan.md` §3 表第 1 行"证据字段"原写"**T0 后的六维基线分**"，
  同样把 T0 当成了基线画像来源；已在本次 T3 中一并改为 **D2/D3 训练**产生的六维分数。

> 该文件（`E5_01_research_protocol.md`）由其他 agent 负责，本任务**未修改**，仅在此精确报告，
> 由负责人应用上述更正。

## 3. 四条链路的 `file:line` 证据

### 链路 1：训练提交 → 六维形成性分数（两条路径都产生）

| 事实 | 证据 |
| --- | --- |
| 提交路由调用评分 | `backend/app/routes/sessions.py:219` `score_payload = score_student_answer(case, answers, case["rubric"])` |
| 评分入口 | `backend/app/services/llm_service.py:408-411` → `evaluate_case_submission`（`scoring_llm.py:127`） |
| **AI 路径**产出六维 | `backend/app/services/scoring_llm.py:152` `scores = {key: round(evaluation.dimensions[key].score, 1) for key in CORE_ABILITIES}` |
| **规则回退路径**产出六维 | `backend/app/services/scoring_llm.py:178-203` `_rule_fallback_result()`，第 185 行 `**{key: rule_score[key] for key in CORE_ABILITIES}`，并标记 `evaluation_mode="rule_fallback"`、`degraded=True` |
| 六维键定义 | `backend/app/services/serializers.py:32-39` `CORE_ABILITIES` |
| 六维落库 | `backend/app/models.py:194-206` `Score` 六个列；`sessions.py:220-243` 写入 |

> 两条路径都返回同一组六个键，且规则回退**显式标记 `rule_fallback`/`degraded`**（符合架构不变式 3：
> 绝不把规则输出当作 AI）。

### 链路 2：分数 → 能力画像（`UPDATE_WEIGHT = 0.3`）

| 事实 | 证据 |
| --- | --- |
| 提交时更新画像 | `backend/app/routes/sessions.py:245` `update_competency_from_case(db, session.student_id, score_payload, session.id)` |
| 更新函数 | `backend/app/services/competency_update_service.py:56-82` |
| 权重 | `backend/app/services/competency_update_service.py:9` `UPDATE_WEIGHT = 0.3`（提交路径实际使用的定义） |
| 写画像 | 同文件 `137-182` `_apply_competency_updates`；第 159 行 `setattr(profile, key, after)`；`after = round(before*(1-0.3) + module_score*0.3, 1)`（第 158 行） |
| 画像表 | `backend/app/models.py:227-244` `competency_profiles` |

> 注：协议原引用的 `competency_projector.py:10` 也定义了同名常量（用于证据重放），
> 但**提交当次**写画像的是 `competency_update_service.py:9`。两者数值一致（0.3）。

### 链路 3：最弱能力 → 因人而异的推荐 → `learning_recommendations`

| 事实 | 证据 |
| --- | --- |
| 提交后生成推荐 | `backend/app/routes/sessions.py:257` `generate_learning_recommendation(profile_dict, [score_payload], cases)` |
| 生成入口 | `backend/app/services/llm_service.py:414-417` → `choose_recommendation` |
| 推荐决策（确定性、无模型） | `backend/app/services/recommendation_service.py:60-75` `choose_recommendation` |
| 最弱能力 | 同文件 `55-57` `weakest_abilities`；`238-253` `_pick_case`（用 `min(CORE_ABILITIES, ...)` 取最弱维度选病例） |
| 推荐理由 | 同文件 `268-278` `_recommendation_reason`（按最弱维度给文案） |
| 学习路径 | 同文件 `78-99` `build_learning_pathway`（LearnerGap → Candidate Generator → Constraint Filter → Ranker） |
| 每人一行 | `backend/app/routes/sessions.py:258-265` 写入 `LearningRecommendation`；表 `backend/app/models.py:247-258` |

> 关键：推荐对象由 `_pick_case`/`_recommendation_reason` 依据**本次提交的最弱维度**决定，
> 因此**不同薄弱画像 → 不同推荐病例与不同理由**（由 §4 的测试实证，非推断）。

### 链路 4：教师读取依据并记录干预

| 事实 | 证据 |
| --- | --- |
| 仅教师可访问 | `backend/app/routes/teacher.py:63-67` 路由级 `require_role(["teacher"])` |
| 学生学习画像 | `backend/app/routes/teacher.py:189-234` `GET /api/teacher/students/{id}/learning-profile`，第 227 行返回 `recommended_tasks`（含 `target_abilities`、`source_evidence`） |
| 班级短板视图 | 同文件 `90-133` `GET /api/teacher/dashboard`，第 122 行 `"weak_dimensions"`；`553-564` `_weak_dimensions` |
| 记录干预 | 同文件 `321-333` `POST /api/teacher/interventions`；表 `backend/app/models.py:471-480` |
| 干预列表 | 同文件 `336-339` `GET /api/teacher/interventions` |

## 4. 最小验证（端到端，确定性、无网络）

测试文件：`backend/tests/test_7day_personalization_loop.py`（本次新增，唯一新增测试文件）。

覆盖：

1. `test_training_scoring_produces_six_dimensions_in_both_paths`
   —— 直接调用真实评分函数，断言 `ai` 与 `rule_fallback` **两条路径都返回六个核心维度**（链路 1）。
2. `test_training_submission_updates_profile_and_writes_recommendation`
   —— 走真实 `POST /api/sessions/start`→`/answers`→`/submit` 路由，断言：
   - 落库的 `Score` 六维齐全；
   - 六个维度均按 `after = round(60*(1-0.3) + module_score*0.3, 1)` 更新；
   - **最弱维度**按其分数移动了 `UPDATE_WEIGHT=0.3`（基线 60，最弱 `evidence_based_medicine` 模块分 48 →
     画像 56.4，位移 −3.6）；
   - 写入了 `LearningRecommendation`，理由以该最弱维度对应文案开头；
   - 写入 `case_session_scored` 学习证据事件，且 `competency_updates_json` 含六维（可溯源，不变式 9）。
3. `test_different_weaknesses_get_different_recommendations`
   —— 两名学生、两个病例，注入**不同最弱维度**（`medical_knowledge` vs `differential_diagnosis`）的评分，
   断言推荐病例与推荐理由**不同**，且理由文本分别指向各自短板（链路 3 的"因人而异"）。
4. `test_teacher_reads_profile_and_records_an_intervention`
   —— 教师读 `learning-profile`（`recommended_tasks` 非空）、读 `dashboard`（`weak_dimensions`），
   创建干预后能在 `GET /api/teacher/interventions` 中查到（链路 4）。
5. `test_an_assessment_session_does_not_enter_the_formative_profile`（**`xfail`，见 §5**）
   —— 文档化"平台无独立考核模式"这一缺口。

运行命令与**真实输出**：

```console
$ cd backend
$ uv run --python 3.11 --with-requirements requirements.txt \
    pytest -q tests/test_7day_personalization_loop.py
....x                                                                    [100%]
4 passed, 1 xfailed, 1 warning in 2.98s
```

`xfail` 一条失败于其意图断言（非报错）：

```console
$ uv run --python 3.11 --with-requirements requirements.txt \
    pytest -q tests/test_7day_personalization_loop.py::test_an_assessment_session_does_not_enter_the_formative_profile --runxfail
>       assert profile.medical_knowledge == BASELINE
E       assert 63.9 == 60.0
tests/test_7day_personalization_loop.py:369: AssertionError
```

（历史说明：当时若把 T0/T1 提交到普通训练路由，它会把六维分数写进形成性画像——
这是 §5 记录的缺口；终稿轮的解决方式是独立在线考核模块，T0/T1 禁止走训练路由，隔离证据见 `FINAL_DELIVERY/TEST_REPORT.md`。）

## 5. 未接通项：平台没有"独立考核模式"

- **现象**：`CaseSession`（`backend/app/models.py:88-111`）没有任何 `mode`/`type` 字段区分"训练"与"考核"；
  `POST /api/sessions/{id}/submit`（`sessions.py:185-271`）**无条件**调用
  `update_competency_from_case`（第 245 行）并写入 `LearningRecommendation`（第 259 行）。
- **后果**：若把 D1 的 T0（或 D6 的 T1）提交进平台的这条路由，其分数会进入驱动 D4–D5 个性化的形成性画像，
  与研究方案"T0 独立、D6 后统一盲评、不进入画像"的设计冲突。
- **最小修复**（不在本任务实施，仅提出）：为 `CaseSession` 增加 `mode`（`training`/`assessment`）字段，
  在 `submit_session` 中对 `assessment` 只落 `Score`、**跳过** `update_competency_from_case` 与
  `LearningRecommendation` 写入。
- 详见 `T3_personalization_gap.md`。

> **合规说明**：本任务**未修改任何后端应用代码**；唯一新增代码是上述测试文件。
> 四条闭环链路均已通过真实路由代码验证接通。
