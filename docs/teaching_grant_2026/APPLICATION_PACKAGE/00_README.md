# 申报材料包（APPLICATION_PACKAGE）

> 项目名称：《基于人工智能辅助临床推理训练的医学生个性化学习与形成性评价教学改革研究》
> 状态：**官方模板填写版已生成**（来源为公开转载件，待申请人确认版本）；其余材料仍为可编辑草稿。
> 提交截止：以贵校教务处通知为准（省厅对一般项目的收件截止为 2026-11-25；任务书所载 10-25 应为校内截止）。

## 0. 官方模板状态：**已取得并已填写**（来源为公开转载件，待申请人确认版本）

申请人的 `ClinPath_2026_Official_Source_Templates.zip` 在本机确实不存在，但该文件是**省教育厅公开印发**的。
Agent 已从**宁波大学医学部官网**转载的《浙江省教育厅办公室关于组织 2026 年本科和研究生教育省级教学改革项目
申报工作的通知》页面取得**真实官方原件**，存放于 `official/`（该目录已 gitignore，不入库）：

| 文件 | 内容 | 大小 |
| --- | --- | --- |
| `att1_选题指南.pdf` | 附件 1 项目选题指南 | 1.8 MB |
| `att2_申报书.docx` | 浙江省高等教育 2026 年教学改革项目**申报书** | 172 KB |
| `att4_汇总表.xlsx` | 浙江省高等教育 2026 年教学改革项目申报**汇总表** | 11.5 KB |
| `att10_通知.pdf` | 省教育厅办公室通知（含工作流程与截止时间） | 1.9 MB |

来源页 `https://medicine.nbu.edu.cn/info/1523/64741.htm`（下载需 Referer 与浏览器 UA）。
**这是公开转载件，不是申请人手上的原件**；详见 `../FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md` §0—§1。

**已产出**（`official_out/`，已 gitignore —— 填写后会含真实姓名，不入公开仓库）：

- `浙江省2026年教改项目申报书_官方模板填写版.docx` —— 六栏正文与已知字段已写入官方模板副本；
- `浙江省2026年教改项目申报汇总表_官方模板填写版.xlsx` —— 保留官方 Excel 格式（通知要求汇总表报送 Excel 版与盖章 PDF 版）。

生成命令（需同时装 python-docx 与 openpyxl）：

```bash
uv run --python 3.11 --with python-docx --with openpyxl python scripts/grant/fill_official_forms.py --overwrite
uv run --python 3.11 --with python-docx python scripts/grant/validate_official_docx.py \
  "docs/teaching_grant_2026/APPLICATION_PACKAGE/official_out/浙江省2026年教改项目申报书_官方模板填写版.docx" \
  --template docs/teaching_grant_2026/APPLICATION_PACKAGE/official/att2_申报书.docx
```

**仍需真人完成**：主持人/成员/单位/职称/出生年月/联系电话/签字/盖章一律为醒目 `【待填】`，
**脚本从不写入任何姓名、日期或职称**；「提交就绪」检查因此**按设计 FAIL**，真人填毕后才会通过。

**需申请人确认（H01）**：本文件所填的是公开转载的版本，**请确认这就是贵校教务处要求提交的版本**；
若栏目名、字数上限或附加页不同，请提供本单位版本并由 Agent 重填。

**需申请人确认（截止时间）**：通知的工作流程为「（二）申报重点项目 → 2026-10-30」、
「（四）申报一般项目 → 2026-11-25」，且**先重点、后一般**两轮。本项目为**一般项目**，
故省厅收件截止是 **11-25**；任务书所载 **2026-10-25 20:00 与两个省厅日期都不符，应为校内截止**。
请向教务处确认实际要赶的轮次与日期。

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
| `70_summary_table_attachment3_draft.md` | 申报汇总表草稿（供阅读，非提交件） | **非官方格式**；正式提交件为 `official_out/` 内的官方模板填写版 |
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
