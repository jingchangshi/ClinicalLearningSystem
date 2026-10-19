# EXAM_SECURITY_FINAL——正式考核题本的公开/私有分离（R9 收敛轮）

> 状态：**TECHNICAL_DELIVERABLE**，日期 2026-10-19，工作树 `feat/clinpath-r9-finalization`。
> 证据代码基线：`1a3663a`（发布前保密扫描）、`7ac099d`（泄漏审计五渠道分离）；两者都是本轮的脚本提交。
> 本文件是任务书 §5（P0 正式考核题本保密）与 §11（发布前保密扫描）的结论文件。
> 配套：`EXAM_SECURE_IMPORT_SPEC.md`（安全导入规范）、`EXAM_FORM_REAUTHORING_REQUIREMENTS.md`（新题本命制要求）、
> `FORM_ORDER_DECISION_OPTIONS.md`（题本顺序决策）、`../../workpackages/A_cases/LEAKAGE_AUDIT_DRAFT.md`（泄漏审计明细）。
> 真人事项：`R9_HUMAN_ACTION_CHECKLIST.md` H09/H14/H18—H21。

## 0. 三句实话（先读这三句，再读后面的能力边界）

1. **现有公开稿已经暴露**：`jingchangshi/ClinicalLearningSystem` 是公开仓库，其历史中已包含 A01 考核卡片（诊断逻辑、
   逐项计分）、A02 旧版与新版草案、两份待审载荷、锚点一致性表与样例题本答案。**删除文件不能消除既往暴露，
   本仓库的历史未被改写，也不应被改写。**
2. **新的保密题本尚不存在**：A01/A02 的新保密版本**没有**被命制、**没有**经过任何真实教师审核、**没有**做过难度校准。
   这是真实作者（医师）与真实审核人的任务，Agent 不能代替（见 `EXAM_FORM_REAUTHORING_REQUIREMENTS.md` §8）。
3. **静态扫描通过 ≠ 不存在泄漏风险**：本轮扫描只覆盖渠道 T（学生可见静态文本）。公开历史（G）、生产实际病例（P）、
   批内口头传播（W）与跨批传播（C）都**没有**被这一次扫描覆盖，其中 P 到目前为止**仍未核查**。

## 1. §5.1 审计：本轮分支新增了什么，公开风险如何标注

### 1.1 本轮新增内容（不含任何题本内容）

| 路径 | 类型 | 是否含题本/答案/真实数据 |
| --- | --- | --- |
| `scripts/grant/publish_safety_scan.py` | 发布前保密扫描（新） | 否（只含规则与"已公开样例"的路径与哈希记录） |
| `backend/tests/test_publish_safety_scan.py` | 上述扫描的测试（新） | 否（所有敏感样例都由字符串拼接构造，避免自身成为命中） |
| `scripts/grant/audit_exam_leakage.py`（扩展） | 泄漏审计：五渠道分离、`--history` 只读历史核查 | 否 |
| `backend/tests/test_exam_leakage_audit.py`（扩展） | 渠道矩阵与措辞限制的测试 | 否 |
| `FINAL_DELIVERY/EXAM_SECURITY_FINAL.md`（本文件） | 结论 | 否 |
| `FINAL_DELIVERY/EXAM_SECURE_IMPORT_SPEC.md` | 导入规范 | 否（只有流程与路径约定） |
| `FINAL_DELIVERY/EXAM_FORM_REAUTHORING_REQUIREMENTS.md` | 命制要求 | 否（只有要求与反例，无题本内容） |
| `FINAL_DELIVERY/FORM_ORDER_DECISION_OPTIONS.md` | 决策文件 | 否（只含设计算术与选项分析） |

结论：**本轮新增提交不包含未公开的正式题本、标准答案、完整评分锚点、真实学生资料、身份映射、
伦理材料中的个人信息、私密申报个人资料或服务器密钥**。这一结论由 §1.2 的扫描支持，而不是由人工目视得出。

### 1.2 发布前保密扫描（`scripts/grant/publish_safety_scan.py`）

**为什么需要它**：仓库是公开的、历史已含考核材料，唯一剩下的控制点是**提交边界**：任何敏感内容都不得进入新的提交。

**它拦截什么（`BLOCK`，退出码 1；路径规则无论是否本轮新增都拦）**

| 类别 | 规则要点 |
| --- | --- |
| 未公开正式考核题本 | 五阶段评估题本结构（≥5 阶段、每阶段 `clinical_information`+`question`）或考核类路径，且**不在已记录的暴露清单**中；新增路径一律拦 |
| 标准答案或完整保密评分锚点 | 考核类文件中的 `answer_key`/`standard_diagnosis`/`标准答案`/`评分锚点`/`rubric` 等标记 |
| 真实学生资料 | 身份证（18 位）、手机号（11 位）、`学号：<数字>` 等标识模式 |
| 身份映射 | 数据文件中把研究编号与姓名/学号配成一条记录（`study_id`×`学号/姓名`） |
| 伦理材料中的个人信息 | 已填写的签名栏（`学生签名：<非占位符> 日期`）；公开材料必须用 `【待填：…】` |
| 私密申报书个人资料 | `申报书/汇总表/简历/application_text` 类文件中出现具名申请人/主持人 |
| 服务器密钥 | 凭证型赋值（`JWT_SECRET=`、`LLM_API_KEY=`…，排除占位值）、私钥块（`-----BEGIN … PRIVATE KEY-----`）、`sk-`/`ghp_`/`AKIA`/`AIza` 型密钥 |
| 无法检查的内容 | 二进制（图片/DOCX/压缩包）内容不可读；**新加入的**二进制默认拦，需 `--accept-uninspected-binary` 明确人工确认 |

**为什么是"fail closed"（不会静默通过）**

- 无法确定扫描范围（不是 git 仓库、没有可扫描文件、空变更集、blob 读不到）→ **退出码 2**；
- 每次运行都打印**实际检查了多少个目标**、有多少个无法检查，以及本工具的局限；
- 唯一能"绕过"规则的方式是**被记录的决定**：已公开样例清单（`EXPOSED_DEV_SAMPLES`，含内容哈希）与
  合成测试夹具清单（`FIXTURE_PATHS`，含理由）；新增条目是人工决定，会留下 diff 记录。

**它不能做什么（必须与结论一起引用）**：静态文本扫描看不懂"换了说法、同一推理链"的题本；
**不会读图片、DOCX、PDF、压缩包内部**；**不能撤销既往暴露**（已推送内容永远在历史里）；
读不到仓库之外的文件（私有受控环境超出其范围）；无法观测题本是否被拍照或口头转述；
可能**落后于真实远端**——本地未 `git fetch` 时看不到远端比本地更新。

### 1.3 已记录的公开暴露清单（只记录，不阻止——因为阻止也无效）

扫描把下列**已经公开**的考核相关路径列为 `INFO`（`EXPOSED_DEV_SAMPLES`），逐条记录了 2026-10-19 的内容哈希；
将来若有人修改其中任一文件，扫描会提示"内容与暴露记录不一致，需人工确认未加入新的保密内容"：

```
docs/teaching_grant_2026/workpackages/A_cases/A01_assessment_UA.md
docs/teaching_grant_2026/workpackages/A_cases/A01_assessment_sicca.md
docs/teaching_grant_2026/workpackages/A_cases/A01_assessment_payload_DRAFT.json
docs/teaching_grant_2026/workpackages/A_cases/A02_assessment_payload_DRAFT.json
docs/teaching_grant_2026/workpackages/A_cases/A04_assessment_quality_control.md
docs/teaching_grant_2026/workpackages/A_cases/review_forms/ANCHOR_CONSISTENCY_TABLE.md
docs/teaching_grant_2026/workpackages/A_cases/review_forms/CASE_REVIEW_FORM_A01.md
docs/teaching_grant_2026/workpackages/A_cases/review_forms/CASE_REVIEW_FORM_A02.md
docs/teaching_grant_2026/workpackages/A_cases/review_forms/DIFFICULTY_MATCH_A01_A02.md
docs/teaching_grant_2026/workpackages/B_rubric/B02_sample_answers.csv
docs/teaching_grant_2026/workpackages/B_rubric/B02_sample_answers.md
```

这 11 条**允许继续留在仓库里**，条件只有一个：**必须清楚标明它们是开发/演示样例，永远不得当作保密考题使用**（任务书 §5.3(9)）。
扫描在它们被改动时要求保留暴露/演示标注；未标注的改动会被拦下。

## 2. §5.4 五类泄漏渠道分离（`audit_exam_leakage.py --channels`）

泄漏不是一个东西。把"静态扫描干净"当成"考试没有泄漏风险"是**错误**的，因此审计脚本现在把五类渠道分开报告，
每类有自己的方法、状态与局限：

| 渠道 | 内容 | 状态（本轮实跑） | 方法 |
| --- | --- | --- | --- |
| **T** | 学生可见训练库重叠 | **部分核查** | 静态扫描 seed_data、服务/前端文案、训练病例卡（本轮 1231 条） |
| **G** | 公开 GitHub 历史暴露 | **部分核查**（`--history`） | 只读列出本地远端跟踪引用中的考核相关路径；不 `fetch`、不改历史 |
| **P** | 当前生产数据库中的实际病例 | **未核查** | 需要生产库的脱敏目录导出（`--extra-json`）；**至今未提供** |
| **W** | 同批学生之间的口头传播 | **仅建模，无法观测** | 按设计计算批内知情者：X 学生 D6 的题本已被 3 名同批同学在 D1 作答、Y 学生 4 名，**49/49 受影响** |
| **C** | 跨轮转批次传播 | **仅建模，无法观测** | 第 b 批 D1 前已有 7(b−1) 名往届同学作答过两份题本（第 7 批 42 人；49 人中 42 人受影响） |

**措辞限制（脚本自己打印，任何文档不得违反）**

- 不得写成"正式考试无泄漏风险""已确认无泄漏"或等价表述；
- 静态扫描只能支持："**本次扫描范围内未发现与考核题高度相似或直接暴露答案的静态文本**"；
- 结论中必须逐项列出**未核查或无法观测**的渠道（本轮为 P/W/C；未加 `--history` 时还包括 G）；
- **生产实际病例目录仍未核查**：不得暗示线上病例库已经检查过。

`--history` 本轮的实际发现（只读、本地引用，8 个引用、11 条考核相关路径）：A01/A02 命题材料与 `B02_sample_answers.*`、
`review_forms/CASE_REVIEW_FORM_A0*.md`、`ANCHOR_CONSISTENCY_TABLE.md`、`DIFFICULTY_MATCH_A01_A02.md`
出现在 `origin/feat/clinpath-final-2026`、`origin/feat/clinpath-independent-assessment-2026`、
`origin/teaching-grant-2026-wpd` 等远端分支上；`A01_assessment_multisystem.md`（旧 A02 时代的文件）
出现在 `teaching-grant-2026-wpd`。这与 L-1 的结论一致：**暴露是既成事实**。

静态扫描本轮的结论（渠道 T）：**HIGH=0、MEDIUM=0、LOW=4**（4 条 LOW 全部是训练病例卡中的**阴性**描述
或分类标准框架，见泄漏审计 L-4）。这**只**说明"仓库内可见的静态文本里没有直接教出答案的内容"。

## 3. §5.2/5.3 公开与私有分离（已落地的部分）

| 内容 | 允许留在公开仓库 | 必须留在私有受控环境 |
| --- | --- | --- |
| 应用代码、数据库迁移 | ✅ | — |
| 不含真实考试答案的测试数据、合成数据 | ✅（须标注为合成/演示） | — |
| 明确标记的演示病例与已公开开发样例 | ✅（`EXPOSED_DEV_SAMPLES`，含哈希记录） | — |
| 申报项目的非敏感技术证据 | ✅ | — |
| **未公开的正式题本（含五阶段题面）** | ❌ | ✅ `~/.config/clinpath/exam_forms/`（mode 700/600） |
| **标准答案键 `answer_key`** | ❌ | ✅ 同上，独立列，学生路径不读取 |
| **完整评分锚点 `rubric`** | ❌ | ✅ 同上 |
| 真实教师审核原件（签名/日期） | ❌ | ✅ 私有 `reviews/` |
| 真实学生资料、身份映射（研究编号↔学号） | ❌ | ✅ 单位受控存储 |
| 伦理材料中的个人信息 | ❌ | ✅ 纸质/受控存储 |
| 服务器密钥 | ❌ | ✅ `~/.config/clinpath/*.env`（mode 600） |

- **怎么把题本带进系统**：见 `EXAM_SECURE_IMPORT_SPEC.md`（受控目录结构、读写权限、版本与哈希、
  导入运行手册、双教师审批门禁、导入后核验、泄漏事件响应）。该规范**尚未被执行过一次**，因为目前不存在可导入的题本。
- **新题本怎么命制**：见 `EXAM_FORM_REAUTHORING_REQUIREMENTS.md`（固定主题：A01 未分化多关节炎、
  A02 原因待查的干燥症状；反"换皮"要求 R1—R8；两位真实教师审核与 G 类问题；命制期间的保密要求）。
- **题本顺序带来的批内/跨批暴露**不由本文件决定：请见 `FORM_ORDER_DECISION_OPTIONS.md`（H14 决策门禁）。

## 4. 任何新的公开提交都必须遵守

1. 不得新增：未公开正式题本、标准答案或完整保密评分锚点、真实学生资料、身份映射、
   伦理材料中的个人信息、私密申报书完整个人资料、服务器密钥（任务书 §11）。
2. 推送前必须运行门禁（在仓库根目录）：

   ```console
   $ python3 -I scripts/grant/publish_safety_scan.py --scope staged          # 提交前：待提交的 blob
   $ python3 -I scripts/grant/publish_safety_scan.py --scope range origin/main..HEAD   # 或按范围
   $ python3 -I scripts/grant/publish_safety_scan.py --scope tree --show-allowlist     # 清点全仓库
   ```

   退出码 0 才可推送；1 表示存在 `BLOCK`；**2 表示无法确定扫描范围（等同失败，不得当作通过）**。
3. 已公开的样例**只**可作为演示：不得把 `A01_assessment_*`、`A02_assessment_*` 的公开稿说成保密试题或现行考核题本。
4. 不得改写 Git 历史、不得改远程可见性、不得自动合并 `main`、不得部署生产（任务书 §11）。
5. 建议（**未安装**，需申请人决定）：把门禁挂成 `pre-push` 钩子，例如在 `.git/hooks/pre-push` 中调用
   `python3 -I scripts/grant/publish_safety_scan.py --scope range origin/main..HEAD`。
   本轮**没有**安装任何钩子：安装属于仓库级配置，应由申请人决定。

## 5. 状态表（如实，供最终报告引用）

| 项 | 状态 |
| --- | --- |
| 公开仓库历史中的考核材料（A01 卡片、旧/新 A02 草案、载荷、锚点表、样例答案） | **已暴露，不可撤销**；已记为 `EXPOSED_DEV_SAMPLES`（11 条，含内容哈希） |
| A01/A02 新保密版本 | **未命制、未审核、未校准**（真人任务；Agent 不得撰写可发布题本） |
| 安全导入规范 | 已写出（`EXAM_SECURE_IMPORT_SPEC.md`），**未实测** |
| 发布前保密扫描 | 已实现并有测试；本轮对工作树扫描 `BLOCK=0` |
| 泄漏审计五渠道 | 已实现；T 部分核查、G 部分核查（`--history`）、P **未核查**、W/C 仅建模 |
| 生产实际病例目录 | **未核查**（需脱敏导出） |
| 平台当前数据库中的正式题本 | **不存在**（种子路径不创建题本；`seed_data --reset` 会清空考核表，生产禁用） |
| 本轮是否推送公开分支 / 是否部署 | **未推送、未部署**（由主负责人按门禁决定） |

## 6. 需要真人完成（与会话内 Agent 无关）

| # | 事项 | 责任方 | 阻塞 |
| --- | --- | --- | --- |
| 1 | 处置公开仓库暴露：改私有 或 移出考核材料；决定是否把 A01 与旧 A02 视为已暴露 | 申请人 / 研究负责人 | 申报引用方式（不得引用仓库地址） |
| 2 | 命制 A01'/A02'（必要时 B01'/B02'）并完成两位真实教师审核与难度校准 | 课题组 + 两位风湿科教师 | 研究启动 |
| 3 | 生产实际病例目录的脱敏导出（渠道 P） | 平台管理员 | 泄漏审计的完整性 |
| 4 | 题本顺序决策（H14） | 申请人 / 统计负责人 | 研究启动 |
| 5 | 伦理材料写明题本保密要求与泄漏事件处理 | 研究负责人 / 伦理委员会 | 研究启动 |
| 6 | 是否安装 pre-push 门禁钩子 | 申请人 | 仅影响流程自动化 |

## 7. 证据与可复现命令（本轮实际运行）

```console
$ python3 -I scripts/grant/publish_safety_scan.py --scope tree
publish-safety scan --scope tree
scope      : tree: 528 tracked + 7 untracked-not-ignored file(s), at their working-tree content (changed = differs from HEAD or untracked)
targets    : 535 (482 content-inspected, 53 not inspectable)
findings   : BLOCK=0 WARN=0 INFO=82

$ python3 -I scripts/grant/audit_exam_leakage.py --channels --history
Scanned 1231 items against 2 exam forms (categories: case, frontend, guideline, knowledge, service_text, skill, sp, training_card)
Findings: HIGH=0 MEDIUM=0 LOW=4
Leakage channels (five separate risks - a clean static scan covers channel T only):
  [T] 部分核查（有已知盲区） … items_scanned=1231
  [G] 部分核查（有已知盲区） … refs=8, exposed_paths=11 条考核相关路径（见 §2）
  [P] 未核查             … 生产实际病例目录未核查
  [W] 仅建模，无法观测    … students_with_any_within_batch_informant_at_D6=49
  [C] 仅建模，无法观测    … students_with_prior_cohort_informants_at_D1=42
Wording restriction (this scan cannot support more): …（见 §2）

# 门禁确实会拦住（在一次性克隆中植入三类敏感内容后扫描，不触碰本工作树）
$ python3 -I scripts/grant/publish_safety_scan.py --scope staged
findings   : BLOCK=6 WARN=0 INFO=0
[BLOCK] C01 服务器密钥 <- deploy/x.env:1
[BLOCK] P05 未公开正式考核题本 <- docs/private/confidential_exam_form.json
[BLOCK] E01 未公开正式考核题本 <- docs/private/confidential_exam_form.json
[BLOCK] E03 标准答案或完整保密评分锚点 <- docs/private/confidential_exam_form.json
[BLOCK] P02 身份映射 <- docs/private/linkage_table.csv
[BLOCK] C08 身份映射 <- docs/private/linkage_table.csv
EXIT=1

$ uv run --python 3.11 --with-requirements backend/requirements.txt pytest \
      backend/tests/test_publish_safety_scan.py backend/tests/test_exam_leakage_audit.py -q
27 passed … 15 passed（两个文件分别运行）
```

说明：
- `tree` 范围的数字随文档增删而变；同一次运行中"未检查内容"的 53 个目标是**已跟踪的二进制**
  （截图、DOCX、ZIP），它们的内容本轮无法用文本规则检查——已在状态表中如实标注，未声称已检查。
- 对**新加入**的二进制默认拦下；这一点由测试固定（`--accept-uninspected-binary` 才降为 WARN）。
- 第一版扫描在本仓库上出现了两类**文档误报**（表格里写变量名 `JWT_SECRET=`、文档描述签名栏规则本身），
  已在本轮修正（提交 `19e4daa`）：变量名后必须有真实值才算密钥，签名栏只有写出人名才算已填写。
  否则运维会把告警当噪声忽略，门禁就失去意义。
- 本轮没有在共享工作树里向索引植入过任何演示泄漏（避免影响其他并行工作）；上面的 6 条 `BLOCK` 证据来自一次性克隆。
