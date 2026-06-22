import json
from typing import Any

from app.llm.prompts.evaluation import SP_PATIENT_SYSTEM_TEMPLATE
from app.services.llm_service import llm_service
from app.services.serializers import loads_json


def generate_patient_reply(sp_case: dict, transcript: list[dict], student_message: str) -> str:
    fallback = _rule_patient_reply(sp_case, student_message)
    system_prompt = _sp_system_prompt(sp_case)
    user_prompt = json.dumps(
        {"transcript": transcript, "student_message": student_message},
        ensure_ascii=False,
    )
    return llm_service.chat_completion(system_prompt, user_prompt, fallback)


def score_sp_session(sp_case: dict, transcript: list[dict], diagnosis_summary: str) -> dict:
    fallback = _rule_score_session(sp_case, transcript, diagnosis_summary)
    payload = llm_service.generate_sp_feedback(sp_case, transcript, diagnosis_summary, fallback)
    return _validated_score(payload, fallback)


def _sp_system_prompt(sp_case: dict) -> str:
    return SP_PATIENT_SYSTEM_TEMPLATE.format(sp_case_json=json.dumps(sp_case, ensure_ascii=False))


def _rule_patient_reply(sp_case: dict, student_message: str) -> str:
    hidden_history = sp_case.get("hidden_history", {})
    message = student_message.strip().lower()
    matched = _history_match(hidden_history, message)
    if matched:
        if _has_empathy(message):
            return f"谢谢医生，您这么说我放心一些。{matched}"
        return matched

    if _has_empathy(message):
        return "谢谢医生，您这么说我放心一些，我会尽量配合把情况讲清楚。"

    if _is_open_question(message):
        return _open_reply(hidden_history)

    if _is_closed_question(message):
        return "有一点，但不是一直都有，具体我也说不太准。"

    return "这个我不太确定，您可以再问得具体一点。"


def _rule_score_session(sp_case: dict, transcript: list[dict], diagnosis_summary: str) -> dict:
    student_messages = [item.get("message", "") for item in transcript if item.get("role") == "student"]
    combined_history = " ".join(student_messages)
    combined_all = f"{combined_history} {diagnosis_summary}"
    expected_tasks = sp_case.get("expected_tasks", [])

    history_taking_score = _history_score(sp_case.get("hidden_history", {}), combined_history, expected_tasks)
    communication_score = _communication_score(student_messages)
    reasoning_score = _reasoning_score(sp_case, diagnosis_summary)
    humanistic_care_score = _humanistic_score(combined_all)
    total_score = round(
        history_taking_score * 0.35
        + communication_score * 0.2
        + reasoning_score * 0.3
        + humanistic_care_score * 0.15,
        1,
    )
    return {
        "total_score": total_score,
        "communication_score": communication_score,
        "history_taking_score": history_taking_score,
        "reasoning_score": reasoning_score,
        "humanistic_care_score": humanistic_care_score,
        "feedback": _score_feedback(
            total_score,
            history_taking_score,
            communication_score,
            reasoning_score,
            humanistic_care_score,
        ),
    }


def _validated_score(payload: Any, fallback: dict) -> dict:
    if not isinstance(payload, dict):
        return fallback
    score_fields = [
        "history_taking_score",
        "communication_score",
        "reasoning_score",
        "humanistic_care_score",
        "total_score",
    ]
    normalized: dict[str, Any] = {}
    try:
        for field in score_fields:
            value = float(payload[field])
            normalized[field] = round(max(0.0, min(100.0, value)), 1)
    except (KeyError, TypeError, ValueError):
        return fallback
    feedback = str(payload.get("feedback") or "").strip()
    normalized["feedback"] = feedback or fallback["feedback"]
    return normalized


def _history_match(hidden_history: dict, message: str) -> str | None:
    keyword_map = {
        "duration": ["多久", "多长", "时间", "开始", "几天", "几周"],
        "fever": ["发热", "发烧", "体温", "寒战", "低热"],
        "pain": ["疼", "痛", "关节", "胸痛", "鼻"],
        "associated": ["伴随", "还有", "尿", "水肿", "脱发", "口腔", "溃疡", "乏力"],
    }
    for key, keywords in keyword_map.items():
        if any(keyword in message for keyword in keywords) and key in hidden_history:
            return str(hidden_history[key])
    return None


def _open_reply(hidden_history: dict) -> str:
    values = list(hidden_history.values())
    if not values:
        return "主要就是我刚才说的那些不舒服，最近让我有些担心。"
    return " ".join(str(value) for value in values[:3])


def _is_open_question(message: str) -> bool:
    return any(keyword in message for keyword in ["怎么", "哪些", "还有", "详细", "具体", "不舒服"])


def _is_closed_question(message: str) -> bool:
    return any(keyword in message for keyword in ["是否", "有没有", "是不是", "吗", "么"])


def _has_empathy(message: str) -> bool:
    return any(keyword in message for keyword in ["担心", "理解", "别紧张", "放心", "辛苦", "害怕"])


def _history_score(hidden_history: dict, combined_history: str, expected_tasks: list[str]) -> float:
    keys = ["duration", "fever", "pain", "associated"]
    hits = sum(1 for key in keys if _history_key_covered(key, hidden_history, combined_history))
    task_hits = sum(1 for task in expected_tasks if _task_covered(task, combined_history))
    return round(min(100.0, hits / len(keys) * 70 + task_hits / max(1, len(expected_tasks)) * 30), 1)


def _history_key_covered(key: str, hidden_history: dict, text: str) -> bool:
    if key not in hidden_history:
        return False
    keywords = {
        "duration": ["多久", "时间", "开始", "病程"],
        "fever": ["发热", "发烧", "体温", "寒战"],
        "pain": ["疼", "痛", "关节", "鼻", "胸"],
        "associated": ["伴随", "尿", "水肿", "脱发", "口腔", "乏力"],
    }
    return any(keyword in text for keyword in keywords[key])


def _task_covered(task: str, text: str) -> bool:
    return any(token in text for token in _tokens(task))


def _communication_score(messages: list[str]) -> float:
    if not messages:
        return 0.0
    question_count = sum(1 for message in messages if "？" in message or "?" in message or _is_closed_question(message))
    structure_hits = sum(1 for keyword in ["首先", "接下来", "总结", "确认", "检查"] if keyword in " ".join(messages))
    return round(min(100.0, question_count / 5 * 70 + structure_hits / 2 * 30), 1)


def _reasoning_score(sp_case: dict, diagnosis_summary: str) -> float:
    disease = str(sp_case.get("disease_category", ""))
    text = diagnosis_summary
    disease_score = 45 if disease and disease in text else 0
    differential_score = 20 if any(keyword in text for keyword in ["鉴别", "感染", "肿瘤", "活动", "肾炎"]) else 0
    plan_score = 25 if any(keyword in text for keyword in ["检查", "治疗", "处理", "监测", "住院"]) else 0
    risk_score = 10 if any(keyword in text for keyword in ["风险", "急", "严重", "告知"]) else 0
    return float(min(100, disease_score + differential_score + plan_score + risk_score))


def _humanistic_score(text: str) -> float:
    keywords = ["理解", "担心", "隐私", "同意", "解释", "放心", "配合", "辛苦"]
    hits = sum(1 for keyword in keywords if keyword in text)
    return round(min(100.0, hits / 3 * 100), 1)


def _score_feedback(
    total: float,
    history: float,
    communication: float,
    reasoning: float,
    humanistic: float,
) -> str:
    messages = []
    if total >= 85:
        messages.append("SP问诊表现稳定，能够兼顾信息收集、沟通和临床推理。")
    elif total >= 70:
        messages.append("SP问诊基本达标，但仍需补充关键病史或诊疗计划。")
    else:
        messages.append("SP问诊仍需按结构化流程练习，关键病史和初步判断不够完整。")
    if history < 80:
        messages.append("问诊完整性不足，建议覆盖病程、主要症状、伴随症状和危险信号。")
    if communication < 80:
        messages.append("沟通表达可更结构化，注意总结和确认患者回答。")
    if reasoning < 80:
        messages.append("诊断总结需包含首要诊断、鉴别诊断、检查和处理计划。")
    if humanistic < 80:
        messages.append("可增加共情、解释、隐私保护和共同决策表达。")
    return "".join(messages)


def _tokens(value: str) -> list[str]:
    for char in ["，", "。", "、", "；", "/", "和"]:
        value = value.replace(char, " ")
    return [token for token in value.split() if len(token) >= 2]


def load_sp_case_payload(raw_case: Any) -> dict:
    return {
        "id": raw_case.id,
        "title": raw_case.title,
        "disease_category": raw_case.disease_category,
        "difficulty": raw_case.difficulty,
        "patient_profile": loads_json(raw_case.patient_profile, {}),
        "opening_statement": raw_case.opening_statement,
        "hidden_history": loads_json(raw_case.hidden_history, {}),
        "emotional_style": raw_case.emotional_style,
        "expected_tasks": loads_json(raw_case.expected_tasks, []),
        "scoring_rubric": loads_json(raw_case.scoring_rubric, {}),
    }
