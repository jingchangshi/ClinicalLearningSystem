# 验收环境隔离说明（R0.3）

> 记录时间：2026-10-18。执行人：Agent Team 牵头成员。
> 本文只记录**实际核实**的事实与真实命令输出，不含推测。

## 1. 为什么必须隔离

生产栈正在同一台机器上运行。若在工作树内直接启动服务或执行迁移，可能覆盖生产的
`.next` 构建产物、占用生产端口，或对生产数据库执行破坏性操作。任务书 R0.3 因此要求
开发/验收环境在 Git 工作目录、前端构建目录、后端端口、前端端口、数据库、环境变量、
日志、临时导出目录八个方面与生产隔离。

## 2. 实际核实结果（只读检查）

生产由 systemd 用户单元运行，其工作目录与端口如下（来自 `systemctl --user cat`，
环境文件内容未读取、未打印）：

| 单元 | WorkingDirectory | 端口 | 环境 |
| --- | --- | --- | --- |
| `clinical-backend.service` | `/home/jcshi/workspace/clinical_learning_system/backend` | 8100 | `CLINPATH_ENV=production`，`EnvironmentFile=%h/.config/clinpath/backend.env` |
| `clinical-frontend.service` | `/home/jcshi/workspace/clinical_learning_system/frontend` | 8101 | `EnvironmentFile=%h/.config/clinpath/frontend.env` |
| `clinical-https.service` | — | HTTPS 入口（Cloudflare tunnel） | — |

三个单元在检查时均为 `active running`。

## 3. 本次验收使用的隔离环境

| 隔离项 | 生产 | 本次验收 |
| --- | --- | --- |
| Git 工作目录 | `/home/jcshi/workspace/clinical_learning_system` | `/home/jcshi/workspace/clinpath-final`（独立 worktree，分支 `feat/clinpath-final-2026`） |
| 前端构建目录 | 生产 `frontend/.next` | 工作树内 `frontend/.next`，与生产物理隔离 |
| 后端端口 | 8100 | 未占用 8100；测试使用内存/临时 SQLite 与 ASGI 测试客户端 |
| 前端端口 | 8101 | 未占用 8101；E2E 使用独立端口 |
| 数据库 | `~/.config/clinpath/backend.env` 所指生产库 | 独立临时 SQLite（`/tmp/...`），迁移验收使用 `alembic upgrade/downgrade/upgrade` |
| 环境变量 | `~/.config/clinpath/*.env`（mode 600） | 测试进程内构造的一次性变量；未读取、未提交生产密钥 |
| 日志 | 生产单元日志 | 测试进程 stdout / 证据目录内日志文件 |
| 临时导出目录 | — | `/tmp/clinpath-*` 一次性目录 |

## 4. 已执行的边界约束

1. **未**对生产数据库执行任何迁移、写入或破坏性测试。
2. **未**停止、重启或重新部署任何生产 systemd 单元。
3. **未**占用生产端口 8100 / 8101。
4. **未**打印或提交任何 API key、JWT secret 或 `.env` 内容。
5. 需要真实迁移验证时，只在临时 SQLite 上执行；若引用生产库副本，必须先复制到 `/tmp`
   再对副本操作，并在 `MIGRATION_ACCEPTANCE.md` 中说明。
6. 本轮**未**合并 `main`，**未**推送远端，**未**部署生产（R8.4）。

## 5. 与 Playwright 的关系（重要）

`frontend/playwright.config.ts` 的 `baseURL` 默认为 `http://127.0.0.1:8101`，与生产前端
端口相同。直接以默认值运行 E2E 会打到生产实例并可能写入生产数据。因此 E2E 必须显式
设置 `E2E_BASE_URL` 指向独立端口，且独立启动后端/前端。此约束已在执行前通知相关成员。

## 6. 未执行项

- 生产库副本上的迁移验收：本轮未执行（见 `MIGRATION_ACCEPTANCE.md` 的实际范围）。
- 生产环境部署与部署后浏览器验收：按 R8.4 本轮不做，需申请人单独授权。
