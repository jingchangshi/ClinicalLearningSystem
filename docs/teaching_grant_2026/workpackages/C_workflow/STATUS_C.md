# STATUS_C · 工作包 C（教学闭环演示）

日期：2026-10-18 · 执行环境：验证栈（**非生产**）
运行版本：`1d4ef4823c75fb9d89a7aec734b8b84d0bfa5c41`（`git_dirty=true`）
后端 `127.0.0.1:8201` / 前端 `127.0.0.1:8202` / 数据库 `/tmp/clinpath-demo-verify/verify.db`

> **一句话结论**：C01–C04 四份交付物已完成，含一份真实运行记录、一个已实跑通过的新增
> E2E 规格、3 处两行以内的可读性修正。**系统跑得通**已被自动化证据覆盖；
> **教学有效性**没有任何证据，也不在本工作包范围内。

## 逐项状态

| 项 | 状态 | 文件 |
| --- | --- | --- |
| C01 演示走查 | ✅ 完成 | `C01_demo_walkthrough.md` |
| C02 运行记录 + 原始证据 | ✅ 完成 | `C02_run_record.md` + `C02_evidence/`（25 个文件） |
| C02 自动化 E2E | ✅ 完成并实跑通过 | `frontend/tests/e2e/research-demo.spec.ts`（3/3 通过） |
| C03 页面缺口审计 | ✅ 完成 | `C03_page_gaps.md`（7 条，3 条已修） |
| C04 录屏脚本 + 截图 | ✅ 完成 | `C04_screenplay.md` + `C04_screenshots/`（17 张） |
| 专家观察记录 | ⛔ **刻意留空** | `C04_screenplay.md` 末节「待用户/真实教师补入」 |

## C01 · 演示走查

- 覆盖：课前诊断 → 5 阶段作答 → AI/规则追问来源 → 评分反馈 → 推荐任务 → 教师复核/干预 → 训练复盘
- 全部路由、一级标题、页面文本均从 Playwright 实际渲染中抄录；未出现臆造路由
- 记录了 10 条学生路由 + 10 条教师路由的实测标题
- 每条步骤标注了数据来源（真实 API / AI / 规则 / 合成）
- **未验证项已单列**：SP 完整作答、技能站、知识测验、指南 PICO、AI 评分成功路径、生产环境

## C02 · 运行记录

### 运行事实

| 项目 | 值 |
| --- | --- |
| 会话 | `session_id=1`，状态 `completed` |
| 病例 | id `1`，「SLE基础病例」 |
| 开始 / 完成 | `2026-10-18T09:28:48.698640` / `2026-10-18T09:29:29.532586` |
| 学生 | `student1`（李明，种子演示账号） |
| 教师 | `verify_teacher`（验收账号） |
| 评分 | **总分 72.6，`evaluation_mode=rule_fallback`，`degraded=true`** |
| 降级原因 | `case_evaluation` 调用 4 次全部 `Timeout`，累计 37581 ms |
| 同会话成功的 AI | `tutor_question` 1330 ms、`recommendation_explanation` 1606 ms、`teacher_insight` 1523 ms |
| 教师复核 | `ai_score=72.6` → `teacher_score=73.7`，`agreement_delta=1.1` |

### 命令与真实输出

```bash
curl -s http://127.0.0.1:8201/api/system/version
```

```json
{"app":"clinpath","environment":"development",
 "git_sha":"1d4ef4823c75fb9d89a7aec734b8b84d0bfa5c41",
 "git_sha_short":"1d4ef482","git_dirty":true,
 "backend_source_fingerprint":"v1:ff017794a5c4",
 "schema_revision":"20260915_06","backend_runtime":"python 3.11","ai_configured":true}
```

**注意**：这是**开发/验证栈**版本，不是生产 `clinpath.1031989.xyz` 上运行的版本。

### E2E 实跑

```bash
cd frontend
E2E_BASE_URL=http://127.0.0.1:8202 \
E2E_TEACHER_USERNAME=verify_teacher E2E_TEACHER_PASSWORD=... \
E2E_STUDENT_USERNAME=student1 E2E_STUDENT_PASSWORD=... \
npx playwright test tests/e2e/research-demo.spec.ts
```

```text
Running 3 tests using 1 worker

  ✓  1 [chromium] › tests/e2e/research-demo.spec.ts:33:7 › synthetic teaching-research demo › a teacher sees the synthetic banner and downloads the SYNTHETIC CSV (2.9s)
  ✓  2 [chromium] › tests/e2e/research-demo.spec.ts:83:7 › synthetic teaching-research demo › a student is redirected away and the API answers 403 (1.2s)
  ✓  3 [chromium] › tests/e2e/research-demo.spec.ts:106:7 › synthetic teaching-research demo › the real research export is unchanged and still offers its own CSV (1.6s)

  3 passed (7.4s)
```

### 既有规格回归（同一验证栈）

| 规格 | 结果 |
| --- | --- |
| `teacher.spec.ts` | 3/3 通过 |
| `demo-readiness.spec.ts` | 5/6 通过（复跑确认，见下） |
| `research-demo.spec.ts`（新增） | 3/3 通过 |

`demo-readiness.spec.ts` 唯一失败项：`研究数据 preview … diverse` 断言「至少 3 名学生 /
3 个模块 / 3 个日期」。复跑实测两个库的数据量：

```text
验证库 /tmp/clinpath-demo-verify/verify.db
  有证据学生数 1   模块 ['case']                    日期数 1
生产库 backend/clinical_learning.db
  有证据学生数 4   模块 ['knowledge','skill','case','guideline','sp']   日期数 17
```

**这是数据量前置条件不满足，不是代码回归**：该规格的设计前提是演示库已被
`scripts/prepare_presentation_data.py` 填充或本身就是生产演示库；一次性验证库没有跑过该脚本。
生产库满足 3/3/3 的门槛。

## C03 · 页面缺口

| # | 问题 | 处理 |
| --- | --- | --- |
| G-01 | 复核页「AI评分」列在规则降级数据上显示规则分 | 记录，未改（需改 API 契约） |
| G-02 | `LAST ERROR TYPE` 易被读成「最近一次调用失败」 | 记录，未改（需后端补字段） |
| G-03 | 学生首页「八维」实为九维 | **已修**（2 行文案） |
| G-04 | 单条记录时趋势图不渲染且缺 `data-testid` | **已修**（1 行） |
| G-05 | 干预页打印 `micro_lesson` / `evidence_based_medicine` | **已修**（改为渲染后端 `display_labels` 中文标签） |
| G-06 | 空数据时「平均能力提升 +0%」像结论 | 记录，未改 |
| G-07 | 学生路径页标题「AI个性化学习路径」与确定性排序不符 | 记录，未改 |

### 实际改动的文件与 diff 摘要

```text
frontend/app/(main)/student/dashboard/StudentDashboardClient.tsx  | 2 +-  (八维 → 九维)
frontend/components/GrowthTrendChart.tsx                            | 2 +-  (单条分支补 data-testid)
frontend/app/(main)/teacher/interventions/page.tsx                  | 改为渲染后端标签
```

> G-05 的最终形态由**带教**在服务端实现：`backend/app/services/display_labels.py` 增加
> `intervention_type_label`，`backend/app/routes/teacher.py` 的 `_serialize_intervention`
> 增加 `intervention_type_label` / `target_ability_label`，`frontend/lib/api.ts` 补类型。
> 服务端出标签比前端映射更符合仓库既有约定，已采纳该版本。

**没有做**任何布局、导航、配色或组件结构重构。

### 验证

```text
$ cd frontend && npm run typecheck
> tsc --noEmit            # 通过，无输出

$ npm run lint
> eslint . --max-warnings=0   # 通过，无输出
```

## C04 · 录屏脚本

- 6 个时间段（0:00–4:40），每段含「画面 / 口播原文 / 对评审说明什么」
- 17 张截图，逐张标注「证明什么 / 版本 SHA / 合成或模拟标注」
- 含合成数据的页面（`14`、`15`）画面内即带吸顶合成横幅
- 「专家观察记录」整节保留为 `待用户/真实教师补入`，未代写任何意见
- 附 5 条常见追问的据实回答（含「AI 挂了怎么办」「有没有真实学生用过」）

## 未验证 / 未取得的内容

| 项目 | 原因 |
| --- | --- |
| AI 评分成功路径（`evaluation_mode="ai"`） | 本次 4 次调用全部 Timeout，未取得一次成功样本 |
| SP 问诊 / 技能站 / 知识测验 / 指南 PICO 的完整作答闭环 | 只确认了列表页标题，未开新会话 |
| 生产环境同一条走查 | 约束禁止触碰生产 `8100/8101` 与 `backend/clinical_learning.db` |
| `demo-readiness.spec.ts` 全绿 | 验证库数据量不足（需演示数据脚本） |
| 真实学生、真实教师、真实课堂 | 未发生；`student1` / `verify_teacher` 均为种子/验收账号 |

## 阻塞在真实人员上的事项

1. **专家观察记录**（`C04_screenplay.md` 末节）：需要至少一名真实临床教师在真实课堂或
   小组演示后填写，附日期与签名。在此之前，任何材料不得声称 ClinPath 已经过临床教师评审。
2. **真实教学有效性**：本工作包只证明系统运行与数据可追溯。要回答「是否提高学习效果」，
   需要真实学生、对照设计与伦理审批——不属于 C 工作包。
3. **真实学生训练数据**：本次会话由种子演示账号产生，不能作为学生群体数据引用。

## 过程中的一次意外（已恢复，需带教知晓）

2026-10-18 09:36–09:41 UTC，在隔离验收栈上执行 `npm run build` 时误用了默认
`distDir`，覆盖了**生产前端服务读取的** `frontend/.next`（生产入口短暂指向临时后端 /
返回 502）。未发生 `git reset --hard`。

处置（已全部完成）：

1. `git stash push -u`（提交信息「wp-D + agent grant work …」）暂存本批改动；
2. 用生产环境变量重建 HEAD 前端并 `systemctl --user restart clinical-frontend.service`；
3. `./scripts/verify_deploy.sh` 恢复为 **PASSED**（运行版本 = `1d4ef48v1:582b7031978c`）；
4. `git stash pop` 恢复工作区；缺失的已跟踪文件改动已从 stash 提交对象
   `a28c95b9b3a7a6357ac18469d5ec9e718625c488` 重新 `apply`，工作区完整。

当前生产运行的仍是**未改动的 HEAD**；本批改动全部留工作区、**未部署**。
教训：验收栈必须使用独立 `NEXT_DIST_DIR`，绝不与生产共用 `frontend/.next`。

## 复现命令

```bash
# 版本
curl -s http://127.0.0.1:8201/api/system/version

# 复核证据链
curl -s -b <teacher.cookie> http://127.0.0.1:8201/api/teacher/reviews
curl -s -b <teacher.cookie> http://127.0.0.1:8201/api/system/ai-invocations

# 前端检查
cd frontend && npm run typecheck && npm run lint

# E2E
cd frontend && E2E_BASE_URL=http://127.0.0.1:8202 \
  E2E_TEACHER_USERNAME=verify_teacher E2E_TEACHER_PASSWORD=... \
  E2E_STUDENT_USERNAME=student1 E2E_STUDENT_PASSWORD=... \
  npx playwright test tests/e2e/research-demo.spec.ts
```

## 交付物清单

```text
docs/teaching_grant_2026/workpackages/C_workflow/
├── STATUS_C.md
├── C01_demo_walkthrough.md
├── C02_run_record.md
├── C02_evidence/             (25 个文件：JSON 原始响应、时间线、Playwright 输出)
├── C03_page_gaps.md
├── C04_screenplay.md
└── C04_screenshots/          (17 张 PNG，1440×900)

frontend/tests/e2e/research-demo.spec.ts   (新增，3 个用例，全部通过)
```
