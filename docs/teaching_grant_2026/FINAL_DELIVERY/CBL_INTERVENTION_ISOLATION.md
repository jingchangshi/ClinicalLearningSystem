# CBL 对照组训练访问隔离（R9 §3）

> 状态：**服务端已实现并通过测试**；干预窗口由批次已登记的教学起止日期决定。
> 本文只描述已实现的代码行为，不声称任何真实研究已经启动。
> 实现位置：`backend/app/research/study_access.py`；测试：
> `backend/tests/test_study_access_isolation.py`（13 项，全部通过）。

## 1. 问题

R9 §3.1 确认：`sessions.py`、`cases.py`、`students.py` 中没有任何
`StudyEnrollment` / `StudyAllocation` 读取，因此被整批随机分入 CBL 组的研究学生
仍可进入 ClinPath 形成性训练（新会话、AI 导师、提交评分、个性化推荐），构成
干预污染。仅隐藏前端导航不构成访问控制。

## 2. 访问策略（一个函数，四个入口共用）

`app/research/study_access.py::access_for(db, student_id, today=...)` 返回一个
不可变的 `StudyAccess` 判定；训练路由只调用 `require_training_access(...)`。

判定顺序：

| 情形 | 结果 | 依据 |
| --- | --- | --- |
| 未在 `StudyEnrollment`（`status="enrolled"`）中 | 不受限 | 非研究学生完全不受影响 |
| 已入组，但 `StudyAllocation(kind="cluster_group")` 尚未冻结 | 不受限，**不推断组别** | §3.3.10 |
| 冻结组别为 `CLINPATH` | 不受限 | |
| 冻结组别为 `CBL`，且批次教学窗口**未结束** | **拒绝** | 见下 |
| 冻结组别为 `CBL`，且批次窗口已登记为结束 | 放行 | 研究结束后由既定教学方案控制 |

窗口语义（`actual_start/actual_end` 优先，其次 `planned_start/planned_end`）：

- 尚无任何日期：`undetermined` → **保持关闭**。理由：组别已冻结即为研究学生，
  在缺少窗口证据时默认放行等于按猜测开放干预；拒绝是保守且不泄漏信息的一侧。
- 今日 < 开始：`not_started` → 关闭（批次已入组、组别已定，干预内容此时同样不可用）。
- 开始 ≤ 今日 ≤ 结束：`open` → 关闭。
- 今日 > 结束：`closed` → 放行。

该函数读取的冻结记录与 `app.assessment.design.design_for` 完全一致（同一
`StudyAllocation` 行、同一 JSON 字段）；`test_policy_agrees_with_the_frozen_allocation`
逐名学生比对两者，防止日后漂移。

## 3. 受保护的入口

| 入口 | 保护 | 说明 |
| --- | --- | --- |
| `POST /api/sessions/start` | 拒绝 | 拒绝发生在**写入会话行之前**（测试断言无新行） |
| `POST /api/sessions/{id}/answers` | 拒绝 | 按**学生当前状态**判定，旧会话不能绕过 |
| `POST /api/sessions/{id}/coach` | 拒绝 | 旧式单问接口 |
| `POST /api/sessions/{id}/tutor` | 拒绝 | AI 导师（真实追问路径） |
| `GET  /api/sessions/{id}/tutor` | 拒绝 | 读取既有导师对话 |
| `POST /api/sessions/{id}/submit` | 拒绝 | 训练提交、评分、画像更新、推荐写入 |
| `GET  /api/sessions/{id}/result` | 拒绝 | 含训练评分与推荐 |
| `GET  /api/student/{pathway,competency,dashboard,history}` | 拒绝 | 个性化推荐、能力画像、训练成绩 |
| `GET  /api/students/{id}/{pathway,competency,dashboard}` | 仅当请求者是该学生本人 | 教师/管理员保留审计视图 |

**不拦截**（§3.3.7：区分普通教学资源与研究干预内容）：

- `GET /api/sessions/{id}`：会话外壳（病例材料 + 学生自己的未评分作答），
  不含导师输出、评分或推荐；且与 `/api/cases/{id}` 可见内容一致。
- `/api/cases`、`/api/knowledge`、`/api/guidelines`、`/api/skills`、`/api/sp-cases`：
  普通病例学习与教学资源。
- `/api/student/me`、`/api/student/knowledge-progress`。
- 独立在线考核全部接口（`/api/assessments/my/*`）：§3.2/§3.3.8 明确要求 CBL 组
  D1/D6 可用，测试 `test_cbl_student_can_complete_the_independent_assessment`
  在同一登录会话中同时验证“考核可完成 + 训练被拒”。

## 4. 拒绝格式与不泄漏

沿用本仓库 `app.assessment.access.fail` 的约定：

```json
{"detail": {"code": "study_training_restricted",
            "message": "当前研究教学安排下，本账号暂不能使用该训练功能；独立在线考核不受影响。请按课程安排参加常规教学，如有疑问请联系任课教师。"}}
```

`message` 不含组别、批次编码、研究编码或窗口日期。`test_refusal_reveals_no_arm_or_cohort`
对三个拒绝响应做子串扫描，断言不出现 `CBL/CLINPATH/C1..C7/研究编码`。
判定原因（`cbl_arm_window_open` 等）只存在于服务端 `StudyAccess.reason` 与管理员
Research 导出中，从不进入学生响应。

## 5. 测试清单（`tests/test_study_access_isolation.py`）

负面：CBL 不能创建训练会话；不能经旧会话继续作答/提交/取回结果/读取导师对话；
不能读个性化与画像；拒绝信息不泄漏组别。

正向：CBL 可完成独立 T0 考核；ClinPath 组完整训练链路（开始→五步作答→提交→结果→
pathway/competency/dashboard/history）正常；非研究学生完全不受影响；普通教学资源
保持开放；教师仍可查看受限学生的画像与路径。

边界：窗口未登记保持关闭；窗口未开始保持关闭；窗口结束后放行；学生退出研究后
不再受限；组别未冻结时**不推断**；策略与冻结分配逐人一致。

## 6. 未覆盖 / 剩余风险

1. **研究结束后的开放**：代码只实现“窗口结束后放行”。是否真正开放由教学方案
   决定，本实现不提供额外开关；如需在窗口结束后仍保持关闭，应另行决策。
2. **CBL 组的常规 CBL 教学**：不使用 ClinPath 训练，因此不需要（也不应）由本策略
   模拟；其过程证据见 `RESEARCH_TRAINING_LINKAGE.md` 的教学登记。
3. **知识/技能/指南/SP 模块**：R9 §3 未将其列为干预要素，故未拦截；若研究方案
   将其纳入干预，需要重新评估（属于方案变更，不是代码缺陷）。
4. **前端**：本实现不修改 `frontend/**`；前端隐藏导航只是体验优化，访问控制以
   上述服务端判定为准。
5. 本文件不构成伦理或研究启动批准；真实研究启动仍需伦理审查与教师排班。
