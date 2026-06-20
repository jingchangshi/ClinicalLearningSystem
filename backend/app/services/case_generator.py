import json
from typing import Any

from app.services.llm_client import chat_json

REQUIRED_CASE_FIELDS = [
    "title",
    "disease_category",
    "difficulty",
    "learning_objectives",
    "chief_complaint",
    "history",
    "physical_exam",
    "lab_results",
    "imaging",
    "standard_diagnosis",
    "differential_diagnosis",
    "treatment_plan",
    "rubric",
]

CASE_GENERATION_SYSTEM_PROMPT = """
你是风湿免疫科临床教学病例设计专家。
请生成适合临床医学本科生训练的结构化病例。
病例必须医学合理，避免真实个人身份信息，适合分步临床推理训练。
JSON 字段必须包括 title, disease_category, difficulty, learning_objectives,
chief_complaint, history, physical_exam, lab_results, imaging, standard_diagnosis,
differential_diagnosis, treatment_plan, rubric。
rubric 必须覆盖 medical_knowledge, key_information, differential_diagnosis,
evidence_integration, clinical_decision, evidence_based_medicine。
"""


def generate_case_payload(prompt: dict) -> dict:
    fallback = fallback_rule_case(prompt)
    payload = chat_json(CASE_GENERATION_SYSTEM_PROMPT, _case_user_prompt(prompt), fallback)
    try:
        return validate_case_payload(payload)
    except ValueError:
        return fallback


def validate_case_payload(payload: dict) -> dict:
    missing = [field for field in REQUIRED_CASE_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Missing required case fields: {', '.join(missing)}")

    normalized = dict(payload)
    normalized["learning_objectives"] = _as_string_list(normalized["learning_objectives"])
    normalized["differential_diagnosis"] = _as_string_list(normalized["differential_diagnosis"])
    normalized["rubric"] = _as_rubric(normalized["rubric"])
    if not normalized["learning_objectives"]:
        raise ValueError("Case field cannot be empty: learning_objectives")
    if not normalized["differential_diagnosis"]:
        raise ValueError("Case field cannot be empty: differential_diagnosis")
    if not normalized["rubric"]:
        raise ValueError("Case field cannot be empty: rubric")
    for field in REQUIRED_CASE_FIELDS:
        if field in {"learning_objectives", "differential_diagnosis", "rubric"}:
            continue
        if not str(normalized[field]).strip():
            raise ValueError(f"Case field cannot be empty: {field}")
    return normalized


def fallback_rule_case(prompt: dict) -> dict:
    disease = str(prompt.get("disease_category") or "风湿免疫疾病")
    difficulty = str(prompt.get("difficulty") or "中等")
    teaching_goal = str(prompt.get("teaching_goal") or "训练临床推理和治疗决策")
    required_elements = _as_string_list(prompt.get("required_elements") or [])
    target_abilities = _as_string_list(prompt.get("target_abilities") or [])
    elements_text = "、".join(required_elements) if required_elements else "发热、皮疹、关节痛和实验室异常"
    ability_text = "、".join(target_abilities) if target_abilities else "关键信息提取、鉴别诊断、临床决策"

    payload = {
        "title": f"{disease}{difficulty}生成病例",
        "disease_category": disease,
        "difficulty": difficulty,
        "learning_objectives": [
            teaching_goal,
            f"围绕{ability_text}完成结构化推理",
            "制定检查、诊断和治疗监测计划",
        ],
        "chief_complaint": f"患者因{elements_text}就诊，要求学生完成系统评估。",
        "history": (
            f"患者近1个月出现{elements_text}。症状逐渐加重，伴乏力和活动耐量下降。"
            "既往无明确自身免疫病史，近期未规律接受相关治疗。"
        ),
        "physical_exam": "生命体征平稳，可见相关皮肤或关节阳性体征，心肺腹查体需结合病情进一步描述。",
        "lab_results": "血常规、炎症指标、自身抗体、补体、尿常规和肝肾功能存在提示性异常。",
        "imaging": "根据病情选择胸部CT、关节超声或腹部/肾脏超声，未见立即危及生命的影像表现。",
        "standard_diagnosis": f"{disease}，需结合活动度和器官受累进一步分层。",
        "differential_diagnosis": ["感染性疾病", "肿瘤或血液系统疾病", "其他结缔组织病", "药物或过敏反应"],
        "treatment_plan": "完善关键检查后进行风险分层，必要时给予对症治疗、免疫治疗或专科会诊，并监测感染和药物不良反应。",
        "rubric": {
            "medical_knowledge": "能识别疾病核心表现和诊断依据。",
            "key_information": "能提取关键阳性、关键阴性和危险信号。",
            "differential_diagnosis": "能覆盖感染、肿瘤和其他自身免疫病鉴别。",
            "evidence_integration": "能解释支持证据、反对证据和证据权重。",
            "clinical_decision": "能制定检查、治疗、监测和随访计划。",
            "evidence_based_medicine": "能结合指南推荐或证据等级说明方案。",
        },
    }
    return validate_case_payload(payload)


def _case_user_prompt(prompt: dict) -> str:
    return json.dumps(
        {
            "生成要求": prompt,
            "必须字段": REQUIRED_CASE_FIELDS,
            "rubric能力维度": [
                "medical_knowledge",
                "key_information",
                "differential_diagnosis",
                "evidence_integration",
                "clinical_decision",
                "evidence_based_medicine",
            ],
        },
        ensure_ascii=False,
    )


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", "\n").replace("、", "\n").splitlines() if item.strip()]
    return []


def _as_rubric(value: Any) -> dict:
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return {str(key): str(item) for key, item in parsed.items()}
        except json.JSONDecodeError:
            return {"raw": value}
    return {}
