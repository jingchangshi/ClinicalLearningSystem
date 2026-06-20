from app.services.serializers import CORE_ABILITIES

PATHWAY_STAGES = [
    {
        "key": "stage_1_basic_recognition",
        "title": "基础疾病识别",
        "description": "识别风湿免疫疾病的核心症状、体征和实验室线索。",
    },
    {
        "key": "stage_2_differential_reasoning",
        "title": "复杂症状鉴别",
        "description": "围绕发热、皮疹、血细胞减少等症状群建立鉴别诊断。",
    },
    {
        "key": "stage_3_clinical_decision",
        "title": "治疗决策训练",
        "description": "结合器官受累和风险评估制定治疗与监测方案。",
    },
    {
        "key": "stage_4_evidence_based_learning",
        "title": "循证医学与文献训练",
        "description": "将指南、证据等级和研究结论纳入临床决策。",
    },
]


def determine_pathway_stage(profile: dict) -> str:
    if profile["medical_knowledge"] < 65 or profile["key_information"] < 65:
        return "stage_1_basic_recognition"
    if profile["differential_diagnosis"] < 70 or profile["evidence_integration"] < 70:
        return "stage_2_differential_reasoning"
    if profile["clinical_decision"] < 70:
        return "stage_3_clinical_decision"
    return "stage_4_evidence_based_learning"


def weakest_abilities(profile: dict, limit: int = 2) -> list[str]:
    return sorted(CORE_ABILITIES, key=lambda key: profile[key])[:limit]


def choose_recommendation(profile: dict, recent_scores: list[dict], cases: list[dict]) -> dict:
    stage = determine_pathway_stage(profile)
    latest = recent_scores[-1] if recent_scores else profile
    case = _pick_case(latest, cases)
    return {
        "case": case,
        "pathway_stage": stage,
        "reason": _recommendation_reason(latest, case),
    }


def _pick_case(scores: dict, cases: list[dict]) -> dict:
    title_preference = None
    if scores.get("differential_diagnosis", 100) < 60:
        title_preference = ["SLE与感染鉴别病例", "成人Still病病例"]
    elif scores.get("medical_knowledge", 100) < 60:
        title_preference = ["SLE基础病例"]
    elif scores.get("clinical_decision", 100) < 60:
        title_preference = ["ANCA相关血管炎病例"]
    elif scores.get("total_score", 0) > 85:
        title_preference = ["皮肌炎/抗合成酶综合征病例"]

    if title_preference:
        for title in title_preference:
            for case in cases:
                if title in case["title"]:
                    return case
    return cases[0]


def _recommendation_reason(scores: dict, case: dict) -> str:
    weakest = min(CORE_ABILITIES, key=lambda key: scores.get(key, 100))
    labels = {
        "medical_knowledge": "医学知识基础需要巩固",
        "key_information": "关键信息提取需要更系统",
        "differential_diagnosis": "鉴别诊断链条需要拓宽",
        "evidence_integration": "证据整合和反证处理需要强化",
        "clinical_decision": "治疗决策和监测计划需要训练",
        "evidence_based_medicine": "循证医学意识需要提升",
    }
    return f"{labels[weakest]}，推荐继续训练“{case['title']}”。"
