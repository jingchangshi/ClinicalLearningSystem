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
from app.llm.prompts.evaluation import (
    GUIDELINE_RATIONALE_SYSTEM_PROMPT,
    GUIDELINE_RATIONALE_USER_TEMPLATE,
    REASONING_QUESTION_SYSTEM_PROMPT,
    REASONING_QUESTION_USER_TEMPLATE,
    SP_FEEDBACK_SYSTEM_TEMPLATE,
)
from app.llm.prompts.insight import TEACHER_INSIGHT_SYSTEM_PROMPT, TEACHER_INSIGHT_USER_TEMPLATE
from app.llm.prompts.pathway import RECOMMENDATION_EXPLANATION_SYSTEM_PROMPT, RECOMMENDATION_EXPLANATION_USER_TEMPLATE


class DeepSeekClient:
    def __init__(self) -> None:
        self.base_url = LLM_BASE_URL
        self.api_key = LLM_API_KEY
        self.model = LLM_MODEL

    def chat(self, messages: list[dict], temperature: float = 0.3, response_format: dict | None = None):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "timeout": LLM_TIMEOUT_SECONDS,
        }
        if response_format:
            kwargs["response_format"] = response_format
        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=0,
        ).chat.completions.create(**kwargs)


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
            RECOMMENDATION_EXPLANATION_SYSTEM_PROMPT,
            RECOMMENDATION_EXPLANATION_USER_TEMPLATE.format(profile=profile, latest_scores=latest_scores, task=task),
            fallback,
        )

    def generate_sp_feedback(self, sp_case: dict, transcript: list[dict], diagnosis_summary: str, fallback: dict) -> dict:
        payload = self.chat_json(
            (
                SP_FEEDBACK_SYSTEM_TEMPLATE.format(sp_case_json=json.dumps(sp_case, ensure_ascii=False))
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
            GUIDELINE_RATIONALE_SYSTEM_PROMPT,
            GUIDELINE_RATIONALE_USER_TEMPLATE.format(
                title=guideline.get("title"),
                payload=payload,
                detail=scoring["detail"],
            ),
            fallback,
        )

    def generate_teacher_insight(self, weak_dimensions: list[dict], training_summary: dict, fallback: str) -> str:
        return self.chat_completion(
            TEACHER_INSIGHT_SYSTEM_PROMPT,
            TEACHER_INSIGHT_USER_TEMPLATE.format(weak_dimensions=weak_dimensions, training_summary=training_summary),
            fallback,
        )

    def _chat_text_once(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client().chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return content.strip() if content and content.strip() else ""

    def _chat_json_once(self, system_prompt: str, user_prompt: str, fallback: Any) -> Any:
        response = self._client().chat(
            [
                {
                    "role": "system",
                    "content": f"{system_prompt}\n必须只输出合法 JSON，不要输出 markdown 或解释。",
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content or "")
        return parsed if isinstance(parsed, (dict, list)) else fallback

    def _with_retries(self, operation, fallback: Any) -> Any:
        last_error: Exception | None = None
        for _ in range(max(1, LLM_MAX_RETRIES + 1)):
            try:
                result = operation()
                if result:
                    return result
                last_error = ValueError("LLM returned an empty response")
            except Exception as error:
                last_error = error
                continue
        if last_error:
            raise last_error
        return fallback

    def _client(self) -> DeepSeekClient:
        return DeepSeekClient()


llm_service = LLMService()


def chat_text(system_prompt: str, user_prompt: str, fallback: str) -> str:
    return llm_service.chat_completion(system_prompt, user_prompt, fallback)


def chat_json(system_prompt: str, user_prompt: str, fallback: Any) -> Any:
    return llm_service.chat_json(system_prompt, user_prompt, fallback)


def generate_reasoning_question(case: dict, step: str, student_answer: str) -> str:
    return llm_service.chat_completion(
        REASONING_QUESTION_SYSTEM_PROMPT,
        REASONING_QUESTION_USER_TEMPLATE.format(
            title=case.get("title"),
            standard_diagnosis=case.get("standard_diagnosis"),
            step=step,
            student_answer=student_answer,
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
