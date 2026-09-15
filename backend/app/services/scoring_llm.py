from pydantic import BaseModel, Field, ValidationError

from app.llm.prompts.evaluation import CASE_EVALUATION_SYSTEM_PROMPT, CASE_EVALUATION_USER_TEMPLATE
from app.services.llm_service import prompt_json
from app.services.serializers import ABILITY_LABELS, CORE_ABILITIES

WEIGHTS = {
    "medical_knowledge": 0.20,
    "key_information": 0.20,
    "differential_diagnosis": 0.20,
    "evidence_integration": 0.15,
    "clinical_decision": 0.15,
    "evidence_based_medicine": 0.10,
}

DIMENSION_KEYWORDS = {
    "medical_knowledge": ["SLE", "系统性红斑狼疮", "Still", "AOSD", "ANCA", "血管炎", "皮肌炎", "抗合成酶", "诊断标准"],
    "key_information": ["发热", "皮疹", "蛋白尿", "ANA", "血细胞减少", "补体", "抗体", "肌痛", "肺间质"],
    "differential_diagnosis": ["感染", "AOSD", "Still", "HLH", "淋巴瘤", "MCTD", "APS", "血管炎"],
    "evidence_integration": ["支持", "反对", "排除", "证据", "器官受累", "活动度", "矛盾"],
    "clinical_decision": ["激素", "免疫抑制剂", "感染筛查", "器官受累评估", "随访", "监测", "不良反应"],
    "evidence_based_medicine": ["指南", "证据", "文献", "推荐级别", "EULAR", "ACR", "共识"],
}

SAFETY_SIGNALS = {
    "未提及感染筛查，免疫抑制前存在安全隐患": ["感染筛查", "感染", "筛查", "结核", "乙肝"],
    "未提及治疗监测或随访计划": ["监测", "随访", "复查", "不良反应"],
    "未提及器官受累评估": ["器官受累", "肾功能", "尿蛋白", "肺功能", "神经系统"],
}


def score_with_rules(case: dict, answers: list[dict], rubric: dict) -> dict:
    answer_by_step = {item["step"]: item["answer_text"] for item in answers}
    all_text = "\n".join(answer_by_step.values())
    diagnosis_text = f"{case.get('standard_diagnosis', '')} {case.get('title', '')}"

    scores = {
        "medical_knowledge": _score_keywords(all_text, _diagnosis_keywords(diagnosis_text), 58, 12),
        "key_information": _score_keywords(
            answer_by_step.get("key_information", all_text), DIMENSION_KEYWORDS["key_information"], 50, 7
        ),
        "differential_diagnosis": _score_keywords(
            answer_by_step.get("differential_diagnosis", all_text), DIMENSION_KEYWORDS["differential_diagnosis"], 48, 8
        ),
        "evidence_integration": _score_keywords(all_text, DIMENSION_KEYWORDS["evidence_integration"], 52, 7),
        "clinical_decision": _score_keywords(
            answer_by_step.get("treatment", all_text), DIMENSION_KEYWORDS["clinical_decision"], 50, 7
        ),
        "evidence_based_medicine": _score_keywords(all_text, DIMENSION_KEYWORDS["evidence_based_medicine"], 45, 8),
    }
    total = round(sum(scores[key] * WEIGHTS[key] for key in CORE_ABILITIES), 1)
    strengths = _strengths(scores)
    weaknesses = _weaknesses(scores)
    return {
        **scores,
        "total_score": total,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "dimensions": _rule_dimensions(answers, all_text),
        "safety_flags": _safety_flags(all_text),
        "feedback": (
            f"本次总分 {total}。{strengths}；{weaknesses}。"
            "下一步建议围绕低分维度复盘诊断依据、鉴别排除和治疗证据。"
        ),
    }


def _rule_dimensions(answers: list[dict], all_text: str) -> dict:
    """Deterministic per-dimension evidence so the UI can always answer "why this score?"."""

    by_step = {item["step"]: item["answer_text"] for item in answers}
    sources = {
        "key_information": by_step.get("key_information", all_text),
        "differential_diagnosis": by_step.get("differential_diagnosis", all_text),
        "clinical_decision": by_step.get("treatment", all_text),
    }
    dimensions: dict[str, dict] = {}
    for key in CORE_ABILITIES:
        text = sources.get(key, all_text)
        keywords = DIMENSION_KEYWORDS[key]
        hits = [keyword for keyword in keywords if keyword.lower() in text.lower()]
        missing = [keyword for keyword in keywords if keyword not in hits]
        coverage = len(hits) / len(keywords) if keywords else 0
        dimensions[key] = {
            "score": None,
            "confidence": round(min(0.9, 0.35 + coverage * 0.5), 2),
            "evidence": [f"命中要点：{keyword}" for keyword in hits[:5]] or ["未识别到明确的能力要点表述"],
            "missing_points": [f"未提及：{keyword}" for keyword in missing[:4]],
            "feedback": _dimension_feedback(key, hits, missing),
            "source": "rule",
        }
    return dimensions


def _dimension_feedback(key: str, hits: list[str], missing: list[str]) -> str:
    label = ABILITY_LABELS.get(key, key)
    if not missing:
        return f"{label}要点覆盖完整，建议补充权重说明。"
    return f"{label}还需补充：{'、'.join(missing[:3])}。"


def _safety_flags(text: str) -> list[str]:
    lowered = text.lower()
    return [
        message
        for message, keywords in SAFETY_SIGNALS.items()
        if not any(keyword.lower() in lowered for keyword in keywords)
    ]


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
                case=prompt_json(case), rubric=prompt_json(rubric),
                answers=prompt_json(answers), rule_evidence=prompt_json(rule_score),
            ),
            fallback,
            task_type="case_evaluation",
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
        return _rule_fallback_result(rule_score)

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
        "evaluation_detail": {
            "mode": "ai",
            "dimensions": {
                key: {**evaluation.dimensions[key].model_dump(), "source": "ai"} for key in CORE_ABILITIES
            },
            "strengths": evaluation.strengths,
            "priority_gaps": evaluation.priority_gaps,
            "overall_feedback": evaluation.overall_feedback,
            "safety_flags": evaluation.safety_flags,
        },
        "safety_flags": evaluation.safety_flags,
    }


def _rule_fallback_result(rule_score: dict) -> dict:
    """Same contract as the AI path, but explicitly marked as degraded."""

    dimensions = {
        key: {**rule_score["dimensions"][key], "score": rule_score[key]} for key in CORE_ABILITIES
    }
    return {
        **{key: rule_score[key] for key in CORE_ABILITIES},
        "total_score": rule_score["total_score"],
        "strengths": rule_score["strengths"],
        "weaknesses": rule_score["weaknesses"],
        "feedback": rule_score["feedback"],
        "evaluation_mode": "rule_fallback",
        "degraded": True,
        "rule_score": rule_score["total_score"],
        "ai_score": None,
        "evaluation_detail": {
            "mode": "rule_fallback",
            "dimensions": dimensions,
            "strengths": [rule_score["strengths"]],
            "priority_gaps": [rule_score["weaknesses"]],
            "overall_feedback": rule_score["feedback"],
            "safety_flags": rule_score["safety_flags"],
        },
        "safety_flags": rule_score["safety_flags"],
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
