#!/usr/bin/env python3
"""Generate the ready-to-sign teacher review packet for the six ClinPath cases.

Output (under docs/teaching_grant_2026/workpackages/A_cases/review_forms/):
  README.md, CASE_REVIEW_FORM_{T01..T04,A01,A02}.md, RUBRIC_REVIEW_FORM.md,
  DIFFICULTY_MATCH_A01_A02.md, DISPUTE_LIST.md, ANCHOR_CONSISTENCY_TABLE.md,
  REVISION_REREVIEW_LOG.md, REVIEW_ITEMS_MASTER_BLANK.csv

Hard rules baked into every output:
  * every item is PENDING_REAL_REVIEW and review_origin is REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED;
  * reviewer names, dates and signatures are blank (never prefilled);
  * anything written by the AI is labelled "AI technical/medical DRAFT re-check";
  * research weights 10/20/25/15/20/10 are shown as pending teacher confirmation and the
    training weights 20/20/20/15/15/10 are shown unchanged.

Standard library only. Run:  python3 -I scripts/grant/build_case_review_forms.py [--out DIR] [--check]
``--check`` rebuilds into memory and exits 1 if the files on disk differ (drift guard).
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = REPO_ROOT / "docs" / "teaching_grant_2026" / "workpackages" / "A_cases"
DEFAULT_OUT = CASE_DIR / "review_forms"

PENDING = "PENDING_REAL_REVIEW"
ORIGIN = "REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED"
AI_LABEL = "AI technical/medical DRAFT re-check（非真实教师审定）"

DIMENSIONS = [
    ("medical_knowledge", "医学知识", 10, 20),
    ("key_information", "关键信息提取", 20, 20),
    ("differential_diagnosis", "鉴别诊断", 25, 20),
    ("evidence_integration", "证据整合", 15, 15),
    ("clinical_decision", "临床决策", 20, 15),
    ("evidence_based_medicine", "循证安全", 10, 10),
]

COMMON_ITEMS = [
    ("C-01", "病史、查体、实验室、影像之间在各阶段内部及相互之间是否一致（无自相矛盾的数值、时间或体征）"),
    ("C-02", "关键阳性与关键阴性是否足以支持卡片的主诊断/暂定诊断，且没有无意中指向其他疾病"),
    ("C-03", "诊断及鉴别逻辑是否符合当前临床实践；分类标准与临床诊断是否被正确区分"),
    ("C-04", "鉴别诊断是否完整、排序是否合理，支持/反对证据是否落到本病例"),
    ("C-05", "危险信号（器官威胁）是否准确、无遗漏、无夸大"),
    ("C-06", "检查策略：各项检查的适应证、优先级与局限是否正确，是否避免无指征堆砌"),
    ("C-07", "治疗/处理原则：是否安全，是否避免无指征的激素或免疫抑制（不要求剂量）"),
    ("C-08", "五阶段信息释放：每一阶段释放的信息是否足以回答该阶段的问题，且不提前泄露后续答案"),
    ("C-09", "难度标定与本科见习阶段的适用性（是否超出范围或过于简单）"),
    ("C-10", "常见错误清单是否真实、可识别"),
    ("C-11", "六维评分锚点是否清晰、可观察、可由两位评分者一致地使用"),
    ("C-12", "引用的指南与文献是否真实、版本是否恰当（逐条核对 UNVERIFIED / 版本待核对项）"),
    ("C-13", "脱敏与虚构病例声明是否充分（无可识别个人信息）"),
    ("C-14", "训练/考核隔离声明是否准确"),
]

EXAM_ITEMS = [
    ("E-01", "学生可见的表题、各阶段 clinical_information 与 question 是否**不含**答案、诊断名称或解释性结论"),
    ("E-02", "各阶段 question 是否措辞中性，不暗示“应排除/不应确诊/应做某检查”"),
    ("E-03", "answer_key.reference_reasoning 的计分与推理是否医学上正确（逐项核对计分表）"),
    ("E-04", "参考答案是否允许合理的不同答案（不强求固定病名）；哪些属于“必须”，哪些属于“加分”"),
    ("E-05", "预计作答时间（AI 估计 45–60 分钟，未校准）是否合理；五阶段是否可在该时间内完成"),
    ("E-06", "与另一份考核病例在难度、推理步骤、评分可操作性上是否可比（见 DIFFICULTY_MATCH_A01_A02.md）"),
    ("E-07", "“万能不确定”答案（只写不能确诊并随访）能否得到不合理的高分？评分锚点是否能识别并限制它"),
    ("E-08", "是否同意以该载荷（JSON）导入独立考核系统供教师评审；同意导入≠批准用于正式考试"),
]

CASES = [
    {
        "id": "CASE-T01", "kind": "训练病例", "card": "A01_training_SLE.md", "payload": None,
        "title": "系统性红斑狼疮（疑伴狼疮肾炎）", "difficulty": "基础",
        "specific": [
            ("S-01", "2019 EULAR/ACR SLE 分类标准的逐域计分表（卡片合计 31 分）表述与阈值（ANA 入口、≥10 分）是否准确"),
            ("S-02", "实验室示意值（WBC、PLT、尿蛋白、C3、C4）是否与教学医院参考范围相符（v1 清单 Q-05）"),
            ("S-03", "“急性皮肤型狼疮 6 分”的计分教学取舍（v1 清单 Q-06）"),
            ("S-04", "EULAR SLE 管理推荐课堂采用 2019 还是 2023 版（v1 清单 Q-11）；狼疮肾炎分型与肾活检指征表述"),
        ],
    },
    {
        "id": "CASE-T02", "kind": "训练病例", "card": "A01_training_RA.md", "payload": None,
        "title": "类风湿关节炎（早期，活动期）", "difficulty": "基础",
        "specific": [
            ("S-01", "2010 ACR/EULAR RA 分类标准计分（卡片 5+3+1+1=10 分）是否准确；关节计数规则"),
            ("S-02", "“典型病例计分不敏感”教学点是否保留（v1 清单 Q-07）"),
            ("S-03", "抗 CCP“强阳性”缺少数值与检测方法（v1 清单 Q-08）"),
            ("S-04", "EULAR RA 管理推荐采用 2019 还是 2022 版；达标治疗（T2T）目标表述"),
            ("S-05", "与 CASE-A01 共用 2010 标准计分框架：作为“方法训练”是否可接受（见 DISPUTE_LIST D-17）"),
        ],
    },
    {
        "id": "CASE-T03", "kind": "训练病例", "card": "A01_training_AAV.md", "payload": None,
        "title": "ANCA 相关性血管炎（GPA 倾向，肺肾受累）", "difficulty": "进阶",
        "specific": [
            ("S-01", "嗜酸性粒细胞 0.18×10⁹/L 对排除 EGPA 的表述（v1 清单 Q-09）"),
            ("S-02", "2022 ACR/EULAR 三份 AAV 分类标准的前提条件表述"),
            ("S-03", "诱导缓解治疗原则（激素联合利妥昔单抗或环磷酰胺）与感染/肾功能监测表述"),
            ("S-04", "EULAR/ERA-EDTA AAV 推荐与 KDIGO 版本（v1 清单 Q-11）"),
        ],
    },
    {
        "id": "CASE-T04", "kind": "训练病例", "card": "A01_training_IIM.md", "payload": None,
        "title": "炎性肌病（抗合成酶综合征伴 ILD）", "difficulty": "进阶",
        "specific": [
            ("S-01", "2017 EULAR/ACR IIM 分类标准与管理推荐版本（2017/2023）"),
            ("S-02", "抗合成酶综合征与抗 MDA5 皮肌炎等表型的表述；ILD 评估与监测"),
            ("S-03", "成人皮肌炎的恶性肿瘤筛查建议（尤其抗 TIF1-γ）"),
            ("S-04", "检查策略中肌电图、肌活检、MRI 的适应证与优先级"),
        ],
    },
    {
        "id": "CASE-A01", "kind": "独立考核病例", "card": "A01_assessment_UA.md",
        "payload": "A01_assessment_payload_DRAFT.json",
        "title": "未分化多关节炎", "difficulty": "中等",
        "specific": [
            ("S-01", "“未分化关节炎”的病程界定（v1 清单 Q-02）；5 周病程与 2 个小关节肿胀是否符合“未分化”教学意图（Q-01）"),
            ("S-02", "2010 ACR/EULAR 初诊计分 2+2+1+0=5 与 3 个月随访计分 2+2+0+1=5：入口条件、关节计数、“低滴度 RF”定义是否准确（RF 仅称“弱阳性”无数值）"),
            ("S-03", "随访时点设计（总分仍为 5）是否为最佳教学组合（Q-03）；是否应更早复评（Q-04）"),
            ("S-04", "载荷 S4 新增了 ENA 谱、HBsAg、抗 HCV、结核检测均阴性（卡片 §2 未列出，AI 为使 S4 有可解释的结果而加入）是否可接受"),
            ("S-05", "EULAR 早期关节炎推荐版本与 UA 自然转归文献（卡片已标待教师指定）"),
            ("S-06", "示意数值：ESR 32/18、CRP 12/4 与参考范围；A01 难点是否为“计分算术”多于“临床判断”"),
        ],
    },
    {
        "id": "CASE-A02", "kind": "独立考核病例", "card": "A01_assessment_sicca.md",
        "payload": "A02_assessment_payload_DRAFT.json",
        "title": "持续性干燥症状待查（疑似原发性干燥综合征，未确诊）", "difficulty": "中等（待校准）",
        "specific": [
            ("S-01", "“干燥症状”≠“确诊干燥综合征”：各阶段信息与问题是否让学生既不能过度诊断，也不能草率排除"),
            ("S-02", "2016 ACR/EULAR 入口/排除条件与计分表述：已知 2 分（Schirmer 1 + OSS 1 + 抗 SSA 0），唾液流率与唇腺活检“未评估”；抗 SSA 阴性时无创检查最多 3 分 <4，唇腺活检/抗 SSA 复测阳性才可能达标——此推演是否正确、是否过度简化"),
            ("S-03", "抗 SSA/Ro 阴性的解释：是否同意“不能排除”；是否要求第二种方法复测（DISPUTE_LIST D-04）"),
            ("S-04", "眼科客观检查（OSS、无麻醉 Schirmer）与眼科转诊指征；OSS 右 5/左 4 的边界设计（D-02）"),
            ("S-05", "唇腺活检的适应证、时机（应在使用激素/免疫抑制之前）、风险、判读要求；对本科生是“必须掌握”还是“加分”（D-05）"),
            ("S-06", "是否已避免无指征系统免疫抑制；羟氯喹是否可用于关节痛/乏力（D-06）；EULAR 2020 关于局部/系统治疗的具体推荐与证据级别"),
            ("S-07", "数值一致性：ESR 28、CRP 3、IgG 17.8 g/L、C3/C4 正常、ANA 1:160 斑点型、RF 28 IU/mL 弱阳性、抗 CCP 未查——组合是否合理，是否过度偏向干燥综合征（D-09）"),
            ("S-08", "腮腺超声“轻度非均匀回声”是否应保留为非标准条目的辅助信息（D-07）"),
            ("S-09", "UNVERIFIED 文献：中华医学会风湿病学分会《原发性干燥综合征诊疗规范》（中华内科杂志 2020;59(4):269–276）与 ESSDAI 原始文献请教师核对原文"),
            ("S-10", "患者在 S5 询问是否需要激素/免疫抑制剂：是否过度提示答案（D-01）"),
        ],
    },
]


# --------------------------------------------------------------------------------------
def _load_payload(name: str | None) -> dict | None:
    if not name:
        return None
    path = CASE_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _sig_block(slot: str) -> str:
    return (
        f"**{slot}**（请审核教师本人填写；不得由他人代填）\n\n"
        "| 项 | 内容 |\n| --- | --- |\n"
        "| 姓名 / 工号 | |\n| 职称 / 单位 | |\n"
        "| 是否参与过本病例起草或本批次学生带教（利益冲突） | ☐ 否　☐ 是，说明： |\n"
        "| 声明：本人独立完成审核，未参考另一位教师的意见 | ☐ 已确认 |\n"
        "| 审核日期（YYYY-MM-DD） | ____-__-__ |\n"
        "| 签字 | |\n"
    )


def _case_form(case: dict) -> str:
    payload = _load_payload(case["payload"])
    lines: list[str] = []
    add = lines.append
    add(f"# {case['id']} 病例审核表（可直接签署）")
    add("")
    add(f"> **状态：`{PENDING}`　review_origin：`{ORIGIN}`**。本表由 AI 预填病例信息与核对要点，**所有审核结论、姓名、日期、签字均为空**，必须由两位真实风湿科教师独立填写。AI 的任何检查只属于“{AI_LABEL}”，不得被引用为教师审定。")
    add("")
    add("## 0. 病例信息（AI 预填，教师请核对）")
    add("")
    add("| 项 | 内容 |\n| --- | --- |")
    add(f"| 病例编号 | {case['id']} |")
    add(f"| 类型 | {case['kind']} |")
    add(f"| 主题 | {case['title']} |")
    add(f"| 标定难度 | {case['difficulty']} |")
    add(f"| 病例卡 | `{case['card']}` |")
    add(f"| 待审载荷 | {('`' + case['payload'] + '`') if case['payload'] else '无（训练病例，不进入独立考核系统）'} |")
    add(f"| 当前审核状态 | `{PENDING}` |")
    add("")
    if payload:
        add("### 学生可见内容（载荷摘录，请核对是否泄露答案）")
        add("")
        add(f"- 学生可见表题：{payload['title']}")
        for i, stage in enumerate(payload["stages"], start=1):
            add(f"- **{stage['title']}**")
            add(f"  - 信息：{stage['clinical_information']}")
            add(f"  - 问题：{stage['question']}")
        add("")
    add("## 1. 审核人（两位独立）")
    add("")
    add(_sig_block("REAL_TEACHER_1"))
    add(_sig_block("REAL_TEACHER_2"))

    add("## 2. 逐项核对（符合 / 需修改 / 不符合 / 无法判断；请在对应教师栏填写，并在“意见”中写具体段落）")
    add("")
    add("| ID | 核对项 | 教师1 结论 | 教师1 意见 | 教师2 结论 | 教师2 意见 | 状态 |")
    add("| --- | --- | --- | --- | --- | --- | --- |")
    items = COMMON_ITEMS + (EXAM_ITEMS if case["kind"] == "独立考核病例" else []) + case["specific"]
    for item_id, text in items:
        add(f"| {item_id} | {text} | | | | | {PENDING} |")
    add("")
    add("## 3. 量化评分（1–5 整数，刻度同 A03）")
    add("")
    add("| 指标 | 说明 | 教师1 | 教师2 |")
    add("| --- | --- | --- | --- |")
    add("| medical_accuracy_1to5 | 1=存在明显医学错误，5=完全符合指南与临床实践 | | |")
    add("| undergraduate_fit_1to5 | 1=明显超出本科见习范围，5=完全适合 | | |")
    add("| difficulty_1to5 | 1=过易，3=与标定难度相符，5=过难 | | |")
    add("| rubric_clarity_1to5 | 1=评分要点无法操作，5=清晰可评分 | | |")
    add("")
    add("## 4. 结论")
    add("")
    add("| 教师 | 结论（单选） | 说明 |")
    add("| --- | --- | --- |")
    add(f"| REAL_TEACHER_1 | ☐ ACCEPT_FOR_TEACHING　☐ REVISE_AND_RESUBMIT　☐ REJECT　（未填写则保持 `{PENDING}`） | |")
    add(f"| REAL_TEACHER_2 | ☐ ACCEPT_FOR_TEACHING　☐ REVISE_AND_RESUBMIT　☐ REJECT　（未填写则保持 `{PENDING}`） | |")
    if case["kind"] == "独立考核病例":
        add("")
        add("> 独立考核病例另需：两位教师分别在系统内提交**各自的**表单审核（不得由一人代签），管理员核验后方可发布；“同意导入”不等于“批准用于正式考试”。")
    add("")
    add("## 5. 修改意见清单")
    add("")
    add("| # | 位置（章节/阶段/句子） | 问题 | 建议修改 | 严重度（必须/建议/可选） | 提出人 | AI/作者回应（仅记录技术处理，不代表采纳） |")
    add("| --- | --- | --- | --- | --- | --- | --- |")
    for i in range(1, 7):
        add(f"| {i} | | | | | | |")
    add("")
    add("## 6. 复审记录")
    add("")
    add("| 轮次 | 修订后版本 | 复审日期 | 复审教师 | 结论 | 签字 |")
    add("| --- | --- | --- | --- | --- | --- |")
    add("| 1 | | ____-__-__ | | | |")
    add("| 2 | | ____-__-__ | | | |")
    add("")
    add("## 7. 第三位教师/教研室仲裁（仅当两位教师结论冲突时填写）")
    add("")
    add("| 仲裁人 | 日期 | 结论 | 签字 |\n| --- | --- | --- | --- |\n| | ____-__-__ | | |")
    add("")
    add("## 8. 声明")
    add("")
    add(f"- 本表不含任何真实教师姓名、签名或日期；不代表本病例的审核已经完成。")
    add(f"- 在两位教师完整填写并签字之前，{case['id']} 保持 `{PENDING}`。")
    add(f"- AI 对本病例所做的修订属“{AI_LABEL}”，修订记录见 `REVISION_REREVIEW_LOG.md`。")
    add("")
    return "\n".join(lines)


def _rubric_form() -> str:
    a01 = _load_payload("A01_assessment_payload_DRAFT.json")
    a02 = _load_payload("A02_assessment_payload_DRAFT.json")
    out: list[str] = []
    add = out.append
    add("# 六维评分量表审核表（独立考核研究量表）")
    add("")
    add(f"> **状态：`{PENDING}`　review_origin：`{ORIGIN}`**。研究权重 **10/20/25/15/20/10 为待教师确认的草案**；平台训练（形成性）权重 **20/20/20/15/15/10 保持不变，不在本表审核范围内，也不得被本表结论覆盖**。")
    add("")
    add("## 1. 审核人")
    add("")
    add(_sig_block("REAL_TEACHER_1"))
    add(_sig_block("REAL_TEACHER_2"))
    add("## 2. 权重确认")
    add("")
    add("| 维度（key） | 研究权重（待确认） | 训练权重（不变） | 教师1：同意/修改为 | 教师2：同意/修改为 | 理由 | 状态 |")
    add("| --- | ---: | ---: | --- | --- | --- | --- |")
    for key, zh, research, training in DIMENSIONS:
        add(f"| {zh}（{key}） | {research}（待教师确认） | {training} | | | | {PENDING} |")
    add(f"| **合计** | **100** | **100** | | | | {PENDING} |")
    add("")
    add("总分公式（系统实现）：总分 = Σ(维度分 × 权重) / 100，维度分 0–100。示例（纯算术演示，非任何学生数据）：各维度分均为 80 → 总分 80；医学知识 100、其余 0 → 总分 10。")
    add("")
    add("## 3. 锚点审核（A01 与 A02 草案各一套；每维度 高/中/低 三档）")
    add("")
    for key, zh, research, _training in DIMENSIONS:
        add(f"### {zh}（{key}，研究权重 {research}，待确认）")
        add("")
        add("| 档位 | CASE-A01 锚点（AI 草案） | CASE-A02 锚点（AI 草案） | 教师1 | 教师2 |")
        add("| --- | --- | --- | --- | --- |")
        for band, label in (("high", "高（80–100）"), ("mid", "中（50–79）"), ("low", "低（0–49）")):
            a1 = a01["rubric"]["anchors"][key][band] if a01 else "（载荷缺失）"
            a2 = a02["rubric"]["anchors"][key][band] if a02 else "（载荷缺失）"
            add(f"| {label} | {a1} | {a2} | | |")
        add("")
    add("## 4. 评分操作规则审核")
    add("")
    add("| ID | 事项 | 教师1 | 教师2 | 状态 |")
    add("| --- | --- | --- | --- | --- |")
    rules = [
        ("R-01", "三档分段（80–100 / 50–79 / 0–49）是否合适；档内如何细分（锚点只给档位，不给逐分规则）"),
        ("R-02", "两位评分者总分差/维度差的**裁决阈值**（系统可配置；阈值须在正式研究前由教师确认，AI 不预设）：建议值：______"),
        ("R-03", "“万能不确定”答案（只写不能确诊并随访）的上限分数规则"),
        ("R-04", "答案遗漏“必须项”时是否有封顶规则（例如出现无指征使用免疫抑制则循证安全≤49）"),
        ("R-05", "是否同意各维度由评分者独立打分、不得看到对方分数、不得看到批次/组别/时点"),
        ("R-06", "评分者校准：正式评分前是否需要用 B 工作包样例答案做一次校准会（已用于培训的样例不得出自 A01/A02 的真实学生答卷）"),
    ]
    for rid, text in rules:
        add(f"| {rid} | {text} | | | {PENDING} |")
    add("")
    add("## 5. 声明")
    add("")
    add(f"- 本表不含任何真实教师姓名、签名或日期；权重与锚点在两位教师签字前均为草案（`{PENDING}`）。")
    add(f"- 独立考核应从**已批准的 rubric 版本**读取权重与锚点；批准动作只能由教师在系统内或经此表签字后由管理员核验完成。")
    add("")
    return "\n".join(out)


def _difficulty_form() -> str:
    a01 = _load_payload("A01_assessment_payload_DRAFT.json")
    a02 = _load_payload("A02_assessment_payload_DRAFT.json")

    def chars(payload: dict | None) -> tuple[str, str]:
        if not payload:
            return ("?", "?")
        info = sum(len(s["clinical_information"]) for s in payload["stages"])
        qs = sum(len(s["question"]) for s in payload["stages"])
        return (str(info), str(qs))

    c1, c2 = chars(a01), chars(a02)
    out: list[str] = []
    add = out.append
    add("# CASE-A01 / CASE-A02 难度匹配表")
    add("")
    add(f"> **状态：`{PENDING}`　review_origin：`{ORIGIN}`**。“AI 估计”列为“{AI_LABEL}”，**未经任何真实校准**；“字符数”列由载荷直接计数，可复核。教师栏必须由两位真实教师独立填写。")
    add("")
    add("## 1. 审核人")
    add("")
    add(_sig_block("REAL_TEACHER_1"))
    add(_sig_block("REAL_TEACHER_2"))
    add("## 2. 逐属性比较（AI 估计 vs 教师判断）")
    add("")
    add("| 属性 | CASE-A01（未分化多关节炎） | CASE-A02（持续性干燥症状待查） | 可比性（AI 估计） | 教师1 判断 | 教师2 判断 | 状态 |")
    add("| --- | --- | --- | --- | --- | --- | --- |")
    rows = [
        ("阶段数 / 结构", "5（S1–S5，同结构）", "5（S1–S5，同结构）", "相同"),
        ("学生可见 clinical_information 总字符数（载荷计数）", c1[0], c2[0], ("A02 信息量更大" if int(c2[0]) > int(c1[0]) else "A01 信息量更大")),
        ("学生可见 question 总字符数（载荷计数）", c1[1], c2[1], "相近"),
        ("主要推理步骤（AI 估计）", "约 7：关节计数/炎性判断、入口条件、初诊计分、≥6 个鉴别、检查优先级与安全筛查、随访重新计分、重新分类触发条件", "约 7：入口与排除条件、客观证据识别、非免疫原因排查、鉴别、2016 计分与未评估项、血清阴性解释与活检指征、对症管理与随访", "相近"),
        ("算术/计分负担", "高：2010 标准在两个时点各计分一次（四项求和）", "中：2016 五项计分，多项“未评估”", "A01 更机械"),
        ("开放性/不确定性", "中：结论为“未分化+随访”", "高：结论为“不能确诊+决定性检查为活检”，对“万能不确定”答案更脆弱", "A02 评分变异风险更高"),
        ("所需背景知识", "关节炎鉴别、2010 RA 标准、早期关节炎管理", "干眼/口干病因、2016 SjD 标准、唇腺活检、自身抗体局限", "领域不同，难比较"),
        ("与训练病例的构念重叠", "与 CASE-T02（RA）共用 2010 标准计分框架", "与训练库无同病种内容；与 A01 共享“勿过度诊断+随访”元模式", "见泄漏审计"),
        ("预计作答时间（AI 估计，未校准）", "45–60 分钟", "45–60 分钟", "相同（假设）"),
        ("评分者一致性风险（AI 估计）", "中低：计分可核对", "中：依赖对不确定性与优先级的判断", "A02 更高"),
    ]
    for attr, v1, v2, comp in rows:
        add(f"| {attr} | {v1} | {v2} | {comp} | | | {PENDING} |")
    add("")
    add("## 3. 教师逐例判断（同 A04 空白表字段）")
    add("")
    add("| case_id | reviewer_slot | expected_difficulty_1to5 | actual_undergraduate_fit_1to5 | information_completeness_1to5 | reasoning_steps_required | estimated_minutes | hardest_step | recommended_change | accept_difficulty_gap（是/否） | final_approval |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for case in ("CASE-A01", "CASE-A02"):
        for slot in ("REAL_TEACHER_1", "REAL_TEACHER_2"):
            add(f"| {case} | {slot} | | | | | | | | | {PENDING} |")
    add("")
    add("## 4. 顺序与传播相关问题（教师请判断）")
    add("")
    add("| ID | 问题 | 教师1 | 教师2 | 状态 |")
    add("| --- | --- | --- | --- | --- |")
    for rid, text in [
        ("M-01", "若两例难度不等，X/Y 批内交叉（各约 4/3 人）能否使“组别×时点”估计不被题本难度混杂？是否需要在分析中以题本为协变量"),
        ("M-02", "是否接受两例预计作答时间相同并统一开放窗口；若不同，应分别设为多少分钟"),
        ("M-03", "是否需要在正式研究前对 A01/A02 做小规模试答（非研究对象的学生/住院医）以校准难度；试答数据不得并入研究数据"),
        ("M-04", "A01 的“高算术负担”与 A02 的“高开放性”是否对不同能力学生有利（例如强于计算者 vs 强于综合者）"),
    ]:
        add(f"| {rid} | {text} | | | {PENDING} |")
    add("")
    add("## 5. 声明")
    add("")
    add(f"- 本表不含任何真实教师姓名、签名或日期；AI 估计不构成难度校准结论。")
    add(f"- 两例是否“难度可比”必须由两位真实教师判断；在此之前不得宣称题本等难。")
    add("")
    return "\n".join(out)


DISPUTES = [
    ("D-01", "A02", "S5 中“患者询问是否需要激素或免疫抑制剂”是否过度提示（它把“免疫抑制是否有指征”变成显性考点）", "保留（真实场景常见，且问题中性）；或删除，让学生自行提出", "保留，但在锚点中明确“主动提出”与“被问及后回答”分开计分"),
    ("D-02", "A02", "OSS 右 5/左 4：恰在阈值（≥5，至少一眼）上，是否适合；是否应改为双眼均明确≥5 或附 van Bijsterveld 评分", "维持边界值以考查“至少一眼”规则；或统一为明确阳性", "维持，教师裁定"),
    ("D-03", "A02", "锚点依据哪套标准：2016 ACR/EULAR（研究分类）、2002 AECG、还是国内《原发性干燥综合征诊疗规范》（UNVERIFIED）", "以 2016 为主、说明差异；国内规范核对原文后再补充", "2016 为主"),
    ("D-04", "A02", "抗 SSA 阴性（常规法）后，是否要求/鼓励第二种方法复测（如免疫印迹/线性免疫分析，区分 Ro60/Ro52）；是否计入高分要点", "作为“加分项”而非“必须项”；本科生以知道“常规法阴性不绝对”为足", "加分项"),
    ("D-05", "A02", "唇腺活检在本病例是“应当考虑”还是“必须掌握”；是否应先做唾液流率/眼科复查/短期随访再决定", "先唾液流率，随后转诊活检；强调适应证、知情同意和在使用激素前取材", "先流率后活检"),
    ("D-06", "A02", "羟氯喹等药物是否可用于关节痛/乏力：EULAR 2020 对干燥症状的推荐与对系统/关节表现的推荐如何区分（原文未取得全文）", "锚点只要求“无指征不启动系统免疫抑制”，不对羟氯喹作硬性对错判定", "不作硬性判定"),
    ("D-07", "A02", "腮腺超声不属于 2016 标准条目：是否保留；保留则必须标注“非计分、辅助、本地可及性不同”", "保留并标注；锚点不奖励“凭超声确诊”", "保留并标注"),
    ("D-08", "A02", "ANA 1:160 斑点型伴抗 SSA/SSB 阴性：是否需要提示 ENA 复核（如其他抗体）；其意义对本科生的深度", "仅要求知道 ANA 非计分条目、不特异", "仅此深度"),
    ("D-09", "A02", "ESR 28、IgG 17.8 g/L、ANA 1:160、RF 弱阳性的组合是否过度偏向干燥综合征，削弱“诊断不确定”的设计意图", "保留（真实血清阴性患者常有此类非特异异常），但锚点明确它们不是条目", "保留"),
    ("D-10", "A02", "是否需要加入抗 CCP/抗 dsDNA 等以排除重叠（继发性干燥综合征）；当前设计为“无滑膜炎/皮疹/蛋白尿，故随访、按需查”", "维持按需查", "维持"),
    ("D-11", "A02", "其他干眼（睑板腺功能障碍、蒸发过强型）未提供睑板腺检查信息，学生只能靠推理：是否需要补充一句眼科描述", "不补充，以保持信息量与 A01 可比", "不补充"),
    ("D-15", "A01+A02", "两例共享“勿过度诊断+随访”元模式：应试策略“凡事不确定+随访”是否能在两例都拿中高分；A02 已在锚点与 S5 问题中要求“把握程度、决定性检查、对症方案”，是否足够", "增加“万能不确定”封顶规则（见量表审核表 R-03）", "封顶规则"),
    ("D-17", "A01 vs T02", "A01 与训练病例 T02 都以 2010 ACR/EULAR 计分为方法：这是“迁移考核”（可接受）还是“答案模式泄漏”（需区分）", "视为构念重叠而非内容泄漏：T02 为典型 RA（10 分），A01 为未分化（5 分），结论相反；教师判断是否足够", "构念重叠，可接受"),
    ("D-12", "A01", "“RF 弱阳性（低滴度）”缺少数值：2010 标准的“低滴度阳性”是 >ULN 且 ≤3×ULN，是否需要给出数值与参考范围", "给出数值（例如 RF 28 IU/mL，参考<20）以使计分可复核", "给出数值"),
    ("D-13", "A01", "S4 新增 ENA/肝炎/结核阴性结果（卡片 §2 未列）", "接受，因其使 S4 可解释；教师确认", "接受"),
    ("D-14", "A01", "UA 病程界定（卡片写“<12 个月且不满足特定分类标准”）与中文教材/EULAR 口径是否一致（v1 清单 Q-02）", "教师裁定", "—"),
    ("D-16", "A01+A02", "两例难度不等时的处理：不改病例（依赖批内顺序平衡）/ 调整 A02 / 调整 A01（见 A04 §1.3 选项）", "待教师校准后决定", "—"),
]


def _dispute_form() -> str:
    out: list[str] = []
    add = out.append
    add("# 诊断及检查策略争议项清单")
    add("")
    add(f"> **状态：`{PENDING}`　review_origin：`{ORIGIN}`**。“AI 立场”列为“{AI_LABEL}”，仅说明起草时的取舍，**不是结论**；两位教师的裁定栏必须由真人填写。涉及临床判断的取舍一律由教师决定。")
    add("")
    add("## 1. 审核人")
    add("")
    add(_sig_block("REAL_TEACHER_1"))
    add(_sig_block("REAL_TEACHER_2"))
    add("## 2. 本轮新增争议项（A02 干燥症状待查与 A01/A02 相关）")
    add("")
    add("| ID | 病例 | 争议 | 备选方案 | AI 立场（草案取舍，非结论） | 教师1 裁定 | 教师2 裁定 | 状态 |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for did, case, issue, options, ai in sorted(DISPUTES, key=lambda d: int(d[0].split("-")[1])):
        add(f"| {did} | {case} | {issue} | {options} | {ai} | | | {PENDING} |")
    add("")
    add("## 3. 沿用自 v1 清单、仍未裁定的问题（`MEDICAL_REVIEW_ISSUES_v1.md` 第三节）")
    add("")
    add("| ID | 病例 | 内容摘要 | 教师1 | 教师2 | 状态 |")
    add("| --- | --- | --- | --- | --- | --- |")
    for qid, case, text in [
        ("Q-01", "A01", "病程 5 周/小关节 2 个是否仍体现“未分化”教学意图"),
        ("Q-02", "A01", "未分化关节炎病程界定在中文教材与 EULAR 的一致性"),
        ("Q-03", "A01", "随访总分维持 5 分 vs 升至 6 分的教学取舍"),
        ("Q-04", "A01", "抗 CCP 阴性/RF 低滴度 UA 的复评间隔"),
        ("Q-05", "T01", "实验室示意值与教学医院参考范围"),
        ("Q-06", "T01", "SLE 逐域计分表中“急性皮肤型狼疮 6 分”的教学取舍"),
        ("Q-07", "T02", "总分改为 10 分后“典型病例计分不敏感”教学点是否保留"),
        ("Q-08", "T02", "抗 CCP“强阳性”缺数值与方法"),
        ("Q-09", "T03", "嗜酸性粒细胞 0.18×10⁹/L 与 EGPA 的排除"),
        ("Q-11", "全部", "各指南的年份/版本核对"),
    ]:
        add(f"| {qid} | {case} | {text} | | | {PENDING} |")
    add("")
    add("（v1 清单 Q-10、Q-12 针对已被取代的旧 AOSD 版 A02，已**作废**，不再需要裁定。）")
    add("")
    add("## 4. 声明")
    add("")
    add("- 本清单不含任何真实教师姓名、签名或日期。争议项不因出现在清单中而被视为已解决。")
    add("")
    return "\n".join(out)


def _anchor_table() -> str:
    a01 = _load_payload("A01_assessment_payload_DRAFT.json")
    a02 = _load_payload("A02_assessment_payload_DRAFT.json")
    out: list[str] = []
    add = out.append
    add("# 评分锚点一致性表")
    add("")
    add(f"> **状态：`{PENDING}`　review_origin：`{ORIGIN}`**。用于核对：（1）A01、A02 的锚点是否对应同一能力定义、粒度相当；（2）锚点与六维量表权重是否一致；（3）锚点是否可由两位评分者一致使用。AI 的“一致性初判”属“{AI_LABEL}”。")
    add("")
    add("## 1. 审核人")
    add("")
    add(_sig_block("REAL_TEACHER_1"))
    add(_sig_block("REAL_TEACHER_2"))
    add("## 2. 逐维度一致性")
    add("")
    add("| 维度 | 研究权重（待确认） | A01 高分档可观察性 | A02 高分档可观察性 | AI 一致性初判（草案） | 教师1：一致/不一致+理由 | 教师2：一致/不一致+理由 | 状态 |")
    add("| --- | ---: | --- | --- | --- | --- | --- | --- |")
    observ = {
        "medical_knowledge": ("可计数：四项计分+入口条件", "可计数：五条目权重+入口/排除条件", "粒度相当"),
        "key_information": ("≥4 阳性、≥3 阴性", "≥4 阳性、≥4 阴性", "A02 要求阴性多 1 条；教师确认是否需统一"),
        "differential_diagnosis": ("≥6 个鉴别，各有支持/反对/排除证据", "≥6 个鉴别，各有支持/反对/排除检查", "相同"),
        "evidence_integration": ("写出 2+2+1+0=5<6", "写出 1+1+0=2<4 且指出未评估项与最大可达 3 分", "A02 推演更长；教师确认是否过高要求"),
        "clinical_decision": ("暂定诊断+1–3 月随访+触发条件", "检查优先级+对症+不启动免疫抑制+随访与升级", "A02 决策点更多"),
        "evidence_based_medicine": ("引用 2010 标准与早期关节炎推荐、避免长期激素、治疗前筛查", "引用 2016 标准与 EULAR 2020、活检风险、监测淋巴瘤标志", "相当；两处推荐版本均待教师核对"),
    }
    for key, zh, research, _t in DIMENSIONS:
        o1, o2, ai = observ[key]
        add(f"| {zh} | {research} | {o1} | {o2} | {ai} | | | {PENDING} |")
    add("")
    add("## 3. 载荷与卡片的一致性（技术核对）")
    add("")
    add("| 核对项 | 结果 | 方式 |")
    add("| --- | --- | --- |")
    for case, payload in (("A01", a01), ("A02", a02)):
        dims = payload["rubric"]["dimensions"] if payload else {}
        ok = dims == {k: w for k, _z, w, _t in DIMENSIONS}
        add(f"| {case} 载荷权重 = 研究量表 10/20/25/15/20/10 | {'一致' if ok else '不一致'} | `validate_assessment_payloads.py` |")
        anchors = payload["rubric"].get("anchors", {}) if payload else {}
        add(f"| {case} 载荷六维均含高/中/低锚点 | {'是' if len(anchors) == 6 else '否'} | `validate_assessment_payloads.py` |")
    add("")
    add("以上技术核对**只证明格式与权重一致**，不证明锚点医学上正确或评分者可一致使用。")
    add("")
    add("## 4. 评分者间一致性的预先检验（建议，需教师同意）")
    add("")
    add("| ID | 事项 | 教师1 | 教师2 | 状态 |")
    add("| --- | --- | --- | --- | --- |")
    for rid, text in [
        ("K-01", "正式评分前，两位评分者用 B 工作包样例（非 A01/A02 真实答卷）做独立试评，并比较各维度差"),
        ("K-02", "若某维度试评差异持续偏大，是修改该维度锚点，还是在裁定规则中处理"),
        ("K-03", "锚点中的“≥N 条”计数要求是否会鼓励“罗列式”答案；是否需要质量描述补充"),
    ]:
        add(f"| {rid} | {text} | | | {PENDING} |")
    add("")
    return "\n".join(out)


def _revision_log() -> str:
    out: list[str] = []
    add = out.append
    add("# 修改意见与复审记录")
    add("")
    add(f"> **状态：`{PENDING}`　review_origin：`{ORIGIN}`**。第一部分记录 AI 所做的“{AI_LABEL}”——它们**不是**教师审定；第二部分为教师意见与复审登记表，**全部为空**，由真实教师填写。")
    add("")
    add("## 1. AI 技术/医学草案复核记录（非教师审定）")
    add("")
    add("| # | 日期 | 对象 | 变更 | 原因 | 来源标签 | 是否教师批准 |")
    add("| --- | --- | --- | --- | --- | --- | --- |")
    rows = [
        ("1", "2026-10-18", "CASE-A02 学生可见表题与各阶段问题", "把“疑似原发性干燥综合征”等提示改为中性表述；S4/S5 问题不再提示“阴性抗 SSA 的局限”“不能做最终判断”", "r1 草案把假设与推理要点写进学生可见字段，会降低区分度并泄露答案", "AI technical/medical DRAFT re-check", "否（PENDING_REAL_REVIEW）"),
        ("2", "2026-10-18", "CASE-A02 S5", "删除“唇腺活检尚未实施”提示，改由学生自行提出", "该句暗示唇腺活检是答案", "AI technical/medical DRAFT re-check", "否"),
        ("3", "2026-10-18", "CASE-A02 S3", "“已知 HCV 感染”改为“抗 HCV 抗体阴性、HIV 抗体阴性”，并补充胸片、血糖/HbA1c/TSH、尿常规、ESR/CRP/IgG/C3/C4", "2016 标准排除条件为活动性（PCR 证实）HCV 感染等；原文表述不能体现排除", "AI technical/medical DRAFT re-check", "否"),
        ("4", "2026-10-18", "CASE-A02 S2", "眼表染色量化为 OSS 右 5/左 4", "原文“眼表染色异常”无法按 2016 标准计分", "AI technical/medical DRAFT re-check", "否"),
        ("5", "2026-10-18", "CASE-A02 计分推演", "增加 2016 逐项计分表：已知 2 分，唾液流率与唇腺活检未评估；抗 SSA 阴性时无创检查最多 3 分<4", "使“唇腺活检为何关键”有可核对的算术依据，并避免把未做检查当作阴性", "AI technical/medical DRAFT re-check", "否"),
        ("6", "2026-10-18", "CASE-A02 治疗策略", "明确不启动系统激素/免疫抑制并说明会干扰活检评分；羟氯喹列为争议项 D-06", "避免无指征免疫抑制；对 EULAR 2020 原文未取得全文，不作硬性断言", "AI technical/medical DRAFT re-check", "否"),
        ("7", "2026-10-18", "CASE-A02 文献", "核实 2016 ACR/EULAR（两种刊载）、EULAR 2020、AECG 2002、Daniels 2011、Brito-Zerón 2016、TFOS DEWS II 的书目；中文规范、ESSDAI 原始文献、血清阴性比例标为 UNVERIFIED", "不得伪造引用；原文未取得的不作医学断言", "AI technical/medical DRAFT re-check", "否"),
        ("8", "2026-10-18", "CASE-A02 文件名", "A01_assessment_multisystem.md → A01_assessment_sicca.md；旧 AOSD 内容仅留 Git 历史", "名称与内容一致，避免现行 A02 被误认为 AOSD", "技术变更", "不适用"),
        ("9", "2026-10-18", "CASE-A01 载荷", "新增 A01 待审载荷（转录自卡片）；S4 增补 ENA/肝炎/结核阴性结果", "此前只有 A02 载荷，A01 无法按同一流程导入与校验", "AI technical/medical DRAFT re-check", "否（D-13 待教师确认）"),
        ("10", "2026-10-18", "A02 锚点", "新增六维高/中/低锚点（载荷 rubric.anchors）", "此前载荷只含权重，没有锚点", "AI technical/medical DRAFT re-check", "否"),
    ]
    for r in rows:
        add("| " + " | ".join(r) + " |")
    add("")
    add("## 2. 教师意见汇总与复审登记（空白，真人填写）")
    add("")
    add("| # | 病例/文件 | 意见来源教师 | 意见日期 | 意见 | 严重度 | 处理人 | 处理说明 | 修订后版本 | 复审教师 | 复审日期 | 复审结论 | 签字 |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for i in range(1, 11):
        add(f"| {i} | | | ____-__-__ | | | | | | | ____-__-__ | | |")
    add("")
    add("## 3. 规则")
    add("")
    add("- 医学内容的任何修改必须创建新版本；已发布并用于考试的版本冻结，不得静默更改。")
    add("- 每次修订后须由教师复审并在本表登记；AI 不得代填“复审结论”“签字”。")
    add("")
    return "\n".join(out)


def _readme() -> str:
    return f"""# 真实教师审核材料包（可直接签署）

> **全部条目状态：`{PENDING}`；review_origin：`{ORIGIN}`。**
> 本目录由 AI 准备，**不含任何教师姓名、日期、签字或审核结论**。AI 的检查一律标注为“{AI_LABEL}”。
> 由 `scripts/grant/build_case_review_forms.py` 生成（`--check` 可检测与磁盘文件的漂移）。

## 内容

| 文件 | 用途 | 给谁 |
| --- | --- | --- |
| `CASE_REVIEW_FORM_T01.md` … `T04.md` | 4 份训练病例（SLE / RA / ANCA 血管炎 / 炎性肌病）审核表 | 两位教师各自独立填写 |
| `CASE_REVIEW_FORM_A01.md`、`CASE_REVIEW_FORM_A02.md` | 2 份独立考核病例审核表（含学生可见内容摘录、考核专项核对） | 同上 |
| `RUBRIC_REVIEW_FORM.md` | 六维量表：权重（10/20/25/15/20/10 待确认；训练权重 20/20/20/15/15/10 不变）、A01/A02 锚点、裁决阈值 | 同上 |
| `DIFFICULTY_MATCH_A01_A02.md` | A01/A02 难度匹配表（AI 估计 + 载荷字符数 + 教师判断） | 同上 |
| `DISPUTE_LIST.md` | 诊断及检查策略争议项（含沿用的 v1 未决问题） | 同上 |
| `ANCHOR_CONSISTENCY_TABLE.md` | 评分锚点一致性表 | 同上 |
| `REVISION_REREVIEW_LOG.md` | AI 草案复核记录（非审定）+ 教师意见与复审登记（空白） | 教师/课题组 |
| `REVIEW_ITEMS_MASTER_BLANK.csv` | 全部核对项的机器可读空白清单 | 课题组统计用 |

## 使用流程

1. 把本目录整体（含 `../A01_*.md` 病例卡与 `../A01_assessment_payload_DRAFT.json`、`../A02_assessment_payload_DRAFT.json`）分别发给两位真实风湿科教师。
2. 两位教师**独立**填写，不互相讨论、不参考对方结论（每份表有独立性声明与利益冲突栏）。
3. 收回后由课题组录入 `REVIEW_ITEMS_MASTER_BLANK.csv`（另存为新文件，不覆盖空白模板），任一指标 ≤2 分或结论冲突的病例进入修订；冲突由第三位教师/教研室仲裁。
4. 修订按 `REVISION_REREVIEW_LOG.md` 登记并复审；医学内容修改必须创建新版本。
5. 独立考核病例（A01、A02）还须两位教师在系统内各自提交表单审核，管理员核验后才能发布；本材料包**不能**代替系统内审核，更**不能**由管理员或 AI 代签。

## 状态图例

| 状态 | 含义 |
| --- | --- |
| `{PENDING}` | 尚无真实教师审核（当前全部条目） |
| `{ORIGIN}` | 真实人工审核尚未进行；审核教师完成后改为 `REAL_HUMAN_REVIEW_CONDUCTED` |

## 诚实声明

- 没有任何一份病例、量表、难度匹配或争议项在此材料包中被审定。
- AI 修订只代表技术/医学草案复核；不得在申报材料中表述为“已通过专家审核”。
"""


def build() -> dict[str, str]:
    files: dict[str, str] = {"README.md": _readme()}
    master_rows: list[tuple[str, str, str, str]] = []
    for case in CASES:
        files[f"CASE_REVIEW_FORM_{case['id'].split('-')[1]}.md"] = _case_form(case)
        items = COMMON_ITEMS + (EXAM_ITEMS if case["kind"] == "独立考核病例" else []) + case["specific"]
        for item_id, text in items:
            master_rows.append((f"{case['id']}/{item_id}", case["id"], f"CASE_REVIEW_FORM_{case['id'].split('-')[1]}.md", text))
    files["RUBRIC_REVIEW_FORM.md"] = _rubric_form()
    files["DIFFICULTY_MATCH_A01_A02.md"] = _difficulty_form()
    files["DISPUTE_LIST.md"] = _dispute_form()
    files["ANCHOR_CONSISTENCY_TABLE.md"] = _anchor_table()
    files["REVISION_REREVIEW_LOG.md"] = _revision_log()
    for key, zh, research, _t in DIMENSIONS:
        master_rows.append((f"RUBRIC/W-{key}", "RUBRIC", "RUBRIC_REVIEW_FORM.md", f"权重确认：{zh} 研究权重 {research}（待确认）"))
    for did, case, issue, _o, _a in DISPUTES:
        master_rows.append((f"DISPUTE/{did}", case, "DISPUTE_LIST.md", issue))
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["item_id", "case_id", "form_file", "item", "teacher1_response", "teacher2_response",
                     "reviewer_name_1", "reviewer_name_2", "review_date_1", "review_date_2", "status", "review_origin"])
    for item_id, case_id, form_file, text in master_rows:
        writer.writerow([item_id, case_id, form_file, text, "", "", "", "", "", "", PENDING, ORIGIN])
    files["REVIEW_ITEMS_MASTER_BLANK.csv"] = buf.getvalue()
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true", help="exit 1 if files on disk differ from a fresh build")
    args = parser.parse_args(argv)
    files = build()
    if args.check:
        drift = [n for n, c in files.items() if not (args.out / n).is_file() or (args.out / n).read_text(encoding="utf-8") != c]
        for name in drift:
            print(f"DRIFT: {name}")
        print("OK: review forms match the generator" if not drift else f"{len(drift)} file(s) differ")
        return 1 if drift else 0
    args.out.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (args.out / name).write_text(content, encoding="utf-8")
    print(f"wrote {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
