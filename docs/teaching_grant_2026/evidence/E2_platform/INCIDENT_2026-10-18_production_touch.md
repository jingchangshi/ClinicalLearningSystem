# 生产误触事件记录（INCIDENT 2026-10-18）

> 记录人：Agent Team 牵头成员。记录时间：2026-10-18 15:2x UTC。
> 本文件记录一次**真实发生的**、由本轮开发过程触达生产实例的事件，包括实际影响核实结果。
> 所有结论均来自只读核实（生产库只读打开、systemd 日志、`/api/system/version`）。

## 1. 事件经过

前端成员在隔离端口 8301 上启动一次性前端用于只读 Playwright 检查时，第一次使用的是
**未注入 `INTERNAL_API_BASE_URL` 的默认 `.next` 构建**。Next.js 的 `rewrites()` 在
**构建期**烘焙进产物，因此该构建的反代目标回落到默认值 `http://127.0.0.1:8100/api`，
即**生产后端**。该次运行因此经 8301 → 8100 向生产发出了少量请求。

成员自行发现（凭据行为与一次性库不一致），随后以
`INTERNAL_API_BASE_URL=http://127.0.0.1:8300/api` 重新构建；此后所有运行（含 6/6 通过的那次）
只访问一次性 8300 栈。两个一次性服务均已停止。成员主动上报了该事件。

## 2. 实际到达生产的请求（systemd 日志实证）

```
Oct 18 15:09:01 POST /api/auth/login 200 OK
Oct 18 15:09:08 POST /api/auth/login 200 OK
Oct 18 15:09:15 POST /api/auth/login 401 Unauthorized
Oct 18 15:09:25 POST /api/auth/login 200 OK
Oct 18 15:09:32 POST /api/auth/login 200 OK
Oct 18 15:14:57 POST /api/auth/login 200 OK
Oct 18 15:15:01 POST /api/auth/login 200 OK
Oct 18 15:08:59 GET /api/assessments/my           404 matched=unmatched
Oct 18 15:14:55 GET /api/assessments/my           404 matched=unmatched
Oct 18 15:14:58 GET /api/assessments/blind/queue  404 matched=unmatched
Oct 18 15:14:58 GET /api/assessments/adjudication/queue 404 unmatched
Oct 18 15:14:58 GET /api/assessments/forms/reviewable   404 unmatched
```

要点：**全部考核请求都是 404 `unmatched`**——生产运行版本 `1d4ef482` 根本没有挂载考核路由，
因此没有任何考核处理函数被执行。

## 3. 影响核实（三项独立证据一致）

| 核实项 | 观测 | 结论 |
| --- | --- | --- |
| 生产库主文件 `mtime` | 仍为 `2026-09-15 16:27` | 未发生写入 |
| 生产库 WAL 文件 `mtime` | 仍为 `2026-09-18 16:58`（`-shm` 为 `10-18 09:12`，早于事件） | 未发生写入 |
| 关键表行数 | `students 4`、`case_sessions 25`、`scores 19`、`competency_profiles 4`、`learning_evidence_events 30`、`ai_invocations 816`、`tutor_turns 43`、`student_answers 96`、`learning_recommendations 23` —— 与事件前记录逐项一致 | 未发生写入 |
| 考核表 | 生产 schema revision `20260915_06`，`sqlite_master` 中**不存在**任何 `assessment_*` 表 | 不可能发生考核写入 |
| 登录路由代码 | `routes/auth.py:login` 只读取用户、校验密码哈希并签发 JWT，**无任何 `db.add` / `db.commit`** | 登录不写库 |
| 限流 | 登录桶 `60 次/小时/身份`，本次约 7 次，且为内存滑窗 | 未锁定任何账号，一小时内自动恢复 |

**结论：本次事件未向生产写入任何数据，未改动生产库，未影响任何账号。**

## 4. 已实际发生的影响（不淡化）

1. 生产实例收到了约 7 次登录请求，其中 5 次凭据有效（200）。这些请求消耗了对应身份的
   登录限流额度（上限 60/小时，未接近）。
2. 生产实例接收到了若干只读 GET，全部返回 404。**没有数据被读取出来**：考核路由未挂载，
   返回的是路由不存在的 404。
3. 未部署、未迁移、未重启任何生产单元；生产仍运行 `1d4ef482`，schema 仍为 `20260915_06`。

### 4.1 关于 `/api/system/version` 的 `git_dirty: true`

事后复查时该端点报告 `git_dirty: true`。已核实其来源：`main.py:git_revision()` 用
`git status --porcelain` 的**非空**判断 dirty，而主检出中存在一个**未跟踪**文件
`docs/goal/teaching-1018-final.md`（用户放入的任务书，从未提交）。该命令不区分已跟踪
修改与未跟踪文件，因此任何未跟踪文件都会置位。

核实：主检出 `git status --porcelain` 只有 `?? docs/goal/teaching-1018-final.md` 一行，
`git status --porcelain --untracked-files=no` 为空，HEAD 仍为 `25a9177`。
**没有任何已跟踪文件被修改，生产运行的代码未变。** 这一项不是本次事件造成的，也不影响
上述"未写入生产"的结论；记录于此以免日后被误读为"生产存在本地代码改动"。

## 5. 根因与纠正措施

**根因**：Next.js `rewrites()` 的目标地址在 `next build` 时确定；仅在 `next start` 时设置
`INTERNAL_API_BASE_URL` 不会改变产物中的目标，于是静默指向了默认端口 8100（生产）。

**纠正措施**（已落实并需在 E2E 步骤中强制）：

1. 凡为验收构建前端，必须在 `next build` 时设置 `INTERNAL_API_BASE_URL` 指向隔离后端，
   或使用独立的 `NEXT_DIST_DIR` 构建目录，二选一，不得复用默认 `.next`。
2. Playwright 必须显式传入 `E2E_BASE_URL`（默认值是 8101，即生产前端端口）。
3. 验收前先确认目标端口不是 8100/8101。
4. 本条已写入 `ENVIRONMENT_ISOLATION.md` §5 与 E2E 任务说明。

## 6. 与任务书的关系

R0.3 要求隔离开发与验收环境；本事件说明**隔离不能只靠"用不同端口"，还必须隔离构建产物**，
因为反代目标在构建期固化。如实记录，不视为"未发生"。
