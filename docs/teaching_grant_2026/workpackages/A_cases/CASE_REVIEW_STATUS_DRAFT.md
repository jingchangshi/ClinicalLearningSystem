# CASE_REVIEW_STATUS（草案）——六份病例的审核状态

> 日期 2026-10-18；工作树 `feat/clinpath-final-2026`。本文件如实记录**已完成的技术工作**与**尚未发生的真实医学审核**。AI 所做的一切检查和修订均属“AI technical/medical DRAFT re-check（非真实教师审定）”。**没有任何一份病例、量表或题本经过真实教师审核，没有任何教师姓名、日期或签字。** 最终交付版 `FINAL_DELIVERY/CASE_REVIEW_STATUS.md` 应由主负责人在合并各工作包后据此生成，不得与本文件矛盾。

## 1. 总表

| 病例 | 类型 | 主题 | 卡片 | 待审载荷 | 审核表 | AI 技术/医学草案复核 | 真实教师审核 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CASE-T01 | 训练 | SLE（疑伴狼疮肾炎） | `A01_training_SLE.md` | 无（训练库） | `review_forms/CASE_REVIEW_FORM_T01.md` | 早期自查记录于 `MEDICAL_REVIEW_ISSUES_v1.md`；本轮未修改内容 | 未进行 | `PENDING_REAL_REVIEW` |
| CASE-T02 | 训练 | 类风湿关节炎 | `A01_training_RA.md` | 无 | `…FORM_T02.md` | 同上 | 未进行 | `PENDING_REAL_REVIEW` |
| CASE-T03 | 训练 | ANCA 相关性血管炎 | `A01_training_AAV.md` | 无 | `…FORM_T03.md` | 同上 | 未进行 | `PENDING_REAL_REVIEW` |
| CASE-T04 | 训练 | 炎性肌病（抗合成酶综合征伴 ILD） | `A01_training_IIM.md` | 无 | `…FORM_T04.md` | 同上 | 未进行 | `PENDING_REAL_REVIEW` |
| CASE-A01 | 独立考核 | 未分化多关节炎 | `A01_assessment_UA.md` | `A01_assessment_payload_DRAFT.json`（本轮新增） | `…FORM_A01.md` | 复核了 2010 ACR/EULAR 两个时点的计分（5 与 5，一致）；载荷由卡片转录，S4 增补的 ENA/肝炎/结核阴性结果待教师确认（D-13）；难度/时间为 AI 估计 | 未进行 | `PENDING_REAL_REVIEW` |
| CASE-A02 | 独立考核 | 持续性干燥症状待查（疑似原发性干燥综合征，未确诊） | `A01_assessment_sicca.md`（原 `…multisystem.md`） | `A02_assessment_payload_DRAFT.json`（r2） | `…FORM_A02.md` | 完整复核并修订，见第 3 节 | 未进行 | `PENDING_REAL_REVIEW` |
| 量表 | — | 六维权重 10/20/25/15/20/10（研究量表） | `A01_case_index.md` §六维 | 载荷 `rubric.anchors` | `review_forms/RUBRIC_REVIEW_FORM.md` | 权重/锚点格式校验通过；锚点医学合理性未经教师确认 | 未进行 | 待教师确认；训练权重 20/20/20/15/15/10 未改动 |
| A01/A02 难度匹配 | — | — | — | — | `review_forms/DIFFICULTY_MATCH_A01_A02.md` | AI 估计 + 载荷字符数（604 / 636） | 未进行 | 未校准，**不得宣称等难** |

旧 AOSD 版 A02 只存在于 Git 历史，**不是**现行考核题本；`A02_REPLACEMENT_REVIEW.md` 已记录替换及本轮修订。

## 2. 本轮实际执行并核对的技术检查

| 检查 | 命令 | 结果（本次实际运行） |
| --- | --- | --- |
| A01/A02 载荷校验（5 阶段、必填字段、锚点、学生可见字段无答案） | `python3 -I scripts/grant/validate_assessment_payloads.py` | 28/28 通过；旧 r1 A02 载荷同一脚本 10/13 通过、**失败**（缺锚点等），证明脚本会失败 |
| 载荷校验测试 | `uv run --python 3.11 --with-requirements requirements.txt pytest -q tests/test_case_payload_validation.py` | 19 passed |
| 审核表空白性与漂移测试 | `…pytest -q tests/test_case_review_forms.py` | 9 passed（全部 PENDING、无姓名/日期/签字、与生成器一致） |
| 泄漏审计脚本及测试 | `python3 -I scripts/grant/audit_exam_leakage.py`；`…pytest -q tests/test_exam_leakage_audit.py` | 扫描 1064 条，HIGH=0 MEDIUM=0 LOW=4；测试 7 passed（含植入泄漏必被发现、缺输入 fail closed） |
| 既有六卡校验脚本 | `python3 -I scripts/grant/check_case_cards.py` | **87/88**：唯一失败是该脚本第 52 行仍写旧文件名 `A01_assessment_multisystem.md`（非本工作包文件）。把该字符串改为 `A01_assessment_sicca.md` 后在临时副本上运行为 **88/88 通过**（新 A02 卡片已按完整卡片格式重写）。待主负责人更新该脚本 |

以上证明**格式与一致性**，不证明医学正确。

## 3. CASE-A02 的医学复核结论与修改（AI 草案复核，非教师审定）

| # | 问题（r1 草案） | 修改（r2） | 理由 |
| --- | --- | --- | --- |
| 1 | 学生可见标题含“疑似原发性干燥综合征”，S4/S5 问题写“解释阴性抗 SSA 的局限”“说明为什么不能仅凭目前证据做最终判断” | 标题与五个问题改为中性表述 | 把假设与评分要点交给学生，会削弱区分度并泄露答案 |
| 2 | S5 写“唇腺活检尚未实施” | 删除，由学生自行提出 | 该句暗示唇腺活检是答案 |
| 3 | S3“无已知 HCV 感染” | 抗 HCV、HIV 抗体阴性，胸片无肺门淋巴结肿大，血糖/HbA1c/TSH/尿常规/血常规正常 | 2016 排除条件是活动性（PCR 证实）HCV 感染等，需结果而非“无已知” |
| 4 | “眼表染色异常”无数值 | OSS 右 5/左 4 | 否则无法按 2016 标准计分 |
| 5 | 无逐项计分与“未评估”处理 | 已知 2 分（Schirmer 1 + OSS 1 + 抗 SSA 0），唾液流率与唇腺活检未评估；抗 SSA 阴性时无创检查最多 3 分 <4，唇腺活检或抗 SSA 复测阳性才可能达标 | 把“为什么活检关键”落实为可核对的算术；避免把未做的检查当作阴性/阳性 |
| 6 | “干燥症状≠确诊”“分类≠诊断”只有一句话 | 卡片中逐点写明：ANA、RF、IgG、ESR、腮腺超声均不是 2016 条目；抗 SSA 阴性不排除；未达 4 分不等于排除 | 任务书 R5.2 第 3–5 项 |
| 7 | 缺少非免疫原因的完整鉴别 | 增加药物（含 3 个月洗脱）、其他干眼、张口呼吸、代谢/内分泌、HCV/HIV/结节病/淀粉样变/IgG4/放疗、继发性干燥综合征、淋巴增殖性疾病 | 鉴别完整性 |
| 8 | 唇腺活检、眼科客观检查、免疫抑制适应证只有一句 | 活检适应证/时机（用激素前）/风险/判读；唾液流率先于活检；Schirmer 需停用抗胆碱能药后；明确不启动系统免疫抑制并说明会干扰活检评分 | 任务书 R5.2 第 6–7 项 |
| 9 | 载荷无锚点 | 六维高/中/低锚点，可计数条目，粒度与 A01 一致 | 任务书 R5.2 第 8 项、R3.2 |
| 10 | 与 A01 的难度未对照 | AI 估计两例推理步骤约 7 步、作答 45–60 分钟；字符数 604 / 636；A01 计分负担更机械，A02 开放性更高，评分者差异风险更大 | 任务书 R5.2 第 9 项；**未经教师校准** |
| 11 | 引用仅 2016 标准与“待补充” | 核实书目：2016 ACR/EULAR（ARD 与 Arthritis Rheumatol 两种刊载）、EULAR 2020 管理建议、AECG 2002、Daniels 2011、Brito-Zerón 2016、TFOS DEWS II | 任务书 R5.2 第 10 项 |

## 4. 引用核实情况

| 引用 | 状态 | 方式 |
| --- | --- | --- |
| Shiboski CH, et al. 2016 ACR/EULAR 原发性干燥综合征分类标准。*Ann Rheum Dis* 2017;76(1):9–16；*Arthritis Rheumatol* 2017;69(1):35–45 | 书目与计分条目/权重已核实；入口/排除条件与药物洗脱说明来自 PMC 全文摘录，未逐字复核原文 | Europe PMC 书目记录；PMC5650478 |
| Ramos-Casals M, et al. EULAR 干燥综合征局部与系统治疗管理建议。*Ann Rheum Dis* 2020;79(1):3–18 | 书目与摘要已核实；**具体推荐文字与证据级别未取得全文**，卡片未作逐条断言 | Europe PMC |
| Vitali C, et al. AECG 修订分类标准。*Ann Rheum Dis* 2002;61(6):554–558 | 书目已核实 | Europe PMC |
| Daniels TE, et al. *Arthritis Rheum* 2011;63(7):2021–2030 | 书目已核实（唇腺组织学） | Europe PMC |
| Brito-Zerón P, et al. Sjögren syndrome. *Nat Rev Dis Primers* 2016;2:16047 | 书目已核实 | Europe PMC |
| Wolffsohn JS, et al. TFOS DEWS II Diagnostic Methodology report. *Ocul Surf* 2017;15(3):539–574 | 书目已核实 | Europe PMC |
| 中华医学会风湿病学分会《原发性干燥综合征诊疗规范》，*中华内科杂志* 2020;59(4):269–276 | **UNVERIFIED**：检索显示条目存在，但发布机构表述不一致，未能打开全文 | — |
| ESSDAI 原始文献（Seror R, et al. 2010） | **UNVERIFIED**：未能在线核实书目 | — |
| 抗 SSA 阴性（血清阴性）干燥综合征的比例/特征 | **UNVERIFIED**：未得到可核实的原始文献，卡片不引用任何百分比 | — |
| 针对干燥综合征的更新版 EULAR/ACR 推荐或分类标准 | **UNVERIFIED**：检索未发现可核实的已发表版本，未引用 | — |
| A01 引用（2010 ACR/EULAR RA、EULAR 早期关节炎推荐版本、UA 自然转归文献）；T01–T04 引用 | 本轮**未重新核实**，沿用卡片中的“版本待教师核对”标注 | — |

## 5. 仍须真实人员完成（阻塞项）

| 缺口 | 责任人 | 动作 | 阻止申报？ | 阻止正式研究/考试？ |
| --- | --- | --- | --- | --- |
| 六份病例的医学审核与签字 | 两位真实风湿科教师 | 使用 `review_forms/` 独立填写；A01/A02 另在系统内各自提交表单审核 | 否（申报可如实写“审核流程已就绪、待执行”） | **是** |
| 量表权重/锚点/裁决阈值确认 | 同上 | `RUBRIC_REVIEW_FORM.md` | 否 | **是** |
| A01/A02 难度匹配 | 同上 | `DIFFICULTY_MATCH_A01_A02.md` | 否 | **是** |
| 争议项裁定（含 v1 遗留 Q-01…Q-09、Q-11） | 同上 | `DISPUTE_LIST.md` | 否 | 是 |
| 更正 UNVERIFIED 引用 | 教师 | 对照原文 | 否 | 是 |
| 公开仓库已托管考核答案（L-1） | 申请人/研究负责人 | 决定可见性与材料存放；决定是否替换已暴露题本 | 视申报书是否引用仓库 | **是** |
| 批内交叉题本的暴露（L-2） | 研究负责人、统计负责人 | 决定 P0/P1/P2（见 `LEAKAGE_AUDIT_DRAFT.md` §3） | 否 | 是 |
| 线上病例目录泄漏审计（L-6） | 有生产只读权限者 | 导出脱敏目录 JSON 并运行 `--extra-json` | 否 | 是 |
| 其他工作包的陈旧引用（L-7）、`check_case_cards.py` 第 52 行 | 对应负责人 | 更新 | 可能（证据索引不一致） | 否 |

## 6. 不得做的表述

- 不得写“病例已通过专家审核/已审定”“量表已确认”“A01/A02 已校准/等难”“已排除泄漏”。
- 可以写：“病例与量表已完成技术校验和 AI 辅助草案复核；真实双教师审核材料已备好，待执行；泄漏风险已评估，存在待决策的公开仓库与批内暴露问题。”
