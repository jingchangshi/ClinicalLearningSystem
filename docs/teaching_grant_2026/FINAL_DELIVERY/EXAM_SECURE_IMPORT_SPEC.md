# EXAM_SECURE_IMPORT_SPEC——正式考核题本的安全导入规范（受控环境 → 平台）

> 状态：**SPECIFICATION_ONLY**，日期 2026-10-19，工作树 `feat/clinpath-r9-finalization`。
> 本文件规定**如何**把一份真实、未公开的正式考核题本带进受控环境并装入平台；它**不包含**任何题本内容，
> 也**没有**导入过任何题本——**目前不存在任何经过真实教师审核的正式题本**（见 `EXAM_SECURITY_FINAL.md`）。
> 配套文件：`EXAM_SECURITY_FINAL.md`（公开/私有分离结论）、`EXAM_FORM_REAUTHORING_REQUIREMENTS.md`（新题本命制要求）、
> `FORM_ORDER_DECISION_OPTIONS.md`（题本顺序决策）、`../../workpackages/A_cases/LEAKAGE_AUDIT_DRAFT.md`（泄漏审计）。
> 真人事项：`R9_HUMAN_ACTION_CHECKLIST.md` H09（教师审核）、H18（公开仓库暴露处置）。

## 1. 适用范围与不可协商的边界

**适用于**：CASE-A01、CASE-A02 以及任何备用/平行题本（如 `FORM_ORDER_DECISION_OPTIONS.md` 的 B01'/B02'）的**正式保密版本**，
包括其五阶段题面、标准答案键（`answer_key`）与评分锚点/量表（`rubric`）。

**不适用于**：训练病例（学生可见，公开无妨）、已公开的开发/演示样例（只能作为演示，见 §2.4）、合成演示数据。

**边界（违反即不得导入）**：

| 不得进入 | 原因 | 现有自动化检查 |
| --- | --- | --- |
| Git 仓库（公开远端） | 历史不可撤销，删除文件不能消除既往暴露 | `scripts/grant/publish_safety_scan.py`（推送前门禁） |
| `backend/app/seed_data.py` / 种子路径 | 种子数据是公开代码的一部分；且 `seed_data --reset` 会 `drop_all` 全部表（含考核表），题本会随重置消失 | 无（代码路径事实，见 §2.3） |
| 前端构建产物 / 静态 JSON | 打包后即随页面公开 | 无（当前前端不引用任何题本文件，见 §2.5） |
| 研究导出数据集 | 导出只允许题本**编码、版本与分数** | 数据字典（`E5_protocol_data_dictionary.md`） |
| 申报材料、演示截图、给学生的说明 | 申报是公开材料 | `check_application_text.py`、人工复核 |

## 2. 当前系统的真实事实（本规范建立在这些事实上）

| # | 事实 | 出处 |
| --- | --- | --- |
| 2.1 | 题本模型 `AssessmentForm`：`code`、`version`（两者联合唯一）、`stages_json`、`key_json`、`rubric_json`、`review_status`、`content_sha256`、`supersedes_form_id`、`published_at/by`、`author_user_id` | `backend/app/assessment_models.py:17-35`；迁移 `20261018_09_assessment_hardening.py:52-70` |
| 2.2 | 五阶段结构在服务端强制校验（恰好 5 阶段，每阶段 `title/clinical_information/question`） | `backend/app/assessment/forms.py:62-64`、`:21` |
| 2.3 | 种子路径**不会**创建任何题本行；`seed_data --reset` 会删除并重建全部表（**生产禁用**，AGENTS.md 不变量 5） | `backend/app/seed_data.py:9-21`、`:30`、`:627-629`；`models.py:508-509` |
| 2.4 | 发布门禁：必须**两位不同真实教师**对**同一内容哈希**批准，作者不得自审；`require_published` 在建场次、批量排考与学生打开考核三条路径上都生效 | `assessment/forms.py:225-253`、`:81-83`；`assessment/admin.py:130-131`、`:409-410`；`assessment/student.py:87-88` |
| 2.5 | 学生响应只投影阶段题面；`key_json`/`rubric_json` 是独立列，学生路径从不读取 | `assessment/student.py:95-98`、`:106-123`；`frontend/lib/assessmentApi.ts` 的 `ExamView` 不含答案键 |
| 2.6 | 版本冻结：批准后不可改；改动必须新建版本（内容哈希必须变化），旧版标记 `SUPERSEDED`；批准与 `form_content_sha256` 绑定 | `assessment/forms.py:119-138`、`:233-234`、`:241` |
| 2.7 | 创建题本的唯一入口是 `POST /api/assessments/forms`（允许 teacher/admin，作者身份记账）；**不存在**文件上传/路径导入端点 | `assessment/forms.py:24-29`、`:106-116`；`assessment/access.py:36-39` |
| 2.8 | 私有配置的既有约定是 `~/.config/clinpath/`，systemd `EnvironmentFile=` 读取，模板要求 `install -m 600` | `deploy/systemd-user/clinical-backend.service:11`；`deploy/env/backend.env.example:4` |
| 2.9 | 平台发布题本会留下审计事件（`form.publish`，只记元数据） | `assessment/forms.py:249-251` |

## 3. 受控环境（题本的家）

### 3.1 位置与权限

```
${HOME}/.config/clinpath/exam_forms/            # 目录 mode 700，仅属主
└── <CODE>/                                      # 例 CASE-A01-SECURE-V1（code 字母数字与下划线）
    └── v<版本号>/                                # v1、v2…
        ├── form.json            # {code,title,stages[5],answer_key,rubric}（mode 600）
        ├── manifest.json        # code、version、content_sha256、作者、导入人、时间、平台 form_id
        ├── reviews/             # 两位真实教师审核原件（扫描件/电子签名，mode 600）
        └── import_log.md        # 每次导入/重导的时间、执行人、结果、核验命令与输出
```

- 目录与文件权限由属主设置（`chmod 700` 目录、`chmod 600` 文件）；平台运行账户以外的账户不得读取。
- **不在 Git 中**、不在任何共享盘、不在聊天工具、不在个人云盘。
- 至少一份**离线加密副本**（单位批准的外部介质或单位存储）作为灾难恢复源；副本的存放位置、访问人与销毁期限
  在伦理材料的数据管理计划中写明（该项由申请人/单位确定，本规范不代填）。

### 3.2 谁可以阅读

| 角色 | 可读范围 | 说明 |
| --- | --- | --- |
| 研究负责人（申请人） | 全部 | 题本的最终责任人 |
| 两位审核教师 | 被分配审核的题本 | 审核完成并发布后按 §3.4 处理访问 |
| 平台运维执行人 | 执行导入时所读的那一份 | 只在导入窗口内访问 |
| 学生 | **不可读**（存储层不可见） | 学生只能看到已发布题本的阶段题面（2.5） |

访问记录：维护一份**具名访问清单**（谁、何时、读了哪份题本、为什么），与 §3.3 的哈希一起复核。
本规范只能规定这份清单存在；**是否真的只有具名人员可读，取决于单位的信息安全执行**，Agent 无法验证。

### 3.3 版本与完整性

- 版本标识是 `code + version`，两者联合唯一（2.1）。目录结构中的 `v<版本号>` 必须与平台中的 `version` 一致。
- `manifest.json` 记录 `content_sha256`；该值由平台的 `form_hash`（`{title,stages,answer_key,rubric}` 的 sha256）产生，
  导入后必须与平台中的 `content_sha256` 逐字一致（核验命令见 §4.4）。
- **公开仓库只允许出现 code、version、审核状态这类非内容标识；不得出现题本内容，也不得出现其哈希**
  （哈希虽不能反推出题本，但会把"哪一份被使用"变成公开可检索的指纹）。哈希只存在于私有 `manifest.json`、审核原件与平台数据库中。
- 任何医学内容修改 = **新版本新目录**（不得原地修改），旧版本目录保留只读备份，标注被替代的时间与原因。
- 审核原件（`reviews/`）与版本一一对应：教师签字/电子签名的对象必须是被导入的那个内容哈希。

### 3.4 题本发布后的处理

发布（`APPROVED_FOR_ASSESSMENT`）后系统层面已冻结（2.6）。在此之后：

- 教师对题本的**只读**访问保留（教师端可查看被分配审核/评分的题本），但不得导出/复制；
- 若怀疑泄漏：**不修改**已发布题本（系统不允许），按 §6 处理，并决定是否新建版本替换；
- 考核结束、数据锁定后，按伦理材料规定保存或销毁私有副本；销毁需记录（谁、何时、销毁了什么）。

## 4. 导入运行手册（操作级，逐步执行）

> 前提：题本已由**两位真实教师**独立审核（H09），审核原件已放入 `reviews/`；**未通过审核的题本不得导入**。
> 全部命令在服务器本机执行，后端只监听本机；任何步骤不得把题本内容打印到终端输出或日志。

### 4.1 导入前（离线检查）

1. 技术校验（结构、五阶段、锚点完整、学生可见字段不含答案）：
   `python3 -I scripts/grant/validate_assessment_payloads.py <私有路径>/form.json`
   —— 该脚本只做技术校验，**不判定医学正确性**（脚本头声明）。
2. 确认文件**不在仓库内**：`git -C <repo> check-ignore -v <路径>` 应报出忽略规则或文件位于仓库外；
   若在仓库内，**停止**，先把文件移出仓库。
3. 推送前保密扫描（本规范新增，门禁）：在仓库中执行
   `python3 -I scripts/grant/publish_safety_scan.py --scope staged`
   必须为 exit 0（无 `BLOCK`）。该扫描会拦截"未公开题本出现在待提交内容中"，但**读不到仓库外文件**——它无法替代第 2 步。
4. 记录本次导入的 `code`、`version`、`manifest.json` 中的 `content_sha256`、执行人与时间。

### 4.2 导入（写入平台）

5. 以**教师或管理员**账户取得访问令牌（作者身份会与 `author_user_id` 绑定）。令牌放入 mode 600 的 curl 配置文件，
   **不要**写在命令行参数里（`ps` 可见）：

   ```console
   # ~/.config/clinpath/import.curl （mode 600，含 Authorization 头）
   # 命令：curl --config ~/.config/clinpath/import.curl \
   #   -H 'Content-Type: application/json' \
   #   --data-binary @<私有路径>/form.json \
   #   http://127.0.0.1:8100/api/assessments/forms
   ```

   题本内容只作为请求体发送到本机后端（2.7 的 `FormIn`），**不经过任何公开端点**。
6. 记录返回的 `form_id`，写入 `manifest.json` 与 `import_log.md`。

### 4.3 双教师审批（发布门禁）

7. 由管理员指定**两位不同真实教师**为审核人；两位教师各自在教师端提交对**当前内容**的批准（2.4）。
   作者不得自审；少于两位不同教师、或内容在审核后被改动，审批无效（`two_approvals_required`）。
8. 仅当 `review_status = APPROVED_FOR_ASSESSMENT` 后，才能把题本分配到考核场次（2.4 的三条路径都会拒绝未批准的题本）。

### 4.4 导入后核验（必做，逐条记录输出）

| 核验项 | 命令/操作 | 通过标准 |
| --- | --- | --- |
| 内容与私有源一致 | 读取平台 `AssessmentForm.content_sha256` 与 `manifest.json` 比对 | 完全一致 |
| 五阶段结构 | 服务端校验（2.2） | 创建成功，无 `bad_stages` |
| 审核绑定正确 | 查询该题本的审批记录 | 两位不同真实教师、`form_content_sha256` 与当前内容一致 |
| 学生侧不泄漏答案 | 以测试学生账户打开该场次考核，检查响应；并跑 `backend/tests/test_student_api_leak_sweep.py` 与 `test_assessment_student_exam.py` | 响应中只有阶段题面，无 `answer_key`/`rubric` 字段 |
| 审计留存 | 查询 `form.publish` 等审计事件（2.9） | 事件存在，只含元数据 |
| 未进公开仓库 | 在仓库执行 `python3 -I scripts/grant/publish_safety_scan.py --scope tree` | exit 0，且 `--show-allowlist` 中没有本题本 |

### 4.5 失败与回滚

- 导入失败（校验/网络/权限）：题目未写入平台即无状态；修正后重做 §4.1。
- 平台数据库被重建或从备份恢复：题本行可能**不存在**（2.3 的 `--reset` 会清空考核表），必须从私有源按 §4.2 重新导入，
  并重新完成双教师审批（审批绑定内容哈希，重建后需重新记录）。**这说明私有源才是权威副本，数据库不是档案**。
- 内容确需修改：新建版本（§3.3），不得原地编辑。

## 5. 与研究数据、演示样例的隔离

- 研究导出只含题本 **code、version、题本顺序、分数**；不得含题面、答案键或锚点文本（数据字典由研究/统计域维护）。
- 已公开的开发样例（`A01_assessment_payload_DRAFT.json` 等）**只能**作平台演示与开发测试：
  它们必须带暴露/演示标注，且**不得**分配给任何真实学生的场次。`scripts/grant/publish_safety_scan.py` 的
  `EXPOSED_DEV_SAMPLES` 已把它们的暴露记录在案（含内容哈希）；修改这些文件会被要求保留暴露标注。
- 备用/平行题本（若采用 `FORM_ORDER_DECISION_OPTIONS.md` 的选项 B）走**同一套**流程，只是数量变为 4 份。

## 6. 泄漏事件响应（与本规范绑定）

1. **记录**：时间、批次、题本 code/version、涉及学生、性质（口头/拍照/打印/截屏）、已知范围。
2. **不同步修改**题本（系统禁止，且会破坏版本与审批链）。
3. **评估**：由研究负责人与统计负责人决定是否停用该题本、是否新建版本替换、是否按预先规定处理分析集
   （主分析不剔除，另做敏感性分析；规则见 SAP §3.4 的 S12 与 `FORM_ORDER_DECISION_OPTIONS.md` §2 选项 A5）。
4. **上报**：按伦理材料的事件分级处理（`E5_protocol/E5_03_ethics_privacy.md` 的事件响应级别）。
5. **复盘**：更新访问清单与本题本的使用范围记录。

## 7. 本规范不能做什么（如实声明）

- 不能阻止拍照、打印与口头转述；也不能观测其是否发生。
- 不能验证"私有环境真的只有具名人员可读"——这取决于单位的账户与介质管理，Agent 无法核查。
- 不能判定题本的医学正确性与难度可比性；那只能由两位真实教师校准。
- 不能替代法律/伦理层面的数据管理计划与销毁要求。
- 静态扫描只覆盖 Git 中的内容：仓库之外的文件、图片内部文字与已推送历史都超出其能力（见脚本自身输出的 limits）。
- 本规范未被执行过任何一次完整导入：截至 2026-10-19 **不存在**通过真实教师审核的正式题本，因此 §4 的全部步骤尚未实测。
