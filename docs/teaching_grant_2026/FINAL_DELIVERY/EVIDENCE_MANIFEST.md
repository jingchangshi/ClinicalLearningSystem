# 证据清单（EVIDENCE_MANIFEST）

> 规则：每条证据必须有**实际 Git SHA、环境、执行时间、日志路径**。没有真实运行的条目只能写 `PENDING`，
> 不得补写看起来合理的数字。检索入口另见 `../EVIDENCE_INDEX.md`。

## 1. 已有真实记录

| ID | 内容 | Git SHA | 环境 | 执行时间 (UTC) | 日志 / 位置 | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| M-01 | 后端全量 pytest（干净检出） | `47f7e6d` | 本机 aarch64 Linux，uv + Python 3.11，detached worktree（无他人未提交改动） | 2026-10-18 14:18—14:20 | `../evidence/E2_platform/test_runs/backend_pytest_47f7e6d.log` | **307 passed / 5 failed / 1 xfailed**；失败项列在 `TEST_REPORT.md` |
| M-01b | 后端全量 pytest（干净检出，第二次） | `f7f737c` | 同上 | 2026-10-18 14:25—14:27 | `../evidence/E2_platform/test_runs/backend_pytest_f7f737c.log` | **329 passed / 1 failed / 1 xfailed** |
| M-02 | 申报正文字数与内容检查 | 本提交 | 本机 python3 | 见 `TEST_REPORT.md` | `python3 scripts/grant/check_application_text.py` | 见 `TEST_REPORT.md` |
| M-03 | 方案一致性检查 | 本提交 | 本机 python3 | 见 `TEST_REPORT.md` | `python3 scripts/grant/check_protocol_consistency.py` | 见 `TEST_REPORT.md` |
| M-04 | 检查脚本自测 | 本提交 | uv + pytest | 见 `TEST_REPORT.md` | `backend/tests/test_grant_checkers.py` | 见 `TEST_REPORT.md` |
| M-05 | 前期工作包 C 真实运行（SLE 端到端）与 D 合成演示 | 前几轮提交（见 `../EVIDENCE_INDEX.md` 生成基线） | 隔离验证栈（非生产） | 2026-10-18（前几轮） | `../workpackages/C_workflow/`、`D_research_demo/` | 仅证明软件流程；评分走 `rule_fallback`，**非教学效果** |
| M-06 | **后端全量 pytest（最终交付树）** | `f2b32d8` | 本机 aarch64 Linux，uv + Python 3.11，临时 SQLite | 2026-10-18 17:0x | `../evidence/E2_platform/test_runs/backend_pytest_f2b32d8.log` | **425 passed / 0 failed**；运行期间 `backend/` 无改动 |
| M-07 | **前端 typecheck / lint / build** | `f2b32d8` | Node（worktree `node_modules`） | 2026-10-18 17:0x | `TEST_REPORT.md` §2 | 三项退出码 0；27/27 静态页 |
| M-08 | **R8.2 完整研究流程浏览器 E2E + 7×49 不变量 + 截图** | `b0a8a3f`（流程）/ 隔离栈重跑 | 隔离栈：后端 8400、前端 8401、`/tmp` SQLite、独立 `NEXT_DIST_DIR`、构建期烘焙 API 目标 | 2026-10-18 16:37—16:41 | `../E4_validation/RUN_RECORD_2026-10-18.md`、`../E2_platform/screenshots/`（16 张） | R8.2 **9/9**；既有套件 26/3/11；7×49 不变量 **7/7** |
| M-09 | **数据库迁移升级/降级/再升级** | `758c57b` / `88631e7` / `28c8081` | 隔离临时 SQLite + **生产库只读副本**（rev `20260915_06`） | 2026-10-18 15:10—15:5x | `../E2_platform/MIGRATION_ACCEPTANCE.md` | 14/14 训练表逐字节一致；修复 `d117899`；**生产库本身未迁移** |
| M-10 | **生产误触事件与影响核实** | — | 生产实例 `1d4ef482` 只读核实 | 2026-10-18 15:2x | `../E2_platform/INCIDENT_2026-10-18_production_touch.md` | 未写入生产（主库与 WAL `mtime` 未变、行数一致、考核路由未挂载） |
| M-11 | 检查脚本运行（5 个）与自测 | `f2b32d8` | 本机 python3 / uv + pytest | 2026-10-18 | `TEST_REPORT.md` §6 | 5 个脚本退出码 0；自测 71 passed |

## 2. 待产生（PENDING，必须由真实运行补入）

| ID | 内容 | 前置条件 | 状态 |
| --- | --- | --- | --- |
| P-01 | 独立考核完整浏览器 E2E（管理员建题本→两教师审核→发布→学生 T0→训练→T1→双评→裁决→导出）截图与日志 | — | **DONE** → M-08 |
| P-02 | 7 批 49 名测试学生 98 份答卷批量流程日志 | — | **DONE** → M-08 |
| P-03 | 迁移升级/降级/再升级（独立库与生产库脱敏副本） | — | **DONE** → M-09（生产库副本为**只读**副本；生产库本身未迁移） |
| P-04 | 前端 typecheck / lint / build | — | **DONE** → M-07 |
| P-05 | 部署与 `verify_deploy.sh` | 申请人明确授权 | **不执行**（R8.4）；不部署时该脚本不适用 |
| P-06 | 真实教师审核记录 | 两位真实教师 | **REAL_PENDING**（不可由 Agent 代作） |
| P-07 | 真实浏览器 smoke（登录→训练→结果→登出） | 部署后 | PENDING（需申请人授权部署） |
| P-08 | 变更类 E2E（`training.spec.ts`、教师干预、数据集冻结） | 需 `E2E_RUN_MUTATING` | PENDING |
| P-09 | 真实 AI 评分路径 | 真实模型密钥 | 本轮**刻意无密钥**；仅验证 `rule_fallback` 显式降级 |

## 3. 添加规则

新增条目时填写：ID、内容、**完整或 7 位 SHA**、环境（OS/Python/Node/DB）、UTC 时间、日志路径、结果（通过/失败/未执行）。
失败如实写失败，并链接对应问题；未执行写「未执行」。
