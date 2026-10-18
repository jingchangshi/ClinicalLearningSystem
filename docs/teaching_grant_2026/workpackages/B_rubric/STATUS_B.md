# STATUS_B：六维形成性评价量表工作包（B01–B04）

| 项目 | 内容 |
| --- | --- |
| 工作包 | B（六维度形成性评价） |
| 仓库 | `/home/jcshi/workspace/clinical_learning_system` |
| 基线 commit | `a8aa65d`（分支 `teaching-grant-2026-wpd`；第二轮修复基线） |
| 完成日期 | 2026-10-18 |
| 总体状态 | **部分完成**：草案与工具已交付；真实教师审核与真实评分**阻塞** |
| 是否改动数据库/生产数据 | **否** |
| 是否声称真实教学效果或真实教师一致性 | **否** |

---

## 0. 第二轮（2026-10-18）与本工作包相关的变更

量表本身**未改**：权重仍为 `10/20/25/15/20/10`，状态仍为「待专家确认」。
本轮改的是**评分来源的标注**，见 `../SCORING_SOURCE_SPEC.md`：

- 平台形成性评分权重保持 `20/20/20/15/15/10`，**本轮未改**；
- 教师复核接口不再把 `rule_fallback` 的总分写进 `ai_score`，新增
  `baseline_score` / `baseline_source`（迁移 `20261018_07`）；
- 因此 B03 所说的「平台复核不是盲评」现在有字段层面的证据：复核记录会明确写出
  它对照的是 AI 分还是规则分。

## 1. 逐项状态

| 编号 | 交付物 | 状态 | 说明 |
| --- | --- | --- | --- |
| B01 | `B01_rubric_v0.1.md` | **完成（草案）** | 六维、权重、定义、证据来源、低/中/高三档行为锚点、加权公式、边界条件、`rubric-v0.1`、形成性 vs 研究主结局对照。待真实教师签字。 |
| B02 | `B02_sample_answers.md` + `.csv` | **完成** | 16 份模拟作答，覆盖 6 个病例、5 个推理阶段；60–160 字；无任何分数列。 |
| B03 | `B03_export_template.md` + `B03_rating_template.csv` | **完成（空白表）** | 32 行 = 16 样本 × 2 评分者槽位；`rater_origin=REAL_BLINDED_RATER`；身份/日期留空。已写明平台“复核确认”会回写画像、不是盲评。 |
| B04 | `scripts/grant/rubric_agreement.py` + 模板 + 模拟演示 + `B04_DEMO_OUTPUT.md` | **完成（脚本已实测）** | 仅标准库；均值/SD、加权总分、精确/±5/±10 一致性、ICC(2,1)、三档 Cohen's kappa、自检；无真实评分时退出码 2 且不出数。 |
| — | `STATUS_B.md` | 本文件 | — |

## 2. 创建的文件

全部为新增文件，未修改任何既有文件、数据库或生产数据。

```text
docs/teaching_grant_2026/workpackages/B_rubric/
├── B01_rubric_v0.1.md              # 量表草案 v0.1
├── B02_sample_answers.md           # 16 份模拟作答（人读）
├── B02_sample_answers.csv          # 同上的机读版（4 列，无分数）
├── B03_export_template.md          # 导出规范 + 盲评流程 + 平台限制
├── B03_rating_template.csv         # 空白评分表，32 行
├── B04_agreement_template.csv      # 分析用空白表，32 行（与 B03 同结构）
├── B04_simulated_rater_demo.csv    # 模拟评分者演示输入，32 行
├── B04_DEMO_OUTPUT.md              # 脚本说明 + 真实运行输出
└── STATUS_B.md                     # 本文件
scripts/grant/
└── rubric_agreement.py             # 一致性分析脚本（Python 3.11 标准库）
```

校验和（sha256，便于复核）：

```text
7bf60aaf1b46a344a57be2a6e5b4cbe3ba0cadc37a57c75f1b48ed05d0a04e95  scripts/grant/rubric_agreement.py
697207f444d86ff4132c0a7bc355e87b6d6fed076f2ce415d00eaf70204047d0  docs/teaching_grant_2026/workpackages/B_rubric/B02_sample_answers.csv
10799fa284fe5064b4a32a8c9932c0a08f0d18be0b29876638acdf35f066be80  docs/teaching_grant_2026/workpackages/B_rubric/B03_rating_template.csv
10799fa284fe5064b4a32a8c9932c0a08f0d18be0b29876638acdf35f066be80  docs/teaching_grant_2026/workpackages/B_rubric/B04_agreement_template.csv
0a06ac2f4f8829d2c485e1d80585fe2a128df4a028afdd8c508834e109666a9b  docs/teaching_grant_2026/workpackages/B_rubric/B04_simulated_rater_demo.csv
```

## 3. 实际执行的命令与真实结果

运行环境：Python `3.11.15`，仓库 `1d4ef48`。

### 3.1 脚本自检

```bash
python3.11 -I scripts/grant/rubric_agreement.py --self-check
```

真实输出（退出码 0）：

```text
ICC(2,1) / Cohen's kappa 自检：
  [PASS] 完全一致的评分 ICC=1      得到 1.0
  [PASS] 手算样例 ICC=280/284   得到 0.9859154929577463，期望 0.9859154929577465
  [PASS] 系统性偏移使 ICC<1       得到 0.9302325581395349
  [PASS] 受试者重排不改变 ICC       得到 0.9859154929577463
  [PASS] 手算样例 kappa=0.5238  得到 0.523809523809524，期望 0.523809523809524
  [PASS] 完全一致的 kappa=1      得到 1.0
  [PASS] 低/中/高分箱边界          39→low, 40→mid, 69→high 边界正确
  [PASS] 加权总分=70.3          得到 70.3
  [PASS] 权重和=1.00           得到 1.00
```

> 自检最初**捕获了两个真实缺陷**并被修正：
> (a) kappa 手算样例的期望值算错（已改为 0.5238 并重新推导）；
> (b) Python `round()` 的银行家舍入使 `70.25 → 70.2`，与 B01 声明的
> `70.3` 不一致——已改为 `Decimal` + `ROUND_HALF_UP`，并在 B01 中注明。

### 3.2 无真实评分时必须拒绝出数

```bash
python3.11 -I scripts/grant/rubric_agreement.py \
  docs/teaching_grant_2026/workpackages/B_rubric/B04_agreement_template.csv
```

真实输出（退出码 **2**）：

```text
尚无可分析的真实评分（REAL_BLINDED_RATER=0），不得报告真实教师一致性
（文件：docs/teaching_grant_2026/workpackages/B_rubric/B04_agreement_template.csv；REAL_BLINDED_RATER 有效评分行 = 0）
```

### 3.3 模拟评分者必须显式 `--demo`

```bash
python3.11 -I scripts/grant/rubric_agreement.py \
  docs/teaching_grant_2026/workpackages/B_rubric/B04_simulated_rater_demo.csv
```

真实输出（退出码 **4**）：

```text
输入文件是模拟评分者数据（SIMULATED_NOT_HUMAN）。
如确需演示脚本，请显式加 --demo；输出会被标注为模拟示例。
```

### 3.4 模拟评分者演示（唯一会产生数字的路径）

```bash
python3.11 -I scripts/grant/rubric_agreement.py \
  docs/teaching_grant_2026/workpackages/B_rubric/B04_simulated_rater_demo.csv --demo
```

退出码 0。真实输出全文见 `B04_DEMO_OUTPUT.md` 第 5 节；首行为
`模拟评分者示例｜SIMULATED_NOT_HUMAN｜不是真实教师一致性`，
末行重复同一横幅。演示结果显示 ICC 约 0.87–0.99、合并 kappa 0.581，
**这些数字只反映两个模拟器围绕同一中心值抽样，不代表任何人类评分者。**

### 3.5 其余护栏（已逐项实测）

| 场景 | 实测结果 |
| --- | --- |
| 同一文件混有真实与模拟评分 | 退出码 5，拒绝运行 |
| 只有 1 个样本具备完整双评分 | 退出码 2，提示至少需要 2 个样本 |
| 缺列 / 非 CSV / 非数字 / 越界 | 退出码 3 |
| 全部评分相同（方差为 0） | 正常退出，ICC 与 kappa 显示“不可计算”，不插补 |
| 缺一个评分者（B2-003） | 正常退出，该样本列入“已排除样本” |
| 真实评分缺 `rater_id` / `review_date` | 打印警告，继续分析 |

### 3.6 数据文件校验

```bash
python3.11 -I - <<'PY'   # 见下方结论
```

实际核验结果：

- `B02_sample_answers.csv`：16 行、4 列；无任何分数/total 列；
  作答长度 62–160 字（均值 111.1），全部落在要求区间；
  六个病例均被覆盖（T01–T04 各 3 份，A01–A02 各 2 份）；
  五个推理阶段全部出现；`source` 全为 `SYNTHETIC_FOR_RATER_CALIBRATION`。
- `B03_rating_template.csv` / `B04_agreement_template.csv`：32 行、14 列；
  16 个 `sample_id` 各出现 2 次；`rater_origin` 全为 `REAL_BLINDED_RATER`；
  `rubric_version` 全为 `rubric-v0.1`；所有身份、日期、分数列为空。
- `B04_simulated_rater_demo.csv`：32 行、14 列；`rater_id` 为
  `SIM_RATER_A` / `SIM_RATER_B`；`rater_origin` 全为 `SIMULATED_NOT_HUMAN`。

## 4. 需要明确记录的设计决定

### 4.1 平台现有权重与 `rubric-v0.1` 不一致

- `backend/app/services/scoring_llm.py` 的 `WEIGHTS` 为
  `20 / 20 / 20 / 15 / 15 / 10`。
- `backend/app/services/competency_projector.py` 的 `confirmed_total()`
  对六维取算术平均。
- 本量表为 `10 / 20 / 25 / 15 / 20 / 10`，加权求和。

因此**平台当前 `total_score` 不是 `rubric-v0.1` 总分**。B01 第 2 节已写明，
本工作包没有修改平台打分逻辑，也没有把两者描述为已对齐。
权重对齐应作为独立变更，附带测试与说明。

### 4.2 病例编号已与工作包 A 核对一致

B02 写作开始时 `docs/teaching_grant_2026/workpackages/A_cases/` 为空，
因此先按任务书约定编写；A 的病例卡落盘后已核对
`A01_case_index.md`，六个编号与主题**一致**
（CASE-T01 SLE / T02 RA / T03 AAV / T04 IIM / A01 UA / A02 AOSD+MAS 风险）。
A 的全部病例仍为 `PENDING_REAL_REVIEW`，因此 B02 中的对应关系仍属
**待真实教师审核**的约定，不是已审核结论。

### 4.3 模拟评分者未被改标

工作包 D 的 `SIMULATED_NOT_HUMAN` 只在 `B04_simulated_rater_demo.csv`
中出现，且脚本要求 `--demo` 才分析，输出首尾均带横幅。任何真实评分文件
若混入 `SIMULATED_NOT_HUMAN` 行会被整份拒绝（退出码 5）。

## 5. 阻塞项（等待真实教师）

| 阻塞项 | 需要谁 | 解除条件 |
| --- | --- | --- |
| B01 权重与锚点的专家确认 | 两位真实带教教师 | 填写并签署审核记录，注明日期 |
| B02 评分者校准 | 两位真实教师 | 先独立盲评 16 份模拟作答，再讨论 |
| 真实评分数据 | 两位真实教师 | 按 `B03_rating_template.csv` 提交，`rater_id` 匿名 |
| 真实一致性分析 | 研究协调人 | 收到 ≥2 个样本的完整双评分后运行 B04 |
| 平台权重对齐 | 工程 | 独立变更 + 测试 + 迁移说明（不在本工作包范围） |
| 平台盲法模式 | 工程/产品 | 目前不存在，研究评分只能离线 |

在上述条件满足前：

- **没有任何真实评分者一致性数值**；
- `B04_agreement_template.csv` 保持空白；
- 不得报告“真实教师一致性”、不得引用 B04 演示数字作为结果。

## 6. 未执行的事项（如实报告）

- 未运行后端测试、前端 typecheck/lint/build、Playwright：
  本工作包只新增文档、CSV 与一个独立脚本，未触及应用代码或 schema。
  若需要纳入仓库门禁，建议为 `rubric_agreement.py --self-check`
  增加一条 CI 步骤。
- 未提交 commit（工作区改动未暂存）。
- 未做部署，也不涉及生产环境。
