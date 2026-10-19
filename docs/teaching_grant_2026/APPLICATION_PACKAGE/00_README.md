# 申报材料包（APPLICATION_PACKAGE）

> 项目名称：《基于人工智能辅助临床推理训练的医学生个性化学习与形成性评价教学改革研究》
> 状态：**可编辑草稿，非官方模板**。生成日期 2026-10-18；提交截止 2026-10-25 20:00（北京时间）。

## 0. 官方模板状态：BLOCKED（原件不在本机）

任务书要求以 2026 年浙江省本科教育教学改革项目的**官方原件**为准：申报通知、附件 1（选题指南）、
附件 2（教学改革项目申报书）、附件 3（项目申报汇总表）。

申请人此前已把官方原件交给 ChatGPT 并恢复为 **`ClinPath_2026_Official_Source_Templates.zip`**。
Agent 无法访问 ChatGPT 文件沙盒，因此按任务书 §7.1 在本机查找该 ZIP：

已搜索：整个文件系统按文件名、`~`、`~/Downloads`、`~/Documents`、`~/Desktop`、`/tmp`、
仓库根与 `docs/`、以及所有 `*.docx *.doc/.pdf/.wps/.xlsx/.zip`。
**结果：该 ZIP 与本机任何一份官方原件均未找到**（仓库内唯一提到「附件1/2/3」的是任务书本身，
另有 `docs/ClinPath_WPD_完整工作包D.zip` 是工作包 D 的合成演示，不是官方模板）。
过程与命令见 `../FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md` §1。

因此：

- 本包中的所有文件**都不是官方模板**，不得标注为「符合官方格式」；
- 六个正文栏目的名称与字数上限只来自任务书，转入官方 Word 后须以模板自带的栏目、字数和填报说明再核对；
- 官方模板里可能存在本包未覆盖的字段（如经费预算表格式、承诺书、主持人情况表的具体栏目），
  见 `官方模板字段及缺失信息清单.md` 与 `../FINAL_DELIVERY/APPLICATION_SUBMISSION_CHECKLIST.md`；
- **需要申请人动作**：把该 ZIP **原样**放到下面任一路径并告知 Agent——
  `docs/teaching_grant_2026/APPLICATION_PACKAGE/official/ClinPath_2026_Official_Source_Templates.zip`、
  `~/.config/clinpath/official/ClinPath_2026_Official_Source_Templates.zip`，或申请人自选路径
  （用 `--zip` 指定绝对路径）。**ZIP 单独就够**：填写脚本会自己识别并解压其中的附件 2/附件 3，
  只解压这两个到仓库外的临时目录；通知与附件 1 不解压。放入 `official/` 的原件**不入库**
  （已在 `.gitignore` 排除）。
- **尚未生成、也不得伪造**（任务书 §7.6）：`浙江省2026年教改项目申报书_官方模板填写版.docx`、
  `浙江省2026年教改项目申报汇总表_官方模板填写版.docx`、`主持人教学简历_待核对.docx`。
- **生成能力已就绪**：ZIP 放到 `official/`（或 `~/.config/clinpath/official/`）后，运行
  `uv run --python 3.11 --with python-docx python scripts/grant/fill_official_forms.py`
  即把六栏正文与已知字段写进官方模板副本，输出到 `official_out/`（gitignore，不入库）；
  再用 `scripts/grant/validate_official_docx.py` 做 §7.6 核验。
  详见 `../FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md` §3.1。

## 1. 文件清单

| 文件 | 内容 | 状态 |
| --- | --- | --- |
| `01_FULL_APPLICATION_DRAFT.md` | 完整申报书可编辑草稿（由脚本拼装，勿手改） | 草稿 |
| `../evidence/E5_protocol/E5_04_application_text.md` | **六栏正文唯一来源**（含字数校验） | 草稿 |
| `10_basic_info_and_host_CV.md` | 项目基本信息与主持人教学简历草稿 | 大量【待填】 |
| `20_team_roles.md` | 团队成员与分工表 | 全部姓名【待填】 |
| `30_implementation_plan.md` | 实施计划 | 日期【待填】 |
| `40_outcomes_and_KPIs.md` | 预期成果与考核指标 | 草稿 |
| `50_budget_suggestion.md` | 经费预算建议表 | 金额【待填】 |
| `60_unit_support_checklist.md` | 单位支持与证明材料清单 | 全部待办 |
| `70_summary_table_attachment3_draft.md` | 申报汇总表（附件 3）待填写版 | **非官方格式** |
| `官方模板字段及缺失信息清单.md` | 官方字段 ↔ 现有内容 ↔ 缺失信息 ↔ 提供方（含 P01—P13） | 清单 |
| `项目申报前最终核对清单.md` | 提交前逐条核对（字数、版式、签字、上传步骤） | 清单 |
| `80_one_page_summary.md` | 一页项目摘要 | 草稿 |
| `90_expert_demo_note.md` | 供专家与教学管理部门的简明技术演示说明 | 草稿 |
| `docx/*.docx` | 以上各文件的 Word 版（`scripts/grant/build_application_package.py` 生成） | 非官方模板 |

## 2. 写作约定

1. 未知的姓名、奖项年度、经费、批次日期、单位信息，一律写 `【待填：…】`，不得猜测。
2. 四种状态用词固定：**已实现 / 已通过技术测试 / 待真实教师审核 / 计划开展**。
3. 不写任何真实教学效果；不写伦理批件号；不写未取得的单位签章或奖项。
4. 合成演示标注 `SYNTHETIC / SIMULATED_NOT_HUMAN`，只证明软件可行。
5. 本项目是教学改革项目，不是软件研发项目。
6. 重新生成：`uv run --python 3.11 --with python-docx python scripts/grant/build_application_package.py`。
7. 检查：`python3 scripts/grant/check_application_text.py`、`python3 scripts/grant/check_protocol_consistency.py`。
