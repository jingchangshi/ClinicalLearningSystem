#!/usr/bin/env python3
"""Global consistency check: no *current* document may still offer 方案 B.

The applicant's teaching organisation forbids splitting a 7-student batch into two
arms, so the study is locked to whole-batch cluster allocation (方案 A). 方案 B may
survive only inside historical revision notes, and there it must be marked 已否决.

This script is deliberately a *text* check: the failure mode it guards against is
a document that quietly keeps recommending the rejected design, or keeps quoting
its numbers, after the decision was made. A human reading one file would miss it.

Files scanned = the current, in-force documents. Files exempt = the historical
revision notes (v1/v2), which are allowed to describe what was once proposed.

Since the final round it also enforces the R7.4 mechanical checks across every
current document (see ``R74_RULES`` / ``R74_REQUIRED``): exact project title, no
in-class random grouping, A02 is the sicca case and the retired AOSD case is not an
exam form, D1/T0 does not feed the competency profile, D4/D5 recommendations come
from D2/D3 evidence, synthetic data is never framed as efficacy, a single two-sided
p definition (no unconditional "minimum 2/35"), a truthful ethics status, and the
real study is never written as completed.

R9 adds two more layers:

* ``R9_CONSISTENCY`` -- the §9 cross-document claims (A01 is undifferentiated
  polyarthritis, A02 is sicca of undetermined cause, both public drafts are
  development demos awaiting confidential re-authoring and real teacher review, the
  six-dimension research weights are provisionally 10/20/25/15/20/10 and the training
  scale 20/20/20/15/15/10 is not overridden, D1/D6 independent, D2/D3 build the
  profile, D4/D5 personalise, the CBL arm receives no ClinPath-only training, the
  unit of study is 7 cohorts, the other 21 students are unconfirmed, and there is no
  real teaching effect, no ethics approval and no real teacher signature). Each names
  the file that must carry the statement; a missing file is a failure.
* ``R9_RULES`` -- per-line honesty rules (A01/A02 topic swap, the training weights
  being rewritten to the research scale, a claimed real teacher signature).
* ``R9_DELIVERABLES`` -- the task brief §12 deliverable paths. A missing one is a
  failure, never a skip.

A key document that is missing is a failure, not a skip.

Usage::

    python3 scripts/grant/check_protocol_consistency.py [--json]

Exit codes: 0 clean, 1 violations found, 2 a required document is missing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRANT = REPO_ROOT / "docs" / "teaching_grant_2026"

# Documents that are in force. 方案 B must not be recommended or left open here.
CURRENT_DOCUMENTS = [
    "STATUS.md",
    "EVIDENCE_INDEX.md",
    "TEACHER_REVIEW_PACKET.md",
    "evidence/E5_protocol/E5_01_research_protocol.md",
    "evidence/E5_protocol/E5_02_SAP_statistical_analysis_plan.md",
    "evidence/E5_protocol/E5_03_ethics_privacy.md",
    "evidence/E5_protocol/E5_04_application_text.md",
    "evidence/E5_protocol/E5_04_placeholders.md",
    "evidence/E5_protocol/E5_protocol_data_dictionary.md",
    "evidence/E5_protocol/STATUS_E5.md",
    "evidence/E5_protocol/T2_7day_teaching_plan.md",
    "evidence/E5_protocol/T3_design_comparison.md",
    "evidence/E5_protocol/T3_personalization_validation.md",
    "workpackages/A_cases/A04_assessment_quality_control.md",
    "workpackages/DATA_DICTIONARY.md",
    "evidence/E1_teaching_credentials/README.md",
    "evidence/E2_platform/README.md",
    "evidence/E3_cases_rubric/README.md",
    "evidence/E4_validation/README.md",
    "FINAL_DELIVERY/ARCHITECTURE.md",
    "FINAL_DELIVERY/IMPLEMENTATION_STATUS.md",
    "FINAL_DELIVERY/TEST_REPORT.md",
    "FINAL_DELIVERY/EVIDENCE_MANIFEST.md",
    "FINAL_DELIVERY/RESEARCH_PROTOCOL_FINAL.md",
    "FINAL_DELIVERY/STATISTICAL_ANALYSIS_PLAN.md",
    "FINAL_DELIVERY/CASE_REVIEW_STATUS.md",
    "FINAL_DELIVERY/HUMAN_ACTION_CHECKLIST.md",
    "FINAL_DELIVERY/APPLICATION_SUBMISSION_CHECKLIST.md",
    "FINAL_DELIVERY/DEPLOYMENT_READINESS.md",
    "FINAL_DELIVERY/FINAL_REPORT_ZH.md",
    "FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md",
    "FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md",
]

# Globs of additional current documents (their absence is not an error; any match
# is scanned). Historical records and the review-issue log are exempt.
CURRENT_GLOBS = [
    "APPLICATION_PACKAGE/*.md",
    "workpackages/A_cases/*.md",
    "workpackages/B_rubric/*.md",
]
EXEMPT_FROM_GLOBS = {
    "workpackages/A_cases/MEDICAL_REVIEW_ISSUES_v1.md",  # historical issue log of the old A02
    "workpackages/A_cases/A02_REPLACEMENT_REVIEW.md",  # documents the replacement itself
}

# Files that must exist for the application to be consistent. A missing one is a
# failure (exit 2): "file not found, so the check passes" is exactly the bug.
REQUIRED_EXTRA = [
    "workpackages/A_cases/A02_assessment_payload_DRAFT.json",
    "workpackages/A_cases/A01_case_index.md",
]

# Historical records: allowed to describe 方案 B, but must mark it rejected.
HISTORICAL_DOCUMENTS = [
    "evidence/E5_protocol/PROTOCOL_REVISION_NOTES_v1.md",
    "evidence/E5_protocol/PROTOCOL_REVISION_NOTES_v2.md",
    "evidence/E5_protocol/PROTOCOL_REVISION_NOTES_v3.md",
]

# 方案 B artefacts that must not be cited as part of the current plan.
FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"推荐方案\s*B", "recommends 方案 B"),
    (r"方案\s*B\s*为(推荐|优先|首选)", "names 方案 B as the preferred design"),
    (r"方案\s*B\s*必须", "treats 方案 B as required"),
    (r"待(教研室)?确认.{0,20}方案\s*[AB]", "leaves the A/B choice open"),
    (r"(是否|能否)(允许|采用).{0,12}班内(随机|分组)", "leaves within-batch allocation open"),
    (r"班内\s*3\s*[+＋]\s*4", "cites the rejected within-batch 3+4 split"),
    (r"每批\s*7\s*人(内部|内)\s*3", "cites the rejected within-batch split"),
    # 24/25 is only a violation when it describes *arm* sizes; the same numbers
    # legitimately describe the X/Y form-order split under whole-batch allocation.
    (r"(?=.*24\s*(?:vs|比|:|：)\s*25)(?=.*(?:每臂|两臂|组别|干预组|对照组)).*",
     "cites 方案 B's 24 vs 25 arm sizes"),
    (r"35\s*[\^⁷]|6\.4\s*[×x]\s*10", "cites 方案 B's 35^7 permutation space"),
    (r"Monte\s*Carlo\s*置换", "cites 方案 B's Monte Carlo permutation test"),
    (r"分层置换检验", "cites 方案 B's stratified permutation test"),
    (r"残差自由度\s*=?\s*40|df\s*=\s*40", "cites 方案 B's residual df of 40"),
    # Plan A must say batch fixed effects are NOT estimable; flagging the phrase
    # unconditionally would flag that correct statement too, so negations are
    # handled by REJECTION_MARKERS below.
    (r"批次固定效应", "cites 方案 B's batch fixed effects as a model term"),
    # Plan B's figure was d ~ 0.81; plan A's is d ~ 0.87, so match the exact
    # plan-B value rather than a prefix (0.8 would also match 0.87).
    (r"d\s*[≈=]\s*0\.81\b", "cites an individual-level power figure for 方案 B"),
]

# A line may mention a forbidden pattern only if it is explicitly rejecting it.
# A line is not a violation if it is rejecting/negating the thing it mentions.
REJECTION_MARKERS = (
    "已否决", "被否决", "否决", "已删除", "作废", "不再", "不得", "禁止", "曾提出", "历史",
    # Negations that make a mention correct rather than a violation.
    "不可估", "不可识别", "共线", "不能", "无法", "删除", "不是",
)



PROJECT_TITLE = "基于人工智能辅助临床推理训练的医学生个性化学习与形成性评价教学改革研究"
TITLE_STEM = "基于人工智能辅助临床推理训练"

# A line is only a violation if it does not carry one of these honesty markers.
R74_HONEST_MARKERS = (
    "取代", "替换", "替代", "训练池", "训练库", "种子病例", "过期表述", "旧版", "旧 A02", "旧A02", "历史", "作废", "否决", "已被", "superseded",
    "Git 历史", "不得", "不能", "并非", "无条件", "禁止", "尚未", "尚无", "待填", "无法", "不预设",
    "不是", "不可能", "没有", "删除", "错误引文", "历史措辞", "历史缺口", "原写", "原表述", "已更正", "未获", "未取得", "未开展", "未完成", "拟", "计划", "排除", "鉴别",
)

# Being in the training pool is not evidence that a "CASE-A02 is AOSD" claim is
# historical: the seed Still case lives in the training pool *and* used to be A02, so a
# line that merely says 训练池/种子病例 would let a stale "current A02 is Still" claim
# through. The A02/AOSD rule therefore uses its own marker set.
_TRAINING_POOL_MARKERS = ("训练池", "训练库", "种子病例")

# Rule index -> the markers that make a match honest. Rules not listed use R74_HONEST_MARKERS.
R74_HONEST_MARKERS_BY_RULE: dict[int, tuple[str, ...]] = {
    0: tuple(m for m in R74_HONEST_MARKERS if m not in _TRAINING_POOL_MARKERS)
    + ("不重叠", "互不重叠", "无同病种"),
}

# (regex, why, honest-if-negated-inside-match). Matching is per line.
R74_RULES: list[tuple[str, str, bool]] = [
    # A02 / AOSD
    (r"(A02|考核|题本|独立考核)[^。|]{0,30}(AOSD|成人\s*Still|Still\s*病)|(AOSD|成人\s*Still)[^。|]{0,30}(A02|考核题本|独立考核)",
     "旧 AOSD 病例被列为现行 A02/考核题本", False),
    # in-class random grouping
    (r"(班内|批内|批次内|课堂内|同批内)\s*(随机|分组|分层)|推荐班内", "出现班内/批内随机分组", False),
    # D1/T0 feeding the profile
    (r"(D1|T0|基线考核|独立考核)[^。|]{0,30}(更新|形成|建立|进入|写入|计入)[^。|]{0,8}(能力画像|画像)",
     "D1/T0 被写成进入能力画像", True),
    # D4/D5 recommendations from D1/T0
    (r"(D4|D5)[^。|]{0,30}(推荐|个性化|强化)[^。|]{0,20}(来自|基于|依据|根据|驱动)[^。|]{0,10}(D1|T0|基线考核|独立考核)",
     "D4/D5 推荐被写成来自 D1/T0 而非 D2/D3 证据", True),
    # two-sided p
    (r"最小[^。|]{0,10}双侧\s*[Pp][^。|]{0,6}[=＝≈为]?\s*2\s*/\s*35", "无条件宣称最小双侧 P 为 2/35", False),
    (r"[Pp]\s*[=＝]\s*2\s*/\s*35[^。|]{0,12}(不可达|最小)", "无条件宣称 P=2/35 为下限", False),
    (r"α\s*[=＝]\s*0\.05[^。|]{0,12}不可达", "无条件宣称 α=0.05 不可达", False),
    (r"2\s*[×x\*]\s*min\s*\(", "出现另一种双侧 P 定义（2×min）", False),
    # ethics
    (r"(伦理|IRB)[^。|]{0,10}(已获批|已批准|已通过|已取得批件|已获得批件|已获)", "声称已取得伦理批准", True),
    (r"批件号\s*[:：]?\s*[A-Za-z0-9][A-Za-z0-9\-—_/]{2,}", "出现伦理批件号", False),
    # real study written as done
    (r"(已完成|已开展|已实施|已纳入|已招募)[^。|]{0,10}(7\s*批|49\s*名|真实学生|真实研究|正式研究|教学研究)",
     "把未开始的真实研究写成已完成", True),
    # synthetic as efficacy
    (r"(合成|虚拟学生|SYNTHETIC|模拟)[^。|]{0,24}(证明|显著提升|疗效|有效性已|效果显著)", "合成数据被写成效果证据", True),
    # fake official artefacts
    (r"(公章|签章|盖章)[^。|]{0,6}(已加盖|已盖|已签)", "声称已有单位签章", True),
]

# Required statements: (file, regex, description). The regex must match somewhere.
R74_REQUIRED: list[tuple[str, str, str]] = [
    ("evidence/E5_protocol/E5_01_research_protocol.md", PROJECT_TITLE, "研究方案含正式项目名称"),
    ("evidence/E5_protocol/E5_04_application_text.md", PROJECT_TITLE, "申报正文含正式项目名称"),
    ("FINAL_DELIVERY/FINAL_REPORT_ZH.md", PROJECT_TITLE, "最终报告含正式项目名称"),
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"T0[^。]{0,40}不[^。]{0,12}(能力画像|画像)", "研究方案写明 T0 不进入能力画像"),
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"D4/D5[^。|]{0,40}D2/D3\s*形成性训练证据", "研究方案写明 D4/D5 来自 D2/D3 证据"),
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"不得无条件宣称最小双侧 P", "研究方案不无条件宣称 2/35"),
    ("evidence/E5_protocol/E5_03_ethics_privacy.md", r"尚未获得批件|尚无批件|无批件", "伦理文件写明尚无批件"),
    ("evidence/E5_protocol/E5_03_ethics_privacy.md", r"尚未提交", "伦理文件写明尚未提交"),
    ("workpackages/A_cases/A01_case_index.md", r"CASE-A02[^\n]*干燥", "病例索引中 A02 为干燥症状病例"),
    ("evidence/E5_protocol/STATUS_E5.md", r"双侧 P", "状态文件含 P 值定义"),
]


def _scan(path: Path) -> list[dict]:
    """Scan one document.

    A mention is acceptable when the line itself rejects it, or when it sits in a
    table whose header (or the nearest preceding heading) marks the whole block as
    superseded — e.g. a "v2.0（作废） vs v3.0（现行）" comparison table. Without the
    table-context rule, documenting *what was rejected* would itself be flagged.
    """

    violations: list[dict] = []
    text = path.read_text(encoding="utf-8")
    table_exempt = False
    previous_was_table = False

    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        is_table_row = stripped.startswith("|")

        if is_table_row and not previous_was_table:
            # First row of a new table: its header decides the whole table.
            table_exempt = any(marker in line for marker in REJECTION_MARKERS)
        elif not is_table_row:
            table_exempt = False

        for pattern, why in FORBIDDEN_PATTERNS:
            if not re.search(pattern, line):
                continue
            if any(marker in line for marker in REJECTION_MARKERS):
                continue
            if table_exempt:
                continue
            violations.append(
                {"file": str(path.relative_to(REPO_ROOT)), "line": number, "why": why, "text": stripped[:160]}
            )

        previous_was_table = is_table_row

    violations.extend(_scan_r74(path, text))
    violations.extend(_scan_r9(path, text))
    return violations


def _scan_r74(path: Path, text: str) -> list[dict]:
    """R7.4 mechanical rules, per line."""
    out: list[dict] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
        # Title consistency: a quoted stem must carry the complete official title.
        if TITLE_STEM in line and PROJECT_TITLE not in line:
            out.append({"file": str(path.relative_to(REPO_ROOT)), "line": number,
                        "why": "项目名称不一致（出现名称片段但不是完整正式名称）", "text": line.strip()[:160]})
        for index, (pattern, why, negation_inside) in enumerate(R74_RULES):
            markers = R74_HONEST_MARKERS_BY_RULE.get(index, R74_HONEST_MARKERS)
            for match in re.finditer(pattern, line):
                span = match.group(0)
                if negation_inside and any(n in span for n in ("不", "未", "禁止", "无")):
                    continue
                if any(marker in line for marker in markers):
                    continue
                out.append({"file": str(path.relative_to(REPO_ROOT)), "line": number, "why": why,
                            "text": line.strip()[:160]})
                break
    return out


def _check_required() -> list[dict]:
    """Required statements and structured-file checks."""
    out: list[dict] = []
    for relative, pattern, description in R74_REQUIRED:
        path = GRANT / relative
        if not path.is_file():
            out.append({"file": relative, "line": 0, "why": f"缺失必需文件，无法核对：{description}", "text": ""})
            continue
        if re.search(pattern, path.read_text(encoding="utf-8")) is None:
            out.append({"file": relative, "line": 0, "why": f"缺少必需表述：{description}", "text": ""})

    payload = GRANT / "workpackages/A_cases/A02_assessment_payload_DRAFT.json"
    if payload.is_file():
        try:
            data = json.loads(payload.read_text(encoding="utf-8"))
            blob = json.dumps(data, ensure_ascii=False)
            if "干燥" not in blob:
                out.append({"file": str(payload.relative_to(GRANT)), "line": 0, "why": "A02 载荷不是干燥症状病例", "text": ""})
            if re.search(r"AOSD|成人\s*Still|Still\s*病", blob):
                out.append({"file": str(payload.relative_to(GRANT)), "line": 0, "why": "A02 载荷仍含 AOSD/Still", "text": ""})
        except json.JSONDecodeError as exc:
            out.append({"file": str(payload.relative_to(GRANT)), "line": 0, "why": f"A02 载荷不是合法 JSON：{exc}", "text": ""})
    return out


# ---------------------------------------------------------------------------
# R9: §9 cross-document consistency, per-line honesty rules, §12 deliverables
# ---------------------------------------------------------------------------

# Forbidden statements about the §9 facts. Per line; a line that negates or marks
# the statement as historical is not a violation.
R9_RULES: list[tuple[str, str, bool]] = [
    (r"A01[^\n]{0,4}(干燥|口干|眼干)|A02[^\n]{0,4}未分化多关节炎",
     "A01/A02 主题互换（A01=未分化多关节炎，A02=干燥症状待查）", False),
    (r"(训练|形成性)[^\n]{0,12}权重[^\n]{0,12}(改为|调整为|覆盖为|统一为|已改为)\s*10\s*/\s*20",
     "把平台形成性训练权重 20/20/20/15/15/10 改写成研究量表权重", False),
    # `[^|\n]` rather than `[^\n]`: the claim must sit inside one table cell, so a
    # row that honestly says "待两位真实教师填写与签字 | 已准备材料包" is not read as
    # "the teachers have signed".
    (r"(真实)?(教师|专家)[^|\n]{0,6}(签字|签名|签署)[^|\n]{0,8}(已|完成|齐备|全部到位)",
     "声称已取得真实教师签字", True),
]

# §9 statements that must be present in the named document. The file must also
# exist: "file not found, so the statement trivially holds" is the bug being
# guarded against, so a missing file is reported as a violation too.
R9_CONSISTENCY: list[tuple[str, str, str]] = [
    # A01 / A02 identities
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"A01[^\n]{0,6}未分化多关节炎",
     "研究方案：A01 为未分化多关节炎"),
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"A02[^\n]{0,12}干燥",
     "研究方案：A02 为原因待查的干燥症状"),
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"原因待查",
     "研究方案：A02 为「原因待查」（未确诊）"),
    ("evidence/E5_protocol/E5_04_application_text.md", r"A01\s*未分化多关节炎",
     "申报正文：A01 为未分化多关节炎"),
    ("evidence/E5_protocol/E5_04_application_text.md", r"A02\s*干燥症状待查",
     "申报正文：A02 为干燥症状待查"),
    ("evidence/E5_protocol/T2_7day_teaching_plan.md", r"CASE-A01[^\n]{0,10}未分化多关节炎",
     "教学实施表：A01 为未分化多关节炎"),
    ("evidence/E5_protocol/T2_7day_teaching_plan.md", r"CASE-A02[^\n]{0,20}干燥",
     "教学实施表：A02 为干燥症状"),
    ("workpackages/A_cases/A04_assessment_quality_control.md", r"A01[^\n]{0,6}未分化多关节炎",
     "A04：A01 为未分化多关节炎"),
    ("workpackages/A_cases/A04_assessment_quality_control.md", r"A02[^\n]{0,20}干燥",
     "A04：A02 为干燥症状"),
    # public drafts are development demos awaiting confidential re-authoring + review
    ("workpackages/A_cases/A04_assessment_quality_control.md", r"PENDING_REAL_REVIEW",
     "A04：两例公开稿为待真实审核的开发演示稿"),
    ("workpackages/A_cases/A04_assessment_quality_control.md", r"保密重新命制",
     "A04：正式题本须保密重新命制"),
    ("evidence/E5_protocol/T2_7day_teaching_plan.md", r"保密重新命制",
     "教学实施表：正式题本须保密重新命制"),
    ("FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md", r"保密重新命制",
     "官方核验：正式题本须保密重新命制"),
    ("FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md", r"真实教师审核",
     "官方核验：正式题本须经真实教师审核"),
    ("FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md", r"无真实教师签字",
     "官方核验：无真实教师签字"),
    # six-dimension weights: research scale provisional, training scale not overridden
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"10/20/25/15/20/10",
     "研究方案：研究量表权重 10/20/25/15/20/10"),
    ("evidence/E5_protocol/E5_01_research_protocol.md",
     r"20/20/20/15/15/10[^\n]{0,12}不得被其覆盖",
     "研究方案：训练量表权重 20/20/20/15/15/10 不被覆盖"),
    ("evidence/E5_protocol/T2_7day_teaching_plan.md", r"10/20/25/15/20/10",
     "教学实施表：研究量表权重 10/20/25/15/20/10 暂定"),
    ("evidence/E5_protocol/T2_7day_teaching_plan.md",
     r"20/20/20/15/15/10[^\n]{0,20}(不被|未改|不得)",
     "教学实施表：训练量表权重不被覆盖、本轮未改"),
    ("workpackages/A_cases/A04_assessment_quality_control.md", r"10/20/25/15/20/10",
     "A04：研究量表权重 10/20/25/15/20/10 待确认"),
    ("workpackages/A_cases/A04_assessment_quality_control.md",
     r"20/20/20/15/15/10[^\n]{0,20}(不被|未改|不得)",
     "A04：训练量表权重不被覆盖、本轮未改"),
    # stage semantics
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"D2/D3[^\n]{0,20}更新其能力画像",
     "研究方案：D2/D3 建立能力画像"),
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"D4/D5[^\n]{0,40}D2/D3\s*形成性训练证据",
     "研究方案：D4/D5 推荐来自 D2/D3 形成性训练证据"),
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"D6[^\n]{0,20}T1[^\n]{0,10}独立在线考核",
     "研究方案：D6 为独立后测 T1"),
    ("evidence/E5_protocol/T2_7day_teaching_plan.md", r"\| D1 \|[^\n]{0,12}T0 考核",
     "教学实施表：D1 为独立前测 T0"),
    ("evidence/E5_protocol/T2_7day_teaching_plan.md", r"\| D6 \|[^\n]{0,12}T1 考核",
     "教学实施表：D6 为独立后测 T1"),
    # CBL arm receives no ClinPath-only training
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"不[^\n]{0,4}使用平台的分步训练与导师追问",
     "研究方案：对照组不使用平台分步训练与导师追问"),
    ("evidence/E5_protocol/T2_7day_teaching_plan.md", r"不做平台个性化",
     "教学实施表：CBL 组不做平台个性化"),
    ("evidence/E5_protocol/E5_04_application_text.md", r"不开放ClinPath干预训练",
     "申报正文：CBL 组不开放 ClinPath 干预训练"),
    # unit of study, population, honest negatives
    ("evidence/E5_protocol/E5_01_research_protocol.md", r"7 个批次整群随机分配",
     "研究方案：研究单位为 7 个批次整群分配"),
    ("evidence/E5_protocol/T2_7day_teaching_plan.md", r"7 个批次",
     "教学实施表：研究单位为 7 个批次"),
    ("evidence/E5_protocol/E5_04_application_text.md", r"共7个批次",
     "申报正文：研究单位为 7 个批次"),
    ("evidence/E5_protocol/E5_02_SAP_statistical_analysis_plan.md", r"21 名学生[^\n]{0,40}待确认",
     "SAP：另 21 名学生的构成待确认"),
    ("evidence/E5_protocol/E5_04_application_text.md", r"21人[^\n]{0,24}【待填",
     "申报正文：21 人构成与是否重叠为【待填】"),
    ("evidence/E5_protocol/E5_04_application_text.md", r"无真实教学效果数据",
     "申报正文：无真实教学效果数据"),
    ("evidence/E5_protocol/E5_03_ethics_privacy.md", r"尚未获得批件|尚无批件|无批件",
     "伦理文件：尚无批件"),
    ("evidence/E5_protocol/E5_04_application_text.md", r"无任何真实教师签字",
     "申报正文：无任何真实教师签字"),
    ("FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md", r"阻塞研究启动",
     "真人待办清单：区分是否阻塞研究启动"),
    # The R9 checklist must stay standalone: the exposure decisions that
    # EXAM_SECURITY_FINAL.md points at have to actually be in it.
    ("FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md", r"仓库.{0,6}私有|改私有",
     "R9 待办清单：公开仓库暴露面处置（H18）"),
    ("FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md", r"E1\s*[—\-–~]\s*E5",
     "R9 待办清单：旧稿处置选项 E1—E5（H19）"),
    ("FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md", r"渠道\s*\*{0,2}P",
     "R9 待办清单：泄漏渠道 P 的核查（H22）"),
    ("FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md", r"UNVERIFIED|待核实引用",
     "R9 待办清单：待核实引用逐条核对（H21）"),
    ("FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md", r"A01'\s*/\s*A02'|A01'/A02'",
     "R9 待办清单：新命制保密题本 A01'/A02'"),
    ("FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md", r"改写\s*Git\s*历史|不得.{0,6}改写.{0,4}历史",
     "R9 待办清单：不得改写 Git 历史"),
    ("workpackages/DATA_DICTIONARY.md", r"训练暴露",
     "数据字典：含训练暴露字段（研究↔训练关联）"),
]

# (referencing document, checklist document). Every ``H<number>`` the referencing
# document attributes to the checklist must exist as a row in it, so renaming or
# deleting an item cannot silently pass. Ranges such as ``H18—H21`` are expanded.
CHECKLIST_CROSS_REFERENCES: list[tuple[str, str]] = [
    ("FINAL_DELIVERY/EXAM_SECURITY_FINAL.md", "FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md"),
    ("FINAL_DELIVERY/EXAM_FORM_REAUTHORING_REQUIREMENTS.md",
     "FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md"),
    ("FINAL_DELIVERY/EXAM_SECURE_IMPORT_SPEC.md", "FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md"),
    ("FINAL_DELIVERY/FORM_ORDER_DECISION_OPTIONS.md",
     "FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md"),
]

H_RANGE_RE = re.compile(r"H\s*(\d+)\s*[—–\-~]\s*H?\s*(\d+)")
H_ID_RE = re.compile(r"H\s*(\d+)")
H_ROW_RE = re.compile(r"^\|\s*H\s*(\d+)\s*\|", re.MULTILINE)


def referenced_h_ids(line: str) -> set[int]:
    """H ids on a line, expanding ranges like ``H18—H21``."""
    ids: set[int] = set()
    for match in H_RANGE_RE.finditer(line):
        low, high = int(match.group(1)), int(match.group(2))
        if low <= high:
            ids.update(range(low, high + 1))
    for match in H_ID_RE.finditer(line):
        ids.add(int(match.group(1)))
    return ids


def defined_h_ids(text: str) -> set[int]:
    """H ids that have their own row in the checklist table."""
    return {int(match.group(1)) for match in H_ROW_RE.finditer(text)}

# Task brief §12 deliverables. Every path must exist; a missing one means the
# round's evidence set is incomplete and the check fails (exit 2).
R9_DELIVERABLES: list[str] = [
    "FINAL_DELIVERY/R9_FINAL_REVIEW.md",
    "FINAL_DELIVERY/CBL_INTERVENTION_ISOLATION.md",
    "FINAL_DELIVERY/RESEARCH_TRAINING_LINKAGE.md",
    "FINAL_DELIVERY/EXAM_SECURITY_FINAL.md",
    "FINAL_DELIVERY/FORM_ORDER_DECISION_OPTIONS.md",
    "FINAL_DELIVERY/OFFICIAL_APPLICATION_VALIDATION.md",
    "FINAL_DELIVERY/R9_TEST_REPORT.md",
    "FINAL_DELIVERY/R9_HUMAN_ACTION_CHECKLIST.md",
    "FINAL_DELIVERY/R9_FINAL_REPORT_ZH.md",
]


def _scan_r9(path: Path, text: str) -> list[dict]:
    """R9 per-line honesty rules. Same honest-marker escape hatch as R7.4."""
    out: list[dict] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern, why, negation_inside in R9_RULES:
            match = re.search(pattern, line)
            if match is None:
                continue
            if negation_inside and any(n in match.group(0) for n in ("不", "未", "禁止", "无")):
                continue
            if any(marker in line for marker in R74_HONEST_MARKERS):
                continue
            out.append({"file": str(path.relative_to(REPO_ROOT)), "line": number, "why": why,
                        "text": line.strip()[:160]})
            break
    return out


def _check_r9_consistency() -> list[dict]:
    """§9 statements that must be present in the named documents."""
    out: list[dict] = []
    for relative, pattern, description in R9_CONSISTENCY:
        path = GRANT / relative
        if not path.is_file():
            out.append({"file": relative, "line": 0,
                        "why": f"缺失关键文档，§9 一致性无法核对：{description}", "text": ""})
            continue
        if re.search(pattern, path.read_text(encoding="utf-8")) is None:
            out.append({"file": relative, "line": 0, "why": f"缺少 §9 一致表述：{description}", "text": ""})
    return out


def _check_checklist_cross_references() -> list[dict]:
    """Every H id a document attributes to the checklist must exist in it.

    This is the guard for the failure mode that actually happened: a document
    cross-references "R9_HUMAN_ACTION_CHECKLIST.md H18—H21" while the checklist
    stops at H15, so the single most consequential decision (the public-repo
    exposure choice) is invisible to a reader of the checklist.
    """
    out: list[dict] = []
    for referencing, checklist in CHECKLIST_CROSS_REFERENCES:
        referencing_path = GRANT / referencing
        checklist_path = GRANT / checklist
        if not referencing_path.is_file() or not checklist_path.is_file():
            continue
        defined = defined_h_ids(checklist_path.read_text(encoding="utf-8"))
        basename = Path(checklist).name
        for number, line in enumerate(referencing_path.read_text(encoding="utf-8").splitlines(), start=1):
            if basename not in line:
                continue
            for h_id in sorted(referenced_h_ids(line)):
                if h_id not in defined:
                    out.append({
                        "file": referencing, "line": number,
                        "why": f"引用了 {basename} 的 H{h_id:02d}，但该编号在清单中没有对应条目",
                        "text": line.strip()[:160],
                    })
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    violations: list[dict] = []
    checked: list[str] = []
    missing: list[str] = []

    targets = list(CURRENT_DOCUMENTS)
    for pattern in CURRENT_GLOBS:
        for found in sorted(GRANT.glob(pattern)):
            relative = found.relative_to(GRANT).as_posix()
            if relative not in targets and relative not in EXEMPT_FROM_GLOBS:
                targets.append(relative)

    for relative in targets:
        path = GRANT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        checked.append(relative)
        violations.extend(_scan(path))

    for relative in REQUIRED_EXTRA:
        if not (GRANT / relative).is_file():
            missing.append(relative)

    for relative in R9_DELIVERABLES:
        if not (GRANT / relative).is_file():
            missing.append(relative)

    violations.extend(_check_required())
    violations.extend(_check_r9_consistency())
    violations.extend(_check_checklist_cross_references())

    # The historical notes must mark 方案 B as rejected.
    history_problems: list[str] = []
    for relative in HISTORICAL_DOCUMENTS:
        path = GRANT / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if "方案 B" in text or "方案B" in text:
            if not any(marker in text for marker in ("已否决", "已删除", "作废")):
                history_problems.append(f"{relative}: mentions 方案 B without marking it rejected")

    if args.json:
        print(json.dumps(
            {"checked": checked, "missing": missing, "violations": violations, "history": history_problems},
            ensure_ascii=False, indent=2,
        ))
    else:
        print("方案 A 唯一设计一致性检查")
        print("=" * 78)
        print(f"已扫描现行文档：{len(checked)} 份")
        for relative in checked:
            print(f"  - {relative}")
        if missing:
            print("\n缺失的关键文档（判定为失败，不是跳过）：")
            for relative in missing:
                print(f"  ! {relative}")
        print()
        if violations:
            print(f"发现 {len(violations)} 处违反（方案 B 残留、R7.4 机械规则或 §9 一致性）：")
            for item in violations:
                print(f"  FAIL {item['file']}:{item['line']}  [{item['why']}]")
                if item["text"]:
                    print(f"       {item['text']}")
        else:
            print("PASS 现行文档未推荐方案 B，R7.4 机械规则与 §9 一致性全部成立")
        if history_problems:
            print("\n历史修订记录问题：")
            for problem in history_problems:
                print(f"  FAIL {problem}")
        elif any((GRANT / h).is_file() for h in HISTORICAL_DOCUMENTS):
            print("PASS 历史修订记录中的方案 B 已标记为已否决")
        print()

    failed = bool(violations or history_problems or missing)
    if not args.json:
        print("结论：" + ("FAIL" if failed else "PASS"))
    if missing:
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
