# E2 平台实现及技术验收（只收录与实际版本对应的真实记录）

> 规则（R6.3）：**截图必须对应实际运行的版本**；每条证据写明 Git SHA、环境、UTC 时间、日志路径。
> 没有真实运行就写 `PENDING`，不得补写数字。总清单见 `../../FINAL_DELIVERY/EVIDENCE_MANIFEST.md`。

## 一、已有真实记录

| 编号 | 证据 | Git SHA | 环境 | 时间 (UTC) | 位置 | 结果 |
| --- | --- | --- | --- | --- | --- | --- |
| E2-01 | 后端全量 pytest（干净检出） | `47f7e6d` | aarch64 Linux / uv / Python 3.11 / 临时 SQLite | 2026-10-18 14:18—14:20 | `test_runs/backend_pytest_47f7e6d.log` | **307 passed，5 failed，1 xfailed**（失败项见 `../../FINAL_DELIVERY/TEST_REPORT.md`） |
| E2-01b | 后端全量 pytest（干净检出，第二次，**最新**） | `f7f737c` | 同上 | 2026-10-18 14:25—14:27 | `test_runs/backend_pytest_f7f737c.log` | **329 passed，1 failed，1 xfailed**（失败：`test_version_endpoint`） |
| E2-02 | 训练闭环四链路核验与端到端测试 | 前几轮提交 | 同上 | 2026-10-18（第四轮） | `../E5_protocol/T3_personalization_validation.md`、`backend/tests/test_7day_personalization_loop.py` | 第四轮记录 4 passed / 1 xfailed；当前以 E2-01 为准 |
| E2-03 | 工作包 C：SLE 端到端真实运行记录（验证栈，非生产） | 见 `../../EVIDENCE_INDEX.md` 生成基线 | 隔离验证栈 | 2026-10-18（第一轮） | `../../workpackages/C_workflow/` | 评分走 `rule_fallback`，提问走真实模型；不得写成 AI 评分 |
| E2-04 | 页面截图（训练与教师侧、合成演示页） | 同上 | 同上 | 同上 | `../../workpackages/C_workflow/C04_screenshots/`、`../../workpackages/D_research_demo/D01_screenshots/` | **属早期版本截图**，不含独立考核页面；引用时须写明其对应的早期 SHA |
| E2-05 | 合成研究演示数据与可复算统计 | 同上 | 同上 | 同上 | `demo_research/synthetic_v1/`、`backend/tests/test_demo_research.py`（仓库根相对路径） | `SYNTHETIC / SIMULATED_NOT_HUMAN`，不是效果证据 |

> 旧版 README 中的「228 passed」「生产 `1d4ef48`」等数字属早期状态，**不再引用**。

## 二、独立考核与研究管理的真实截图/测试记录（PENDING）

下列条目**目前没有真实运行记录**，在隔离环境实际跑出后，按 `FINAL_DELIVERY/EVIDENCE_MANIFEST.md` 的规则补入
SHA、环境、时间、日志路径与截图（截图文件名带 SHA 前 7 位）。

| 编号 | 需要的证据 | 状态 |
| --- | --- | --- |
| E2-10 | 训练闭环（登录→五阶段→追问→结果→画像→推荐） | PENDING（新 SHA 上重拍） |
| E2-11 | 管理员创建题本 → 两名不同教师各自审核 → 管理员发布 | PENDING |
| E2-12 | 学生 T0 独立在线作答（阶段信息隔离、提交成功页不显示答案/评分） | PENDING |
| E2-13 | 双教师盲评（匿名队列、互不可见、评分锁定）与分歧裁决 | PENDING |
| E2-14 | 研究管理（批次、整批随机化记录、题本顺序、受控导出、数据冻结） | PENDING |
| E2-15 | 数据域隔离回归测试（考核不写 Score/画像/推荐，不调用 AI） | PENDING（看 `TEST_REPORT.md`） |
| E2-16 | 迁移升级/降级/再升级记录 | PENDING |
| E2-17 | 7 批 49 名**测试**学生、98 份答卷批量流程（标 `TEST/SYNTHETIC`） | PENDING |
| E2-18 | 版本验收：`GET /api/system/version` 与运行 SHA 一致 | PENDING（需获授权的部署） |

## 三、仍需外部确认

| 项目 | 说明 |
| --- | --- |
| 展示授权 | 院系/单位确认可在申报材料中使用系统截图 |
| 教师实际演示反馈 | 需真实教师观摩后填写；未观摩前不得写「已完成教师观察」 |
