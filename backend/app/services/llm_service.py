import json
import logging
import time
from typing import Any

from openai import OpenAI

from app.core import ai_audit
from app.core.ai_runtime import ai_runtime
from app.core.deidentify import deidentify, deidentify_text
from app.core.llm_config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MODEL,
    LLM_PROVIDER,
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

logger = logging.getLogger("clinpath.llm")


def prompt_json(payload: Any) -> str:
    """Serialise a prompt payload for the provider.

    Two guarantees in one choke point: it never fails on a datetime or Decimal,
    and identifier-shaped content is redacted before the payload leaves the box.
    """

    return json.dumps(deidentify(payload), ensure_ascii=False, default=str)


class OpenAICompatibleClient:
    def __init__(self) -> None:
        self.base_url = LLM_BASE_URL
        self.api_key = LLM_API_KEY
        self.model = LLM_MODEL

    def chat(self, messages: list[dict], temperature: float = 0.3, response_format: dict | None = None):
        kwargs = {
            "model": self.model,
            "messages": _sanitised(messages),
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


def _sanitised(messages: list[dict]) -> list[dict]:
    """Last mile before the provider: no identifier-shaped content leaves here,
    whatever path assembled the prompt."""

    return [
        {**message, "content": deidentify_text(str(message.get("content", "")))}
        for message in messages
    ]


class LLMService:
    def chat_completion(self, system_prompt: str, user_prompt: str, fallback: str) -> str:
        if not LLM_API_KEY:
            ai_runtime.record_call("rule_fallback", "NotConfigured")
            ai_audit.report_call(success=False, fallback_used=True, latency_ms=0, error_type="NotConfigured")
            return fallback
        return self._with_retries(lambda: self._chat_text_once(system_prompt, user_prompt), fallback, "text")

    def chat_json(self, system_prompt: str, user_prompt: str, fallback: Any) -> Any:
        if not LLM_API_KEY:
            ai_runtime.record_call("rule_fallback", "NotConfigured")
            ai_audit.report_call(success=False, fallback_used=True, latency_ms=0, error_type="NotConfigured")
            return fallback
        return self._with_retries(lambda: self._chat_json_once(system_prompt, user_prompt, fallback), fallback, "json")

    def generate_case(self, system_prompt: str, user_prompt: str, fallback: dict) -> dict:
        payload = self.chat_json(system_prompt, user_prompt, fallback)
        return payload if isinstance(payload, dict) else fallback

    def explain_recommendation(self, profile: dict, latest_scores: dict, task: dict, fallback: str) -> str:
        return self.chat_completion(
            RECOMMENDATION_EXPLANATION_SYSTEM_PROMPT,
            RECOMMENDATION_EXPLANATION_USER_TEMPLATE.format(profile=profile, latest_scores=latest_scores, task=task),
            fallback,
        )

    def explain_recommendation_batch(self, profile: dict, recent_evidence: dict, tasks: list[dict]) -> dict[str, str]:
        fallback: dict[str, str] = {}
        payload = self.chat_json(
            (
                "你是临床学习路径导师。只输出 JSON："
                "{\"explanations\":{\"task_key\":\"简洁、基于能力画像的训练理由\"}}。"
                "不得预测未经验证的学习增益。"
            ),
            prompt_json({"profile": profile, "recent_evidence": recent_evidence, "tasks": tasks}),
            fallback,
        )
        explanations = payload.get("explanations") if isinstance(payload, dict) else None
        if not isinstance(explanations, dict):
            return fallback
        return {str(key): value for key, value in explanations.items() if isinstance(value, str) and value.strip()}

    def generate_sp_feedback(self, sp_case: dict, transcript: list[dict], diagnosis_summary: str, fallback: dict) -> dict:
        payload = self.chat_json(
            (
                SP_FEEDBACK_SYSTEM_TEMPLATE.format(sp_case_json=prompt_json(sp_case))
            ),
            prompt_json({"transcript": transcript, "diagnosis_summary": diagnosis_summary}),
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

    def _with_retries(self, operation, fallback: Any, operation_name: str = "chat") -> Any:
        last_error: Exception | None = None
        started = time.monotonic()
        for attempt in range(max(1, LLM_MAX_RETRIES + 1)):
            attempt_started = time.monotonic()
            try:
                result = operation()
                if result:
                    ai_runtime.record_call("ai")
                    ai_audit.report_call(
                        success=True,
                        fallback_used=False,
                        latency_ms=round((time.monotonic() - attempt_started) * 1000),
                    )
                    return result
                last_error = ValueError("LLM returned an empty response")
                ai_audit.report_call(
                    success=False,
                    fallback_used=False,
                    latency_ms=round((time.monotonic() - attempt_started) * 1000),
                    error_type="EmptyResponse",
                )
            except Exception as error:
                last_error = error
                ai_audit.report_call(
                    success=False,
                    fallback_used=False,
                    latency_ms=round((time.monotonic() - attempt_started) * 1000),
                    error_type=type(error).__name__,
                )
                logger.warning(
                    "LLM degraded provider=%s model=%s operation=%s failure_type=%s retry=%s latency_ms=%s",
                    LLM_PROVIDER, LLM_MODEL, operation_name, type(error).__name__, attempt,
                    round((time.monotonic() - started) * 1000),
                )
                continue
        if last_error:
            logger.warning("LLM fallback used operation=%s", operation_name)
            ai_runtime.record_call("rule_fallback", type(last_error).__name__)
            ai_audit.report_call(
                success=False,
                fallback_used=True,
                latency_ms=0,
                error_type=type(last_error).__name__,
            )
        return fallback

    def probe(self) -> dict:
        """One real, minimal request. Never returns or logs provider output."""

        if not LLM_API_KEY:
            ai_runtime.record_probe(False, None, "NotConfigured")
            return {"reachable": False, "latency_ms": None, "error_type": "NotConfigured"}
        started = time.monotonic()
        try:
            self._client().chat([{"role": "user", "content": "Reply: ok"}], temperature=0)
            latency_ms = round((time.monotonic() - started) * 1000)
            ai_runtime.record_probe(True, latency_ms, None)
            return {"reachable": True, "latency_ms": latency_ms, "error_type": None}
        except Exception as error:
            latency_ms = round((time.monotonic() - started) * 1000)
            ai_runtime.record_probe(False, latency_ms, type(error).__name__)
            return {"reachable": False, "latency_ms": latency_ms, "error_type": type(error).__name__}

    def _client(self) -> OpenAICompatibleClient:
        return OpenAICompatibleClient()


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
            case_context=prompt_json(case),
            step=step,
            student_answer=student_answer,
        ),
        _rule_reasoning_question(step, student_answer),
    )


def score_student_answer(case: dict, answers: list[dict], rubric: dict) -> dict:
    from app.services.scoring_llm import evaluate_case_submission

    return evaluate_case_submission(case, answers, rubric, llm_service)


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
