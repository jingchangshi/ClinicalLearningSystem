# STATUS — E5 研究方案证据包

**日期**：2026-10-18
**工作目录**：`/home/jcshi/workspace/clinical_learning_system`
**当前 SHA**：`1d4ef4823c75fb9d89a7aec734b8b84d0bfa5c41`（`main`；工作树含未提交改动，见下）
**状态**：文件已写完；**所有研究内容均为"拟开展"**，没有任何真实研究结果。

---

## 1. 交付文件

| # | 文件 | 字数（字符） | 状态 |
| --- | --- | --- | --- |
| 1 | `E5_01_research_protocol.md` | 23,650 | ✅ 完成 |
| 2 | `E5_02_SAP_statistical_analysis_plan.md` | 20,215 | ✅ 完成 |
| 3 | `E5_protocol_data_dictionary.md` | 22,097 | ✅ 完成 |
| 4 | `E5_03_ethics_privacy.md` | 15,239 | ✅ 完成 |
| 5 | `E5_04_application_text.md` | 22,607 | ✅ 完成 |
| 6 | `STATUS_E5.md`（本文件） | — | ✅ |
| 7 | `scripts/grant/sample_size.py` | — | ✅ 已实际运行，输出已粘贴进 E5-02 |

---

## 2. 实际运行的命令与真实输出

### 2.1 合成演示测试（确认演示层仍然可用）

```bash
cd backend
uv run --python 3.11 --with-requirements requirements.txt pytest -q tests/test_demo_research.py
```

**真实输出**：

```
................                                                         [100%]
=============================== warnings summary ===============================
../../../.cache/uv/archive-v0/dvAqh2s2pOALJYP3/lib/python3.11/site-packages/starlette/testclient.py:40
  /home/jcshi/.cache/uv/archive-v0/dvAqh2s2pOALJYP3/lib/python3.11/site-packages/starlette/testclient.py:40: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = typing.Callable[[], typing.ContextManager[DeprecationWarning]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
16 passed, 1 warning in 2.80s
```

### 2.2 样本量计算（stdlib only，Python 3.11）

```bash
python3.11 -I scripts/grant/sample_size.py
```

**真实输出（完整）**：

```
==========================================================================
E5 样本量可行性计算   α=0.05（双尾）  power=0.80  两组等量
==========================================================================
z_(1-α/2) = 1.959964
z_(1-β)   = 0.841621
(z_(1-α/2)+z_(1-β))^2 = 7.848880
2*(...)^2 = 15.697759   → n/组 = 15.6978 / d^2

--------------------------------------------------------------------------
[1] 正态近似 vs t 分布修正（d = 组间差值 / 变化量标准差）
--------------------------------------------------------------------------
    d      n/组(正态)     n/组(t修正)     +15%脱落      合计N
 0.40        98.11           99        117      234
 0.50        62.79           64         76      152
 0.60        43.60           45         53      106
 0.70        32.04           33         39       78
 0.80        24.53           26         31       62
 1.00        15.70           17         20       40

--------------------------------------------------------------------------
[2] 可行性反推：若只能招到 n/组，80% 功效能检出多大的 d？
--------------------------------------------------------------------------
   n/组         最小可检出d     d=0.50功效     d=0.60功效     d=0.70功效
    20          0.886        0.329        0.449        0.575
    25          0.792        0.404        0.544        0.679
    30          0.723        0.474        0.626        0.761
    40          0.626        0.597        0.756        0.873
    45          0.591        0.650        0.805        0.909
    60          0.511        0.776        0.904        0.968
    90          0.418        0.916        0.980        0.997

--------------------------------------------------------------------------
[3] 若按轮转班次整群分配（每群 m=30 人）
--------------------------------------------------------------------------
    d    rho       设计效应       群数/组       人数/组
 0.50   0.05       2.45          6        180
 0.50   0.10       3.90          9        270
 0.60   0.05       2.45          4        120
 0.60   0.10       3.90          6        180
 0.70   0.05       2.45          3         90
 0.70   0.10       3.90          5        150

--------------------------------------------------------------------------
[4] ANCOVA 相对变化量检验的效率比 sqrt((1+rho)/2)（rho = 前后测相关）
--------------------------------------------------------------------------
rho=0.30  方差比=0.650  n 可乘以 0.650  （例：t修正 64/组 → 42/组）
rho=0.50  方差比=0.750  n 可乘以 0.750  （例：t修正 64/组 → 48/组）
rho=0.70  方差比=0.850  n 可乘以 0.850  （例：t修正 64/组 → 55/组）

--------------------------------------------------------------------------
[4b] 以原始分标准差表达的效应量 → ANCOVA 规划用 d_adj = d_raw / sqrt(1-rho)
--------------------------------------------------------------------------
 d_raw   rho   d_adj     n/组(t修正)     +15%脱落
  0.40  0.30   0.419           91        108
  0.40  0.50   0.462           75         89
  0.40  0.70   0.560           51         60
  0.50  0.30   0.524           59         70
  0.50  0.50   0.577           48         57
  0.50  0.70   0.700           33         39
  0.60  0.30   0.629           41         49
  0.60  0.50   0.693           34         40
  0.60  0.70   0.840           24         29

--------------------------------------------------------------------------
[5] 合成演示数据为什么不能提供效应量（只读 demo_research/synthetic_v1）
--------------------------------------------------------------------------
      CBL: n= 30  提升均值=4.33  提升标准差=4.05
 CLINPATH: n= 30  提升均值=20.15  提升标准差=4.78
提升差 = 15.82   合并标准差 = 4.43   折算 d = 3.57
说明：该 d 是生成脚本**预先设定**的（nominal 6 vs 18），不是估计值，
      只能证明统计流程可跑通，不能用于样本量规划。
```

### 2.3 演示数据交叉核对（一次性核对脚本，未落盘）

```bash
python3.11 -I <<'EOF'
# 读取 participants/assessments/sessions/reasoning_steps，核对计数与均值
EOF
```

**真实输出**：

```
participants 60 unique ids 60
groups Counter({'CLINPATH': 30, 'CBL': 30})
cohorts Counter({'教学批次A': 30, '教学批次B': 30})
assessments 120 timepoints Counter({'T0': 60, 'T1': 60})
sessions 180 reasoning rows 450
CBL 30 58.81 63.13
CLINPATH 30 61.44 81.58
students with both 60
sessions per student Counter({3: 60})
reasoning per student Counter({15: 30})
completed Counter({'YES': 180})
eval mode Counter({'SIMULATED_AI': 90, 'NO_AI': 90})
weeks Counter({'1': 60, '3': 60, '5': 60})
case_code Counter({'SLE': 60, 'RA': 60, 'AAV': 60})
assessment_case Counter({'ASSESS-A': 60, 'ASSESS-B': 60})
rater_origin Counter({'SIMULATED_NOT_HUMAN': 120})
ai_scoring_used Counter({'NO': 120})
```

**与 `metrics_SYNTHETIC.json` 的对照**：

| 指标 | JSON | 独立复算 | 一致 |
| --- | --- | --- | --- |
| CBL n | 30 | 30 | ✅ |
| CBL pre_mean | 58.81 | 58.81 | ✅ |
| CBL post_mean | 63.14 | 63.135（round→63.14） | ✅ |
| CBL gain_mean | 4.33 | 4.325（round→4.33） | ✅ |
| CBL gain_sd | 4.05 | 4.0534 | ✅ |
| CLINPATH n | 30 | 30 | ✅ |
| CLINPATH pre_mean | 61.44 | 61.4367 | ✅ |
| CLINPATH post_mean | 81.58 | 81.5833 | ✅ |
| CLINPATH gain_mean | 20.15 | 20.1467 | ✅ |
| CLINPATH gain_sd | 4.78 | 4.7756 | ✅ |
| n_assessments | 120 | 120 | ✅ |
| n_learning_sessions | 180 | 180 | ✅ |
| n_synthetic_reasoning_steps | 450 | 450 | ✅ |
| rater_origin | — | 120/120 `SIMULATED_NOT_HUMAN` | ✅ |
| ai_scoring_used_for_primary_outcome | — | 120/120 `NO` | ✅ |

**结论**：E5 文件中引用的每一个演示数字都来自上述 JSON/CSV 或本次复算，
没有引用文件中不存在的数字。

### 2.4 专家审核表核对

```bash
python3.11 -c "
import csv
with open('demo_research/synthetic_v1/templates/expert_review_BLANK.csv',encoding='utf-8-sig') as f: r=list(csv.DictReader(f))
print('rows',len(r)); print(set(x['final_approval'] for x in r)); print(set(x['review_origin'] for x in r))
"
```

**真实输出**：

```
rows 12
{'PENDING_REAL_REVIEW'}
{'REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED'}
```

→ 12 行全部待审核。E5 文件中所有"未完成专家审核"的表述与此一致。

### 2.5 禁用表述扫描

```bash
grep -n "我们的研究\|研究发现\|已完成专家审核\|已完成两名\|结果显示\|显著提升\|证明平台有效" *.md
```

**真实输出**（只命中提交前检查清单里的反面示例，无正文违规）：

```
E5_04_application_text.md:366:- [ ] 全文没有"我们的研究发现""结果显示""P<0.001 证明"等已完成时态的效果表述；
E5_04_application_text.md:368:- [ ] 没有声称已完成专家审核；
```

### 2.6 演示数据的前后测相关（用于说明"合成数据不能给 ρ 先验"）
```bash
python3.11 -I -c "... statistics.correlation(pre, post) ..."
```

**真实输出**：

```
pre-post r all: 0.709
CBL r= 0.89
CLINPATH r= 0.852
```

→ 这些相关系数同样是生成器设定的结果，E5-02 中**没有**用它们作为 ρ 的先验，
只在 §7.5 要求用预试验估计。

### 2.7 申报书各栏目汉字数实测

```bash
python3.11 -I -c "统计 E5_04 各栏目汉字数（不含代码块）"
```

**真实输出**：

```
   219 汉字  # E5-04 申报书可直接使用的文字
  1287 汉字  栏目一：立项依据（建议 1500–2000 字）
   648 汉字  栏目二：研究内容（建议 1200–1600 字）
   963 汉字  栏目三：研究基础（建议 1000–1400 字）
   968 汉字  栏目四：研究方案（建议 1500–2000 字）
   390 汉字  栏目五：预期成果（建议 600–900 字）
   590 汉字  栏目六：可行性（建议 800–1200 字）
   357 汉字  栏目七（可选）：研究基础中的"平台与研究数据采集前期基础"单段版
   385 汉字  附：字数预算与提交前检查
    88 汉字  附：可直接引用的证据路径
```

→ 正文六栏合计 4846 汉字，低于 6600–9100 的建议区间。
E5-04 已如实写明需要扩写的栏目与可扩写的内容，**没有**用重复段落凑字数。

---

## 3. 关键设计决定（供评审复核）

| 决定 | 理由 | 文件位置 |
| --- | --- | --- |
| 两组前后测、整群分配 | 个体随机化会因同班同伴外溢污染对照组 | E5-01 §3.2 |
| 主分析 ANCOVA + HC3 | 基线不平衡 + 异方差 + 量表边界效应 | E5-02 §2.2–2.4 |
| 六维度用 BH，主要结局不校正 | 单一主要结局；六维为一个族 | E5-02 §6 |
| 样本量用 t 修正而非只看正态近似 | 小样本下正态近似低估 n（64 vs 62.79） | E5-02 §7.1 |
| 明确写出整群设计效应可能使研究不可行 | 30 人/班 × ICC 0.05 需约 180/组 | E5-02 §7.3 |
| 不提供效应量估计 | 无真实前测；合成数据效应是输入参数 | E5-02 §7.5、§8 |
| 真实数据字段与合成字段**列名不同** | 误合并会在列名层面暴露 | 数据字典 §5 |
| 同意建为事件表而非状态字段 | 撤回与版本变更可审计 | 数据字典 §3 |

---

## 4. 发现的不一致（需要人决策，未擅自修改代码）

### 4.1 六维度权重两套并存

| 位置 | 权重（医学知识/关键信息/鉴别诊断/证据整合/临床决策/循证） |
| --- | --- |
| `backend/app/services/scoring_llm.py` `WEIGHTS` | 0.20 / 0.20 / 0.20 / 0.15 / 0.15 / 0.10 |
| `demo_research/synthetic_v1/generate_demo.py` `DIMS` | 0.10 / 0.20 / 0.25 / 0.15 / 0.20 / 0.10 |

E5 文件中已把它列为"必须在 T0 前固定"的事项（E5-01 §13 注、数据字典 §8、E5-02 §11）。
**没有修改任何代码或演示数据**，因为修改会改变已经交付的演示截图与 SHA。

### 4.2 `evaluation_mode` 枚举在演示数据与平台代码中不一致

| 位置 | 取值 |
| --- | --- |
| 平台 `scores.evaluation_mode` | `ai` / `rule_fallback` |
| 合成演示 `learning_sessions_SYNTHETIC.csv` | `SIMULATED_AI` / `NO_AI` |

演示数据是独立数据集，两者不必相同；但真实研究的数据字典必须统一，
E5 数据字典 §5 已规定真实研究用 `ai` / `rule_fallback` / `no_ai`。

### 4.3 任务说明中提到的 `README_先读.md` 不在解压目录

`demo_research/synthetic_v1/` 中没有该文件；它在压缩包
`docs/ClinPath_WPD_完整工作包D.zip` 内（`clinpath_wpD_demo/README_先读.md`）。
已用 `unzip -p` 只读读取，**没有解压到工作树**，避免产生未跟踪文件。
E5 文件引用了该 README 的"准确表达/不能写"段落，并与其口径一致。

---

## 5. 只能由用户/单位提供的内容（E5 文件已全部标为占位符）

### 5.1 教学单位

| # | 事项 | 影响 |
| --- | --- | --- |
| 1 | 每个轮转班次实际人数 | 决定方案 A/B/C |
| 2 | 每学年班次数与排课 | 决定能否达到 60/组 |
| 3 | 风湿免疫见习轮转周数、每周课时 | 训练剂量与 T0/T1 时点 |
| 4 | 分配单位：班次 or 班次内小组 | **最关键**：决定设计效应与样本量 |
| 5 | 班次分配方式与执行人 | 能否声称分配隐藏 |
| 6 | 可参与带教教师人数与排班 | 评分者、裁决者是否充足 |
| 7 | 是否允许对照组延迟开放 | 对照定义 |
| 8 | 六维度权重选定 | 结局总分如何计算 |
| 9 | 学生课程成绩是否与参与挂钩（建议不挂钩） | 伦理与自愿性 |

### 5.2 伦理与科研管理

| # | 事项 |
| --- | --- |
| 10 | 伦理委员会名称、受理编号、批件号、批件日期与有效期 |
| 11 | 审查类型（简易审查 / 豁免签署）由委员会决定 |
| 12 | 研究数据存储系统与保存年限 |
| 13 | 单位支持函/承诺书（**本文件不代拟**） |
| 14 | 研究负责人与团队名单、分工、利益冲突声明 |
| 15 | 模型提供商数据处理协议的实际条款 |

### 5.3 研究执行

| # | 事项 |
| --- | --- |
| 16 | 预注册平台（ChiCTR / OSF）与时间 |
| 17 | 预试验是否开展、规模（用于估计 ρ 与提升量标准差） |
| 18 | 统计顾问 / 双人复算安排 |
| 19 | 评分者分歧裁决阈值（建议 ≥10 分） |
| 20 | 目标期刊 |

---

## 6. 未做的事（如实说明）

- **未**运行完整后端测试套件（只运行了 `tests/test_demo_research.py`，16 项通过）。
  E5 交付物是文档，没有改动后端代码；`scripts/grant/sample_size.py` 是新增的独立脚本，
  不被应用导入，不影响测试。
- **未**运行前端 typecheck/lint/build 与 Playwright。同样因为本次没有改动前端。
- **未**部署。本次没有生产变更。
- **未**提交 git。工作树中除本文件外还有他人的未提交改动（`backend/app/main.py`、
  `frontend/...`、`docs/ARCH.md` 等），不应由本任务一并提交。
- **未**修改 `demo_research/synthetic_v1/` 或任何演示数值。

> 若需要把 E5 纳入正式提交，建议只 `git add docs/teaching_grant_2026/evidence/E5_protocol/
> scripts/grant/sample_size.py`，与演示层改动分开提交。

---

## 7. 建议的下一步（按优先级）

1. **确定分配单位**（班次 vs 班次内小组）——这一项决定样本量是否可行，其余都可以后补；
2. 让教研室填 §5.1 的 1–9 项，特别是人数与班次数；
3. 固定六维度权重（§4.1），并同步到评分量表工作包 `B_rubric`；
4. 起草知情同意书（ICF-v1.0）并提交伦理；
5. 定稿 SAP 并预注册；
6. 若时间允许，做一个班次的单组预试验，估计 ρ 与提升量标准差，再回头修订样本量。

---

## 8. 事实来源索引

| 主张 | 来源 |
| --- | --- |
| 五步推理、作答唯一约束、提交幂等 | `backend/app/core/reasoning_steps.py`；`docs/ARCH.md` §6 |
| 形成性追问、泄漏防护、轮次上限 | `docs/ARCH.md` §6.1 |
| 能力投影 `0.7/0.3` | `backend/app/services/competency_projector.py` `UPDATE_WEIGHT = 0.3`；`docs/ARCH.md` §7 |
| 六维权重 | `backend/app/services/scoring_llm.py` `WEIGHTS` |
| 演示数据规模与均值 | `demo_research/synthetic_v1/metrics_SYNTHETIC.json`、`data/*.csv`（本次复算） |
| 演示隔离与标识 | `docs/ARCH.md` §18.2、§18.4；`backend/tests/test_demo_research.py` |
| 演示统计真值源 | `docs/ARCH.md` §18.3；`backend/app/services/demo_research.py` |
| 匿名研究导出 | `backend/app/routes/teacher.py` `/export/research-data[.csv]`；`docs/ARCH.md` §17.3 |
| 脱敏出口与限制 | `backend/app/core/deidentify.py`；`docs/ARCH.md` §10 |
| AI 审计字段 | `backend/app/models.py` `AIInvocation`；`docs/ARCH.md` §5.3 |
| 容量与降级实测 | `docs/PILOT_READINESS_REPORT.md` §6、§11；`docs/ARCH.md` §16 |
| 测试门禁 189 项 | `docs/PILOT_READINESS_REPORT.md` §11.1 |
| 专家审核 12 行待审核 | `demo_research/synthetic_v1/templates/expert_review_BLANK.csv`（本次核对） |
