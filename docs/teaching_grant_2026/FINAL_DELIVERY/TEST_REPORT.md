# 测试报告（TEST_REPORT）

> **中期报告**（2026-10-18，应用/申报成员编写）。只记录**本成员实际执行**的检查及其真实输出；
> 其他成员负责的验收（前端、Playwright、迁移、E2E）在对应条目标「未执行」，**不得视为通过**。
> 牵头成员在集成后用最终 SHA 的完整运行替换第一节。

## 1. 后端全量测试（已执行，已提交基线）

| 项 | 值 |
| --- | --- |
| Git SHA | `47f7e6d`（分支 `feat/clinpath-final-2026`） |
| 检出 | 干净 detached worktree（排除他人未提交修改） |
| 环境 | aarch64 Linux 6.8，uv，Python 3.11，临时 SQLite |
| 命令 | `cd backend && uv run --python 3.11 --with-requirements requirements.txt pytest -q` |
| 时间 | 2026-10-18 14:18—14:20 UTC，耗时 107 s |
| 结果 | **307 passed，5 failed，1 xfailed** |
| 日志 | `../evidence/E2_platform/test_runs/backend_pytest_47f7e6d.log` |

失败的 5 项（**如实记录，未隐藏**）：

| 测试 | 原因（已核实的部分） | 归属 |
| --- | --- | --- |
| `test_independent_assessments.py::test_reject_unapproved_form` | 测试代码引用未定义的 `rater_ids`（`NameError`），是测试自身缺陷 | 独立考核实现者 |
| `test_seed_migration_semantics.py`（3 项） | 断言迁移 head 为 `20261018_07`，而仓库 head 已是 `20261018_08`（预期值过期）；他人对该文件的修改尚未提交 | 迁移/数据库成员 |
| `test_version_endpoint.py::test_version_endpoint_reports_deployment_truth` | `schema_revision` 为 `None`，与上一条同属迁移 head 问题；未单独定位 | 同上 |

`xfailed` 1 项：`test_7day_personalization_loop.py` 中记录“普通训练提交路由会更新画像”的历史缺口；
终稿轮需以 Assessment 正向隔离测试证明最终隔离，而不是靠该 `xfail`（R8.1）。

> 本报告写成时，他人的硬化工作（如 `20261018_09`）仍是未提交状态，故以上数字**不代表最终结果**。

## 2. 申报文本检查（已执行）

`python3 scripts/grant/check_application_text.py`（退出码 0）：

```text
栏目                        字数    上限    余量  结果
--------------------------------------------------------
项目研究基础                 488     600     112  PASS
拟解决的重点问题             370     600     230  PASS
项目工作思路与举措           900    1000     100  PASS
项目特色与创新               223     300      77  PASS
具体实施计划及预期成果       446     600     154  PASS
政策支持与经费保障           619     800     181  PASS
--------------------------------------------------------
合计                        3046    3900     854  PASS
```

内容机械检查（R7.4）共 23 项，全部 PASS（项目名称全文一致、四种状态用词、无已完成的真实研究/效果性表述/具体 P 值/伦理批准/批件号/班内随机/AOSD/无条件 2/35/合成效果、
必含 T0 不进入画像、D4/D5 来自 D2/D3、3+4 与 35 种、准实验备选、真实研究未启动、伦理尚无批件、21 人待确认、荣誉与单位承诺为待填、探索性）。

## 3. 一致性检查（已执行）

`python3 scripts/grant/check_protocol_consistency.py` 现覆盖 R7.4 机械规则，并把**缺失的关键文档视为失败（退出码 2）**。
截至本报告，它在本成员负责的文件上无违规；剩余违规只来自其他成员负责的文件（见 `FINAL_REPORT_ZH.md` §6.6 “过期表述”）：
`workpackages/A_cases/A04_difficulty_calibration_BLANK.md:14`、`A_cases/STATUS_A.md:42`、
`B_rubric/B02_sample_answers.md:138,173`、`B_rubric/STATUS_B.md:183` （过期表述）仍把 CASE-A02 写成 AOSD/Still，应改为干燥症状病例。
这些在其负责人修正前，该脚本会保持 FAIL——这是预期的“防止遗留过期表述”行为，而不是脚本缺陷。

## 4. 检查脚本自测（已执行）

`backend/tests/test_grant_checkers.py`：**44 passed**（`pytest -q`，0.12 s）。覆盖：六栏上限、缺文档/缺栏目退出码 2、超限与过期声明失败、
9 类被植入的错误陈述、否定式诚实陈述不误报、未知事实必须保持【待填】、缺失关键文档失败、13 类规则的植入/放行、A02 载荷校验。

## 5. 其他现有检查（已执行，非本成员负责）

`python3 scripts/grant/check_case_cards.py`：88 项检查，通过 87，失败 1，总体 FAIL。失败项属病例卡（病例负责人在改动 A02），本成员未处理。

## 6. 未执行（不得视为通过）

| 项 | 原因 |
| --- | --- |
| `npm run typecheck` | 本 worktree 未安装 `node_modules`（`tsc: not found`） |
| `npm run lint` / `npm run build` | 同上；并且不得在共享目录覆盖他人构建 |
| Playwright / 关键角色 E2E / 中断恢复 / 完整模拟研究流程 | 依赖前端构建与完整实现 |
| 7 批 49 人 98 份答卷批量流程 | 依赖实现合并 |
| 迁移升级/降级/再升级（独立库与生产库脱敏副本） | 他人负责；`_09` 未提交 |
| Assessment 数据域隔离正向测试 | 他人负责 |
| `verify_deploy.sh`、真实浏览器 smoke | 未部署，需申请人授权 |

## 7. 重新运行

```bash
cd backend && uv run --python 3.11 --with-requirements requirements.txt pytest -q
python3 scripts/grant/check_application_text.py
python3 scripts/grant/check_protocol_consistency.py
cd frontend && npm ci && npm run typecheck && npm run lint && npm run build && npx playwright test
```
