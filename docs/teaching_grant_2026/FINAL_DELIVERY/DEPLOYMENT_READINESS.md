# 部署就绪清单（DEPLOYMENT_READINESS）

> **本轮不合并 `main`、不部署生产**（R8.4）。本文件只是一份**待申请人明确授权后才执行**的清单，
> 里面没有任何一项被执行过。生产状态（历史记录为 `main@1d4ef48`）**本成员未重新核实**。
> 依据：`AGENTS.md`「Definition of Done」与开发不变量 1—15。

## 授权状态

- 申请人部署授权：**未授予**。
- 合并到 `main`：**未发生**。

## 部署前必须全部满足

| # | 检查项 | 状态 |
| --- | --- | --- |
| 1 | 后端测试全绿（`uv run --python 3.11 --with-requirements requirements.txt pytest -q`）；失败项逐条说明 | 未满足（基线 307 通过 / 5 失败，见 `TEST_REPORT.md`） |
| 2 | `npm run typecheck && npm run lint && npm run build` | 未执行（本成员 worktree 无 `node_modules`） |
| 3 | Playwright 全量，含独立考核中断恢复 | 未执行 |
| 4 | **带时间戳的 SQLite 备份**（任何 schema/数据变更前） | 未执行；生产库本成员未触碰 |
| 5 | 迁移在独立库与生产库**脱敏副本**上：升级 → 降级 → 再升级；表结构、行数、训练成绩与画像不变性核查 | 未执行 |
| 6 | 测试构建使用独立 `distDir`，**不覆盖生产 `.next`**（见 `STATUS.md §3` 的事故记录） | 须遵守 |
| 7 | `JWT_SECRET` 等密钥在 `~/.config/clinpath/` 的 mode-600 文件；不提交 `.env` | 须遵守 |
| 8 | 无特权账号被 seed；教师/管理员只通过 `python -m app.manage_users` 创建；禁止生产 `seed_data --reset` | 须遵守 |
| 9 | 多进程部署时重新核对内存限流与运行计数语义（不变量 15） | 未评估 |
| 10 | 学生接口无隐藏答案；考核题本、评分锚点不对学生可见 | 待 Assessment 隔离测试通过 |

## 部署步骤（获授权后）

1. 记录当前运行 SHA 与 schema；停止写入窗口；
2. 备份 SQLite（带时间戳）；
3. 在副本上演练迁移；
4. 部署（systemd user units）；迁移；
5. `./scripts/verify_deploy.sh` 必须 PASSED（运行源码 == 本检出，schema 在 head）；
6. **真实浏览器 smoke**：登录 → 训练 → 结果 → 登出；检查控制台与网络；
7. 如实报告运行的 SHA；任何失败立即回滚并报告。

## 研究启动前的额外门槛（与部署无关）

伦理意见/豁免、教师审核签字、教研室排期与随机化执行方式——见 `HUMAN_ACTION_CHECKLIST.md`。
部署成功**不等于**研究就绪。
