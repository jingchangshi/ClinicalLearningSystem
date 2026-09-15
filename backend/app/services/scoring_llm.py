import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.llm.prompts.evaluation import CASE_EVALUATION_SYSTEM_PROMPT, CASE_EVALUATION_USER_TEMPLATE
from app.services.serializers import CORE_ABILITIES

WEIGHTS = {
    "medical_knowledge": 0.20,
    "key_information": 0.20,
    "differential_diagnosis": 0.20,
    "evidence_integration": 0.15,
    "clinical_decision": 0.15,
    "evidence_based_medicine": 0.10,
}


def score_with_rules(case: dict, answers: list[dict], rubric: dict) -> dict:
    answer_by_step = {item["step"]: item["answer_text"] for item in answers}
    all_text = "\n".join(answer_by_step.values())
    diagnosis_text = f"{case.get('standard_diagnosis', '')} {case.get('title', '')}"

    scores = {
        "medical_knowledge": _score_keywords(all_text, _diagnosis_keywords(diagnosis_text), 58, 12),
        "key_information": _score_keywords(
            answer_by_step.get("key_information", all_text),
            ["发热", "皮疹", "蛋白尿", "ANA", "血细胞减少", "补体", "抗体", "肌痛", "肺间质"],
            50,
            7,
        ),
        "differential_diagnosis": _score_keywords(
            answer_by_step.get("differential_diagnosis", all_text),
            ["感染", "AOSD", "Still", "HLH", "淋巴瘤", "MCTD", "APS", "血管炎"],
            48,
            8,
        ),
        "evidence_integration": _score_keywords(
            all_text,
            ["支持", "反对", "排除", "证据", "器官受累", "活动度", "矛盾"],
            52,
            7,
        ),
        "clinical_decision": _score_keywords(
            answer_by_step.get("treatment", all_text),
            ["激素", "免疫抑制剂", "感染筛查", "器官受累评估", "随访", "监测", "不良反应"],
            50,
            7,
        ),
        "evidence_based_medicine": _score_keywords(
            all_text,
            ["指南", "证据", "文献", "推荐级别", "EULAR", "ACR", "共识"],
            45,
            8,
        ),
    }
    total = round(sum(scores[key] * WEIGHTS[key] for key in CORE_ABILITIES), 1)
    strengths = _strengths(scores)
    weaknesses = _weaknesses(scores)
    return {
        **scores,
        "total_score": total,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "feedback": (
            f"本次总分 {total}。{strengths}；{weaknesses}。"
            "下一步建议围绕低分维度复盘诊断依据、鉴别排除和治疗证据。"
        ),
    }


class DimensionEvaluation(BaseModel):
    score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]
    missing_points: list[str]
    feedback: str


class CaseEvaluation(BaseModel):
    dimensions: dict[str, DimensionEvaluation]
    strengths: list[str]
    priority_gaps: list[str]
    overall_feedback: str
    safety_flags: list[str]


def evaluate_case_submission(case: dict, answers: list[dict], rubric: dict, llm_service) -> dict:
    """Use the semantic rubric when available; deterministic scoring remains a safe fallback."""
    rule_score = score_with_rules(case, answers, rubric)
    fallback = {"_fallback": True}
    try:
        raw = llm_service.chat_json(
            CASE_EVALUATION_SYSTEM_PROMPT,
            CASE_EVALUATION_USER_TEMPLATE.format(
                case=json.dumps(case, ensure_ascii=False), rubric=json.dumps(rubric, ensure_ascii=False),
                answers=json.dumps(answers, ensure_ascii=False), rule_evidence=json.dumps(rule_score, ensure_ascii=False),
            ),
            fallback,
        )
    except Exception:
        raw = fallback
    try:
        if raw == fallback:
            raise ValueError("LLM unavailable")
        evaluation = CaseEvaluation.model_validate(raw)
        if set(evaluation.dimensions) != set(CORE_ABILITIES):
            raise ValueError("unexpected competency dimensions")
    except (ValidationError, ValueError, TypeError):
        return {
            **rule_score,
            "evaluation_mode": "rule_fallback",
            "degraded": True,
            "rule_score": rule_score["total_score"],
            "ai_score": None,
            "evaluation_detail": {},
            "safety_flags": [],
        }

    scores = {key: round(evaluation.dimensions[key].score, 1) for key in CORE_ABILITIES}
    total = round(sum(scores[key] * WEIGHTS[key] for key in CORE_ABILITIES), 1)
    return {
        **scores,
        "total_score": total,
        "strengths": "；".join(evaluation.strengths),
        "weaknesses": "；".join(evaluation.priority_gaps),
        "feedback": evaluation.overall_feedback,
        "evaluation_mode": "ai",
        "degraded": False,
        "rule_score": rule_score["total_score"],
        "ai_score": total,
        "evaluation_detail": evaluation.model_dump(),
        "safety_flags": evaluation.safety_flags,
    }


def _score_keywords(text: str, keywords: list[str], base: int, step: int) -> float:
    lower_text = text.lower()
    hits = sum(1 for keyword in keywords if keyword.lower() in lower_text)
    length_bonus = min(len(text) // 80, 3) * 3
    return float(min(96, base + hits * step + length_bonus))


def _diagnosis_keywords(text: str) -> list[str]:
    keywords = ["SLE", "系统性红斑狼疮", "Still", "AOSD", "ANCA", "血管炎", "皮肌炎", "抗合成酶"]
    return [keyword for keyword in keywords if keyword.lower() in text.lower()] or keywords


def _strengths(scores: dict) -> str:
    best = max(CORE_ABILITIES, key=lambda key: scores[key])
    labels = {
        "medical_knowledge": "初步诊断方向较准确",
        "key_information": "能够提取部分关键病史和检查信息",
        "differential_diagnosis": "鉴别诊断覆盖较完整",
        "evidence_integration": "能尝试整合支持和反对证据",
        "clinical_decision": "治疗决策具有基本安全意识",
        "evidence_based_medicine": "能主动联系指南或证据来源",
    }
    return labels[best]


def _weaknesses(scores: dict) -> str:
    worst = min(CORE_ABILITIES, key=lambda key: scores[key])
    labels = {
        "medical_knowledge": "疾病谱和诊断标准掌握仍需加强",
        "key_information": "关键信息提取不够系统",
        "differential_diagnosis": "对感染、AOSD、HLH、淋巴瘤等排除逻辑不足",
        "evidence_integration": "支持证据和反对证据的权重说明不足",
        "clinical_decision": "治疗依据、风险评估和监测计划不够完整",
        "evidence_based_medicine": "循证医学意识不足，较少引用指南或证据等级",
    }
    return labels[worst]
