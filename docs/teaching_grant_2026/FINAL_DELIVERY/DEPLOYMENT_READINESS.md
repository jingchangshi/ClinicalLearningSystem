# 部署就绪清单（DEPLOYMENT_READINESS）

> **本轮不合并 `main`、不部署生产**（R8.4）。本文件是**待申请人明确授权后才执行**的清单；
> 下列步骤**没有任何一项被执行过**。依据：`AGENTS.md`「Definition of Done」与开发不变量 1—15。
> 更新于 2026-10-18，交付 SHA `f2b32d8`。

## 授权状态

- 申请人部署授权：**未授予**。
- 合并到 `main`：**未发生**。
- 推送远端：**未发生**（本地领先远端 `80ce271`，交付顶端 `454a7bd`）。**注意 B8**：远端仓库为公开，推送会公开考核题本与答案逻辑。

## 生产现状（已核实，2026-10-18）

| 项 | 值 | 来源 |
| --- | --- | --- |
| 生产运行 SHA | `1d4ef482` | `GET http://127.0.0.1:8100/api/system/version` |
| 环境 | `production` | 同上 |
| schema revision | `20260915_06` | 同上 |
| 数据库 | 主检出 `backend/clinical_learning.db`（`backend.env` 未设 `DATABASE_URL`，使用代码默认相对路径） | `systemctl --user cat` + 环境文件键名 |
| 服务 | `clinical-backend`(:8100)、`clinical-frontend`(:8101)、`clinical-https` 均 active | `systemctl --user` |

本轮**未**停止、重启、迁移或写入上述任何服务与数据库。

## 部署前必须全部满足

| # | 检查项 | 状态 |
| --- | --- | --- |
| 1 | 后端测试全绿 | **已满足**（`f2b32d8`：425 passed / 0 failed） |
| 2 | `npm run typecheck && npm run lint && npm run build` | **已满足**（三项退出码 0，27/27 静态页） |
| 3 | Playwright 全量 | **部分**：R8.2 9/9；既有套件 26 passed / 3 failed / 11 skipped（3 项失败需真实模型密钥重建演示数据，见 `TEST_REPORT.md` §3） |
| 4 | **带时间戳的 SQLite 备份**（任何 schema/数据变更前） | **未执行**（本轮不部署） |
| 5 | 迁移在独立库与生产库副本上 升级→降级→再升级 | **已满足**（`MIGRATION_ACCEPTANCE.md`：隔离库 + 生产库只读副本；14/14 训练表逐字节一致） |
| 6 | 测试构建使用独立 `distDir`，不覆盖生产 `.next` | **已遵守**（E2E 用 `NEXT_DIST_DIR=.next-accept`）；部署时须继续遵守 |
| 7 | 密钥在 `~/.config/clinpath/` 的 mode-600 文件；不提交 `.env` | **已遵守** |
| 8 | 无特权账号被 seed；教师/管理员只经 `python -m app.manage_users` | **已遵守** |
| 9 | 多进程部署时重新核对内存限流与运行计数语义（不变量 15） | **未评估**（本轮单进程测试） |
| 10 | 学生接口无隐藏答案；考核题本与锚点不对学生可见 | **已满足**（隔离测试 + 浏览器截图核验） |
| 11 | 盲评 API 不泄漏姓名/学号/组别/批次/时点 | **已满足**（测试 + 截图核验） |

## 部署步骤（获授权后）

1. 记录当前运行 SHA 与 schema（`GET /api/system/version`）；
2. 停止写入窗口；**带时间戳备份** SQLite；
3. 在副本上演练迁移（`scripts/verify_migration_cycle.sh` 已可复用）；
4. 部署（systemd user units）；执行迁移；
5. `./scripts/verify_deploy.sh` 必须 PASSED（运行源码 == 本检出，schema 在 head）；
6. **真实浏览器 smoke**：登录 → 训练 → 结果 → 登出；检查控制台与网络；
7. 如实报告运行的 SHA；任何失败立即回滚并报告。

## 部署后必做的浏览器验收（R8.2）

学生 T0 独立考核完整流程、教师盲评、裁决、研究导出；并确认全过程**无 AI 调用**、
不更新能力画像、不产生学习推荐。

## 研究启动前的额外门槛（与部署无关）

伦理意见/豁免、教师审核签字、教研室排期与随机化执行方式、盲评人员独立性——
见 `HUMAN_ACTION_CHECKLIST.md` 与 `FINAL_REPORT_ZH.md` §6.6。

> **部署成功不等于研究就绪**，技术就绪也不等于研究可启动。
