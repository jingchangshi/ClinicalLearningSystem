# C03 · 页面可读性缺口审计

> 审计方式：以临床教师视角，在验证栈 `127.0.0.1:8202` 上逐个打开教师端与学生端页面，
> 读取**实际渲染的文本**，并对照 API 返回的数据判断「页面说的」和「数据是」是否一致。
> 只列**小**问题；不做重构。

## 结论摘要

| # | 页面 | 问题 | 严重度 | 处理 |
| --- | --- | --- | --- | --- |
| G-01 | `/teacher/score-review` | 待复核与复核记录两处的「AI评分」列，在 `rule_fallback` 数据上显示的是规则分 | **中**（与「不把规则说成 AI」相冲突） | 已列，未改（改动涉及接口契约） |
| G-02 | `/teacher/runtime` | `LAST ERROR TYPE` 与 `CALLS/FAILURES/FALLBACKS` 并排，容易被念成「最近一次调用失败」 | 中 | 已列，未改（涉及后端字段语义） |
| G-03 | `/student/dashboard` | 「八维能力画像」实际画的是九维 | 中 | **已修**（2 行） |
| G-04 | `/teacher/students/[id]` | 只有 1 次训练记录时，趋势区不渲染图，且没有 `data-testid` | 中 | **已修**（1 行） |
| G-05 | `/teacher/interventions` | 直接打印 `evidence_based_medicine`、`micro_lesson` 等枚举键 | 中 | **已修**（由带教改成后端 `display_labels` 提供中文标签） |
| G-06 | `/teacher/dashboard` | 空数据时「平均能力提升 +0%」旁边是「平均分 72.6」，读起来像全班都是 0 提升 | 低 | 已列，未改 |
| G-07 | `/student/pathway` | 页面标题「AI个性化学习路径」，但排序是确定性的 | 低 | 已列，未改 |

---

## G-01 · 复核页把规则分标成「AI评分」

**位置**：`frontend/app/(main)/teacher/score-review/page.tsx`，
`frontend/app/(main)/teacher/score-review/TeacherReviewClient.tsx`

**看到什么**：两张表的表头都写「AI评分」，值取 `ai_score`。但
`backend/app/routes/teacher.py` 的 `list_reviewable_evidence` 与
`create_score_review` 在 `score.ai_score is None` 时回退到 `score.total_score`：

```python
"ai_score": score.ai_score if score.ai_score is not None else score.total_score,
```

本次运行中 `evaluation_mode=rule_fallback`、`ai_score=null`、`total_score=72.6`，
于是复核页显示「AI评分 72.6」——**这个 72.6 是规则分，不是 AI 分**。

**为什么算缺口**：与 AGENTS.md 第 3 条（规则结果不得冒充 AI）以及学生结果页
已经做对的「规则降级评价（AI 当前不可用）」相冲突。教师看到的证据种类决定了
他复核时的心理锚点。

**建议**（未实施）：`reviewable-evidence` 增加 `evaluation_mode` / `degraded` 字段，
表头改为「评价分数」并在单元格加「规则」/「AI」标签。这要改 API 契约与
`frontend/lib/api.ts` 的类型，超出「一两行」范围，因此只记录。

**本次演示如何处理**：`C01`、`C02` 明确写明该分数来自规则降级；`C04` 的口播稿
在展示复核页时也会点明。

## G-02 · 运行状态页的 `LAST ERROR TYPE`

**位置**：`frontend/app/(main)/teacher/runtime/AiRuntimeClient.tsx:46`

**看到什么**：`LAST ERROR TYPE` 显示 `Timeout`，下一行 `CALLS / FAILURES / FALLBACKS`
显示 `6 / 1 / 1`。这两行并排时，读者会理解成「最近一次调用超时失败」。

**实际情况**：`backend/app/core/ai_runtime.py` 的 `last_error_type` 记录的是
**最近一次出现过的错误类型**，不是「最近一次调用的结果」；`last_call_mode=ai`
说明最近一次调用**成功**。本次运行正是这种情况：`case_evaluation` 4 次调用超时，
随后的 `recommendation_explanation`、`teacher_insight` 都成功。

**建议**（未实施）：标签改为「最近错误类型（非最近一次结果）」或增加一行
「最近一次调用结果」。只改前端文案是一行，但正确的修法是让后端同时给出
`last_call_ok`，否则文案仍然依赖读者自己推断。记录在此。

## G-03 · 学生首页「八维」实为九维 ✅ 已修

**位置**：`frontend/app/(main)/student/dashboard/StudentDashboardClient.tsx:91,129`

**看到什么**：指标卡注脚「八维能力画像均值」，右侧雷达图标题「八维能力画像」；
但雷达图数据是 `dashboard.competency.expanded_chart_data`，**9 项**
（医学知识 / 技能操作 / 关键信息提取 / 鉴别诊断 / 证据整合 / 临床决策 /
循证医学 / 医患沟通 / 人文关怀）。而且「综合胜任力指数 66」正是这 9 项的平均值
（`competencyAverage` 用 `expanded_chart_data` 求平均）。

**为什么算缺口**：教师/评委会数雷达图的轴。标题说八维、图上九维，会让人怀疑
数据来源；同时「八维」与「九维」在教师端（`/teacher/dashboard` 写「全班九维能力均值」）
不一致。

**改动**（2 行，纯文案）：

```diff
-<MetricCard ... note="八维能力画像均值" ... />
+<MetricCard ... note="九维能力画像均值" ... />
-<h2 className="font-semibold">八维能力画像</h2>
+<h2 className="font-semibold">九维能力画像</h2>
```

未改动 `frontend/components/demo/CompetencyAssessmentDemo.tsx` 的「八维临床胜任力雷达图」：
那是独立的产品演示组件，不在本次走查路径上。

## G-04 · 单条记录时趋势图「消失」 ✅ 已修

**位置**：`frontend/components/GrowthTrendChart.tsx:43-52`

**看到什么**：`/teacher/students/1` 的「阶段性学习表现趋势」区只显示一行灰底文字
「当前仅有 1 次有效训练记录，完成更多训练后可形成趋势。」，**没有** `growth-trend-chart`
这个 `data-testid`，只有 `points.length > 1` 的分支才有。

**为什么算缺口**：新班级的第一周必然只有 1 条记录。此时该区块在结构上"缺失"，
既不利于自动化断言，也让教师以为趋势功能没做。

**改动**（1 行）：给单条记录分支的容器补上同一 `data-testid`。

```diff
-<div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
+<div className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-slate-600" data-testid="growth-trend-chart">
```

修完后 `demo-readiness.spec.ts` 中「李明 profile explains the trend…」由失败转为通过。

## G-05 · 干预页打印枚举键 ✅ 已修（带教改为后端标签）

**位置**：`frontend/app/(main)/teacher/interventions/page.tsx`

**看到什么**：卡片右上角徽标显示 `micro_lesson`，正文「目标能力：evidence_based_medicine」。

**为什么算缺口**：这是给临床教师看的页面，`micro_lesson` 不是中文教学语言；
也与仓库既有的「一个中文显示词表」约定（`backend/app/services/display_labels.py`）不符。

**最终改动**：本工作包先在前端加了一层映射，随后带教在 `display_labels.py` 与
`_serialize_intervention` 中补了 `intervention_type_label` / `target_ability_label`
（服务端出标签，前端不再持有第二套词表，符合仓库既有做法）。前端改为直接渲染
后端标签：

```diff
-<span ...>{INTERVENTION_TYPE_LABELS[item.intervention_type] ?? item.intervention_type}</span>
+<span ...>{item.intervention_type_label}</span>
-<p ...>目标能力：{abilityLabel(item.target_ability)}</p>
+<p ...>目标能力：{item.target_ability_label}</p>
```

实测（`GET /api/teacher/interventions`）：`micro_lesson → 专题小课`、
`evidence_based_medicine → 循证医学`。截图 `C04_screenshots/13_interventions.png`。

## G-06 · 空数据时「+0%」看起来像结论

**位置**：`frontend/app/(main)/teacher/dashboard/page.tsx`

**看到什么**：指标卡「平均能力提升 +0%」，注脚「平均分 72.6」。本次班级只有 1 条
完成记录，`average_improvement` 因此为 0。

**为什么算缺口**：教师会把它读成「这个班没有进步」，而实际上样本只有 1 人 1 次。
建议在 `average_improvement === 0 && completed_session_count <= 1` 时显示
「暂无足够数据」。改动是一行条件文案，但涉及产品口径（0 与「无数据」的区分），
留待带教决定。

## G-07 · 「AI个性化学习路径」标题与确定性排序

**位置**：`frontend/app/(main)/student/pathway/page.tsx`

**看到什么**：一级标题「AI个性化学习路径」。

**实际情况**：路径排序由 `recommendation_service` 确定性计算，模型只改写推荐理由
的措辞（AGENTS.md 第 12 条）。标题让人以为模型在决定学什么。

**建议**（未实施）：改为「个性化学习路径」，「AI」只出现在解释段落。属产品措辞
决定，不在本次改动范围。

---

## 已核对、**没有**发现问题的项

| 检查 | 结果 |
| --- | --- |
| 学生端是否泄露标准诊断 / 治疗方案 / rubric | `GET /api/cases/1` 对学生只返回主诉、病史、体查、化验、影像、学习目标；`GET /api/sessions/1/result` 只返回学生自己的答案与评分。未见泄露 |
| 结果页是否标注评价方式 | 有，`规则降级评价（AI 当前不可用）`，且注明「形成性评价，仅供教学参考，最终评价由教师确认。」 |
| 合成研究页是否带合成标记 | 有，吸顶横幅 + 数据集/种子/标记行，导出 CSV 文件名与每行都带 `SYNTHETIC` |
| 真实导出页是否被合数据污染 | 没有；两页互链但各自标注清晰 |
| 运行时页是否打印密钥 | 没有；页面声明不出 Key/Authorization，实测文本中亦无 |
| 教师端是否出现 `student_code` / `module_type` / `created_at` 等原始字段 | 学生总览与驾驶舱均无（`demo-readiness.spec.ts` 断言通过） |
| 中文教学语言（阶段名、模块名、能力名） | 教师/学生页面一致，如「阶段2：复杂症状鉴别」「病例推理训练」 |

## 本次实际改动的文件

| 文件 | 改动 |
| --- | --- |
| `frontend/app/(main)/student/dashboard/StudentDashboardClient.tsx` | 2 处文案：八维 → 九维 |
| `frontend/components/GrowthTrendChart.tsx` | 1 处：单条记录分支补 `data-testid="growth-trend-chart"` |
| `frontend/app/(main)/teacher/interventions/page.tsx` | 改为渲染后端提供的 `intervention_type_label` / `target_ability_label`（中文标签由带教在 `backend/app/services/display_labels.py` 与 `routes/teacher.py` 补齐） |

验证：`npm run typecheck`、`npm run lint` 均通过；`npx playwright test` 中
`research-demo.spec.ts` 3/3、`teacher.spec.ts` 3/3、`demo-readiness.spec.ts` 5/6
（唯一失败项是数据量前置条件，见 `STATUS_C.md`）。

**没有做**任何布局、导航、配色或组件结构上的重构。

## 演示时必须主动说明的两点

1. 本次评分为**规则降级**（`rule_fallback`），复核页的「AI评分」列标签问题（G-01）
   会让这个区别在教师端变模糊——讲解时要口头点明。
2. 运行状态页的 `LAST ERROR TYPE: Timeout` 不等于「最近一次调用失败」，
   要看 `LAST EVALUATION SOURCE: ai` 与审计表（G-02）。
