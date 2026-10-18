# E4 前期验证（来源必须分离）

> 状态：**部分完成**。本目录把"真实运行"与"合成演示"分开引用，不合并计数。

## 4.1 教学闭环（真实系统运行，非教学效果）

| 证据 | 位置 | 性质 |
| --- | --- | --- |
| SLE 端到端走查 | `workpackages/C_workflow/C01_demo_walkthrough.md` | 验证栈真实运行 |
| 原始 HTTP 证据 | `workpackages/C_workflow/C02_evidence/` | 25 份原始响应 |
| 运行记录 | `workpackages/C_workflow/C02_run_record.md` | 含版本、账号、模型、评价模式 |
| 演示脚本与截图 | `workpackages/C_workflow/C04_screenplay.md` + 17 张截图 | 1440×900 |

**注意**：该次运行中评分走的是 `rule_fallback`（模型 4 次超时），
提问走的是真实模型。材料不得把该次评分写成 AI 评分。

## 4.2 合成模拟研究（60 名虚拟学生，非真实学生）

| 证据 | 位置 | 性质 |
| --- | --- | --- |
| 数据集 | `demo_research/synthetic_v1/` | `SYNTHETIC_DEMO_NOT_REAL_STUDENTS` |
| 页面与统计 | `/teacher/research-demo`；`workpackages/D_research_demo/` | 统计由 CSV 现算 |
| 一致性测试 | `backend/tests/test_demo_research.py` | 与离线工作簿逐项一致 |

**注意**：模拟的组间差异是生成时预设的，P 值不能作为教学效果证据。

## 4.3 数据完整性统计

| 项目 | 数值 | 来源 |
| --- | --- | --- |
| 虚拟学生 | 60（CBL 30 / ClinPath 30） | `participants_SYNTHETIC.csv` |
| 独立前后测 | 120（每人 T0/T1 各一） | `assessments_SYNTHETIC.csv` |
| 训练记录 | 180 | `learning_sessions_SYNTHETIC.csv` |
| 五阶段记录 | 450（90 会话 × 5） | `reasoning_steps_SYNTHETIC.csv` |
| 业务表污染 | 0（调用前后行数不变） | `test_demo_router_never_touches_the_database` |

## 4.4 仍需真实人员提供

- 真实教师对教学演示的观摩意见与签名（`workpackages/C_workflow/C04_screenplay.md` §4）。
- 如开展真实学生可用性试点：伦理审批与原始记录。
