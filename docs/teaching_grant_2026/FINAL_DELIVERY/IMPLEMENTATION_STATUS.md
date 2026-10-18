# 实现状态（IMPLEMENTATION_STATUS）

> 快照：2026-10-18，已提交基线 `47f7e6d`（分支 `feat/clinpath-final-2026`）。
> 他人正在进行的未提交工作（如 `20261018_09` 硬化迁移、`backend/app/assessment/`）**不计入**「已实现」，
> 合并入库后由牵头成员更新本表。状态词：**已实现**＝已提交且有对应测试；**已提交未验证**＝代码在库、无通过的测试证据；
> **进行中**；**未开始**；**真实人员待办**。

| 阶段 | 内容 | 状态 | 证据 / 备注 |
| --- | --- | --- | --- |
| R0 | 基线审计、生产隔离 | 进行中（他人） | 见各成员报告；本成员未改动生产 |
| R1 | 独立考核数据模型与权限 | **已提交未验证** | `assessment_models.py`、`routes/assessments.py`、迁移 `_08`；基线 `test_reject_unapproved_form` 因测试内未定义变量失败（见 TEST_REPORT） |
| R2 | 学生在线作答、可靠性、页面 | **已提交未验证** | `frontend/app/(main)/student/assessments/` 已存在；断网/幂等/窗口策略属硬化工作（进行中） |
| R3 | 双教师盲评、裁决、一致性 | 部分 | 盲评队列与评分接口已提交；裁决与锁定在硬化工作中；ICC 纯函数已提交（`research/agreement.py`，有测试） |
| R4 | 7 批 49 人研究管理 | 部分 | 整批随机化（35 种）、题本顺序、冻结哈希的纯函数已提交（`research/`，有测试）；DB 接线与批次管理 UI 待验收 |
| R5 | 病例与医学质控 | 草案 | 6 例病例卡 `PENDING_REAL_REVIEW`；新 A02 为干燥症状待查；见 `CASE_REVIEW_STATUS.md` |
| R6.1/6.2 | 精确统计 | **已实现（纯函数 + 测试）** | `research/exact_permutation.py`、`tests/test_research_exact_permutation.py`；双侧 P 唯一定义见 SAP §3.5 |
| R6.3 | E1—E5 证据包 | **已更新（本成员）** | `evidence/E1…E5`；E2 的真实截图/运行记录标 PENDING 直至实际产生 |
| R6.4 | 合成 Demo | 保留 | `demo_research/synthetic_v1/` 未改动；`SYNTHETIC / SIMULATED_NOT_HUMAN` |
| R7 | 申报材料 | **草稿已交付（本成员）**；官方模板 **BLOCKED** | `APPLICATION_PACKAGE/`、`E5_04_application_text.md` |
| R8.1 | 后端测试 | 已执行（中期） | 见 `TEST_REPORT.md`：`f7f737c` 329 通过 / 1 失败 / 1 xfail（`47f7e6d` 为 307 / 5 / 1） |
| R8.2 | 前端/浏览器 | **未执行（本成员）** | worktree 未安装 `node_modules`，`tsc: not found`，不得视为通过 |
| R8.3 | 迁移验收 | **未执行（本成员）** | 他人负责；部分迁移测试在基线失败 |
| R8.4 | 生产保护 | 遵守 | 未合并 `main`、未部署、未对生产库迁移 |
| R8.5 | 最终交付文件 | 骨架已建 | 本目录 11 个文件；每个文件只有一个版本 |

## 技术开发完成 ≠ 研究就绪

即使上表全部转绿，下列仍为**真实人员待办**（见 `HUMAN_ACTION_CHECKLIST.md`）：
两位教师的病例与量表审核、教研室批次日期与随机化执行方式、21 名实习生构成、伦理意见、单位经费与签章。
