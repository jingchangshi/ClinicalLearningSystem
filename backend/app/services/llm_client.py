import os
import json
from typing import Any

from openai import OpenAI


def chat_text(system_prompt: str, user_prompt: str, fallback: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return fallback
    try:
        client = _client()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return content.strip() if content and content.strip() else fallback
    except Exception:
        return fallback


def chat_json(system_prompt: str, user_prompt: str, fallback: Any) -> Any:
    if not os.getenv("OPENAI_API_KEY"):
        return fallback
    try:
        client = _client()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": f"{system_prompt}\n必须只输出合法 JSON，不要输出 markdown 或解释。",
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        parsed = json.loads(content)
        if isinstance(parsed, (dict, list)):
            return parsed
    except Exception:
        return fallback
    return fallback


def generate_reasoning_question(case: dict, step: str, student_answer: str) -> str:
    if os.getenv("OPENAI_API_KEY"):
        return _openai_reasoning_question(case, step, student_answer)
    return _rule_reasoning_question(step, student_answer)


def score_student_answer(case: dict, answers: list[dict], rubric: dict) -> dict:
    from app.services.scoring_llm import score_with_rules

    return score_with_rules(case, answers, rubric)


def generate_learning_recommendation(
    profile: dict, recent_scores: list[dict], cases: list[dict]
) -> dict:
    from app.services.recommendation_service import choose_recommendation

    return choose_recommendation(profile, recent_scores, cases)


def _openai_reasoning_question(case: dict, step: str, student_answer: str) -> str:
    fallback = _rule_reasoning_question(step, student_answer)
    return chat_text(
        "你是风湿免疫临床教学导师，请提出一个能促进临床推理的追问。",
        (
            f"病例：{case.get('title')}\n标准诊断：{case.get('standard_diagnosis')}\n"
            f"当前步骤：{step}\n学生回答：{student_answer}"
        ),
        fallback,
    )


def _rule_reasoning_question(step: str, student_answer: str) -> str:
    text = student_answer.strip()
    if step == "key_information":
        if len(text) < 60:
            return "请进一步提取本病例中的关键阳性表现、关键阴性表现和异常检查结果。"
        return "这些关键信息中，哪些最能改变你的诊断排序？请说明权重。"
    if step == "initial_diagnosis":
        return "你为什么首先考虑这个诊断？请分别从症状、实验室检查和器官受累三个方面说明证据。"
    if step == "differential_diagnosis":
        keywords = ["感染", "AOSD", "Still", "HLH", "淋巴瘤"]
        if not any(keyword.lower() in text.lower() for keyword in keywords):
            return "你的鉴别诊断还不够完整。除当前诊断外，还需要考虑感染、成人Still病、HLH或血液系统疾病吗？请说明如何排除。"
        return "请按危险程度和可验证性排列你的鉴别诊断，并说明下一步排除策略。"
    if step == "examination":
        return "为了验证你的诊断和评估疾病活动度，还需要补充哪些检查？这些检查分别解决什么临床问题？"
    if step == "treatment":
        return "请说明治疗方案的依据、风险评估和需要监测的不良反应。"
    return "请补充你的临床推理依据，并说明哪些证据支持或反对当前判断。"


def normalize_openai_payload(value: Any) -> Any:
    return value


def _client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
