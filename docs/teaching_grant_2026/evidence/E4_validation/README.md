# E4 教学工作流与演示（可复现步骤；合成/测试账号）

> 目的：让任何人能在**隔离环境**里按步骤重现「学生 T0 → 训练 → 能力画像 → 个性化推荐 → 教师干预 → T1 → 盲评 → 研究导出」。
> **所有账号与数据都是测试/合成的**，不是真实学生、不是真实教师。
> 真实教师尚未观摩演示，因此**不能声称已经完成教师观察**；观摩意见模板见 §6。
> 状态：§5 已有**真实运行记录**（提交 `375e197`，2026-10-18，隔离栈）。但仅限 `TEST`/`SYNTHETIC` 数据上的
> 软件验收；真实教师审核、真实学生与教学效果仍不存在，不得据此声称研究已启动。

## 1. 先读：三类数据，不得混用

| 类别 | 标签 | 来源 | 用途 |
| --- | --- | --- | --- |
| 60 名虚拟学生研究演示 | `SYNTHETIC / SIMULATED_NOT_HUMAN` | `demo_research/synthetic_v1/`（只读） | 展示导出与统计流程；**不是教学效果** |
| 软件验收用测试学生/教师（含 49 人 × 7 批的批量场景） | `TEST` | 隔离库中一次性创建 | 验证软件流程 |
| 真实研究数据 | `REAL` | 尚不存在 | 获伦理意见后才可产生 |

## 2. 隔离环境（不得触碰生产）

1. 使用独立 Git 工作目录（本分支 worktree）、独立数据库（`DATABASE_URL=/tmp/<随机目录>/accept.db`）、独立端口、独立构建目录（`NEXT_DIST_DIR=.next-accept`）；
2. **绝不**使用生产学生库，**绝不**覆盖生产 `frontend/.next`；
3. 账号：测试教师/管理员只经 `python -m app.manage_users create-teacher|create-admin` 创建，密码用一次性随机值，**不写入仓库**；
   测试学生由 seed 或脚本创建，并在姓名/备注中标 `TEST`；
4. 命令骨架（端口与路径示意，按实际调整）：

```bash
export DATABASE_URL=sqlite:////tmp/clinpath-e4/accept.db   # 一次性库
cd backend && uv run --python 3.11 --with-requirements requirements.txt alembic upgrade head
uv run --python 3.11 --with-requirements requirements.txt python -m app.manage_users create-teacher e4_teacher --name "测试教师A" --teacher-no TEST-A
uv run --python 3.11 --with-requirements requirements.txt python -m app.manage_users create-teacher e4_rater_b --name "测试教师B" --teacher-no TEST-B
uv run --python 3.11 --with-requirements requirements.txt python -m app.manage_users create-admin e4_admin
uv run --python 3.11 --with-requirements requirements.txt uvicorn app.main:app --host 127.0.0.1 --port 8205
cd ../frontend && NEXT_DIST_DIR=.next-accept INTERNAL_API_BASE_URL=http://127.0.0.1:8205 npm run build \
  && NEXT_DIST_DIR=.next-accept INTERNAL_API_BASE_URL=http://127.0.0.1:8205 npm run start -- --hostname 127.0.0.1 --port 8204
```

> 说明：测试账号必须明确**不是**真实临床教师，演示材料中以「测试教师 A/B」称呼。

## 3. 演示步骤（每步写明角色、页面/API、预期、留证）

| 步 | 角色 | 操作 | 预期（可核查） | 留证 |
| --- | --- | --- | --- | --- |
| 1 | 测试管理员 | `/teacher/assessment-admin` 用**已准备好的待审 JSON** 创建 A01、A02 题本 | 状态为待审；未经审核不可发布 | 截图 + `GET /api/assessments/forms/admin/all` |
| 2 | 测试教师 A、B（两个不同账号） | `/teacher/assessment-forms` 各自独立审核并批准 | 两个不同审核人记录；同一账号不能充当两人 | 审核记录 JSON |
| 3 | 测试管理员 | 核验后发布题本；发布后版本冻结 | 已发布版本不可静默修改 | 截图 |
| 4 | 测试管理员 | 创建 sitting：学生、研究批次、T0、题本（X/Y）、窗口、两名评分者 | 记录批次、组别、题本顺序 | sitting 列表 |
| 5 | 测试学生 | `/student/assessments` 在窗口内作答 T0；逐阶段保存与提交 | 只见当前阶段；不能提前访问后续阶段；无 AI 追问；提交后不显示答案/评分 | 截图；**不得出现任何 AI 调用记录** |
| 6 | （检查） | 查询训练表 | T0 后 `Score`、`CompetencyProfile`、`LearningRecommendation` 均无新行 | SQL/测试输出 |
| 7 | 测试学生 | 进入 ClinPath 训练：D2/D3 两个训练病例，五阶段 + 追问 | 产生形成性评分（来源：AI 或 `rule_fallback`，**必须显式标记**）与画像 | 会话 JSON、`ai_invocations` |
| 8 | 测试学生 | D4/D5：查看个性化推荐及理由 | 推荐可追溯到 D2/D3 的证据事件，不来自 T0 | `learning_recommendations` + 证据事件 |
| 9 | 测试教师 | 教师看板：查看薄弱维度，创建干预；复核形成性评分 | 干预含理由；复核保留原始 AI/规则分、确认人、时间 | 干预与复核 JSON |
| 10 | 测试学生 | D6：独立在线 T1（另一题本） | 同第 5 步；T1 同样不更新画像 | 截图 |
| 11 | 测试评分者 A、B | `/teacher/assessments` 匿名队列独立评分 | 看不到姓名/学号/组别/批次/时点，也看不到对方分数；提交后锁定 | 队列与评分截图 |
| 12 | 测试管理员/裁决人 | 分歧超阈值进入裁决；形成独立裁决记录 | 原始双评不被改写；最终成绩标明来源 | 裁决记录 |
| 13 | 测试管理员 | 受控导出研究数据，必要时冻结数据集 | 仅研究编码；`data_origin=TEST`；冻结后版本号与哈希可复现 | 导出 CSV（标 TEST）、冻结清单 |

批量版本（软件验收）：7 批 × 7 名**测试**学生、最多 98 份答卷、196 份评分——属 E2-17，结果标 `TEST/SYNTHETIC`，
**不得**写成 49 名真实见习生的教学效果，也不得改动旧版 60 人合成结果。

## 4. 60 人合成演示（单独陈述）

打开 `/teacher/research-demo`：页面顶部固定横幅 `SYNTHETIC / SIMULATED_NOT_HUMAN`；可下载 60 行 `SYNTHETIC` CSV。
统计由 CSV 现算，模拟的组间差异是生成时预设的，P 值**不能**作为教学效果证据。
说明性数据条目（60 名虚拟学生、120 次独立前后测、180 条训练记录、450 条五阶段记录、业务表污染 0）来自前几轮记录，
见 `../../workpackages/D_research_demo/`。

## 5. 运行记录（只在真实执行后填写）

完整记录见 **[`RUN_RECORD_2026-10-18.md`](RUN_RECORD_2026-10-18.md)**（提交 `375e197`，2026-10-18 16:27—16:31 UTC，
隔离栈 8400/8401 + `/tmp` 一次性库 + 刻意无模型密钥）。

| 步骤 | 执行人 | Git SHA | 环境 | 时间 (UTC) | 结果 | 证据路径 |
| --- | --- | --- | --- | --- | --- | --- |
| 1—4 题本到排考 | Agent（e2e） | `375e197` | 隔离栈 8400/8401 | 2026-10-18 16:27—16:31 | **通过**（R8.2 步骤 1—3） | `RUN_RECORD_2026-10-18.md` §5.1 |
| 5—6 学生 T0 + 隔离检查 | 同上 | `375e197` | 同上 | 同上 | **通过**（R8.2 步骤 4；学生读 AI 审计得 403） | 同上 |
| 7—9 训练、推荐、干预 | 同上 | `375e197` | 同上 | 同上 | **部分**：D2/D3 训练与 D4/D5 规则推荐已实测（R8.2 步骤 5）；**教师干预未执行** | 同上 |
| 10 T1 | 同上 | `375e197` | 同上 | 同上 | **通过**（R8.2 步骤 6） | 同上 |
| 11—12 盲评与裁决 | 同上 | `375e197` | 同上 | 同上 | **通过**（R8.2 步骤 7—8，`scoring_provenance=adjudicated`） | 同上 |
| 13 导出与冻结 | 同上 | `375e197` | 同上 | 同上 | **部分**：工作数据集导出已实测（R8.2 步骤 9）；**数据集冻结未执行** | 同上 |
| 49 人 × 7 批批量 | 同上 | `375e197` | 同上 | 同上 | **通过**（7/7 不变量） | `RUN_RECORD_2026-10-18.md` §6 |

> 仍然成立：真实教师审核、真实学生数据、教学效果、伦理意见**都不存在**。
> 上表全部为 `TEST` / `SYNTHETIC` 数据上的软件验收。
> 未执行项（训练套件 8 条、教师干预、数据集冻结、真实断网）见 `RUN_RECORD_2026-10-18.md` §8。

早期（前几轮）的真实运行记录仅覆盖训练闭环（工作包 C）与合成演示（工作包 D），见 `../../workpackages/C_workflow/C02_run_record.md`；
其中评分走 `rule_fallback`，提问走真实模型。

## 6. 教师观摩意见（真实教师填写；当前为空）

| 观摩教师（真实姓名/职称） | 日期 | 观摩内容 | 意见 | 签字 |
| --- | --- | --- | --- | --- |
| 【待填】 | 【待填】 | 【待填】 | 【待填】 | 【待签】 |

## 7. 仍需真实人员提供

- 真实教师对教学演示的观摩意见与签字；
- 如开展真实学生可用性试点：伦理意见及原始记录。
