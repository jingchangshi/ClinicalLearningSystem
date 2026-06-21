import json
from typing import Any

from openai import OpenAI

from app.core.llm_config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
)


class LLMService:
    def chat_completion(self, system_prompt: str, user_prompt: str, fallback: str) -> str:
        if not LLM_API_KEY:
            return fallback
        return self._with_retries(lambda: self._chat_text_once(system_prompt, user_prompt), fallback)

    def chat_json(self, system_prompt: str, user_prompt: str, fallback: Any) -> Any:
        if not LLM_API_KEY:
            return fallback
        return self._with_retries(lambda: self._chat_json_once(system_prompt, user_prompt, fallback), fallback)

    def generate_case(self, system_prompt: str, user_prompt: str, fallback: dict) -> dict:
        payload = self.chat_json(system_prompt, user_prompt, fallback)
        return payload if isinstance(payload, dict) else fallback

    def explain_recommendation(self, profile: dict, latest_scores: dict, task: dict, fallback: str) -> str:
        return self.chat_completion(
            "你是医学教育研究者，请生成可用于教学研究报告的学习路径推荐解释。要求具体、克制、可验证。",
            (
                f"学生能力画像：{profile}\n"
                f"最近训练得分：{latest_scores}\n"
                f"推荐任务：{task}\n"
                "请用2-3句话说明为什么推荐、对应能力缺口、下一步学习策略。"
            ),
            fallback,
        )

    def generate_sp_feedback(self, sp_case: dict, transcript: list[dict], diagnosis_summary: str, fallback: dict) -> dict:
        payload = self.chat_json(
            (
                "你是临床医学 OSCE 标准化病人考核评分员。"
                "请根据 SP 病例、学生问诊对话和最后总结评分。"
                "必须只输出 JSON，字段包括 history_taking_score, communication_score, "
                "reasoning_score, humanistic_care_score, total_score, feedback。"
                "所有分数为0-100数字。\n"
                f"SP病例：{json.dumps(sp_case, ensure_ascii=False)}"
            ),
            json.dumps(
                {"transcript": transcript, "diagnosis_summary": diagnosis_summary},
                ensure_ascii=False,
            ),
            fallback,
        )
        return payload if isinstance(payload, dict) else fallback

    def generate_guideline_rationale(self, guideline: dict, payload: dict, scoring: dict, fallback: str) -> str:
        return self.chat_completion(
            "你是医学教育测评专家，请解释循证作答评分依据。",
            (
                f"指南：{guideline.get('title')}\n"
                f"学生作答：{payload}\n"
                f"评分细项：{scoring['detail']}\n"
                "请用2句话说明评分理由，避免夸大。"
            ),
            fallback,
        )

    def generate_teacher_insight(self, weak_dimensions: list[dict], training_summary: dict, fallback: str) -> str:
        return self.chat_completion(
            "你是医学教育质量改进顾问，请基于班级数据生成教师端教学洞察。",
            (
                f"班级短板：{weak_dimensions}\n"
                f"训练分布：{training_summary}\n"
                "请输出2句话，包含班级共性问题和下一步教学干预建议。"
            ),
            fallback,
        )

    def _chat_text_once(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            timeout=LLM_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
        return content.strip() if content and content.strip() else ""

    def _chat_json_once(self, system_prompt: str, user_prompt: str, fallback: Any) -> Any:
        response = self._client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": f"{system_prompt}\n必须只输出合法 JSON，不要输出 markdown 或解释。",
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            timeout=LLM_TIMEOUT_SECONDS,
        )
        parsed = json.loads(response.choices[0].message.content or "")
        return parsed if isinstance(parsed, (dict, list)) else fallback

    def _with_retries(self, operation, fallback: Any) -> Any:
        for _ in range(max(1, LLM_MAX_RETRIES + 1)):
            try:
                result = operation()
                if result:
                    return result
            except Exception:
                continue
        return fallback

    def _client(self) -> OpenAI:
        return OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=0,
        )


llm_service = LLMService()


def chat_text(system_prompt: str, user_prompt: str, fallback: str) -> str:
    return llm_service.chat_completion(system_prompt, user_prompt, fallback)


def chat_json(system_prompt: str, user_prompt: str, fallback: Any) -> Any:
    return llm_service.chat_json(system_prompt, user_prompt, fallback)


def generate_reasoning_question(case: dict, step: str, student_answer: str) -> str:
    return llm_service.chat_completion(
        "你是风湿免疫临床教学导师，请提出一个能促进临床推理的追问。",
        (
            f"病例：{case.get('title')}\n标准诊断：{case.get('standard_diagnosis')}\n"
            f"当前步骤：{step}\n学生回答：{student_answer}"
        ),
        _rule_reasoning_question(step, student_answer),
    )


def score_student_answer(case: dict, answers: list[dict], rubric: dict) -> dict:
    from app.services.scoring_llm import score_with_rules

    return score_with_rules(case, answers, rubric)


def generate_learning_recommendation(profile: dict, recent_scores: list[dict], cases: list[dict]) -> dict:
    from app.services.recommendation_service import choose_recommendation

    return choose_recommendation(profile, recent_scores, cases)


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
