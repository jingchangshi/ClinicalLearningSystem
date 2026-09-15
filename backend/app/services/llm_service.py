import json
import logging
import time
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from app.core import ai_audit
from app.core.ai_runtime import ai_runtime
from app.core.deidentify import deidentify, deidentify_text
from app.core.llm_config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_REASONING_EFFORT,
    LLM_TIMEOUT_SECONDS,
    thinking_mode_active,
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

# A tiny, deterministic, non-thinking request: the probe answers "is the
# provider reachable?", never "how well does it reason?".
PROBE_PROMPT = "Reply exactly: ok"
PROBE_MAX_TOKENS = 16

# Transient provider failures worth another attempt. Everything else (bad
# request, bad key, empty balance, invalid parameters) is permanent: retrying it
# only delays the honest degraded result.
RETRYABLE_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504})
RETRY_BACKOFF_SECONDS = 0.5
RETRY_BACKOFF_CAP_SECONDS = 4.0


def classify_provider_error(error: BaseException) -> tuple[str, bool]:
    """Return ``(error_type, retryable)`` using the official error semantics.

    400/401/402/422 are permanent; 429/5xx and network problems are transient.
    Content-level failures (empty body, unparseable JSON) are reported as their
    own type and are worth one retry before the rule fallback takes over.
    """

    if isinstance(error, APITimeoutError):
        return "Timeout", True
    if isinstance(error, APIConnectionError):
        return "ConnectionError", True
    status = getattr(error, "status_code", None)
    if isinstance(status, int):
        return f"HTTP{status}", status in RETRYABLE_STATUS_CODES
    if isinstance(error, (json.JSONDecodeError, ValueError)):
        return "EmptyResponse", True
    if isinstance(error, APIStatusError):  # pragma: no cover - status_code is set in practice
        return type(error).__name__, False
    return type(error).__name__, True


def build_chat_kwargs(
    messages: list[dict],
    temperature: float = 0.3,
    response_format: dict | None = None,
    thinking: bool | None = None,
    max_tokens: int | None = None,
) -> dict:
    """Assemble provider request kwargs. The one place Thinking Mode is decided.

    - Thinking Mode (DeepSeek) is requested explicitly instead of relying on the
      provider default, and carries ``reasoning_effort``.
    - ``temperature`` is omitted while thinking is on: the provider ignores it,
      so sending it would only imply control the caller does not have.
    - ``max_tokens`` is always sent, so a JSON answer cannot be silently
      truncated by a provider-side default.
    """

    deepseek = LLM_PROVIDER == "deepseek"
    wants_thinking = thinking_mode_active(LLM_PROVIDER) if thinking is None else (deepseek and thinking)
    kwargs: dict = {
        "model": LLM_MODEL,
        "messages": _sanitised(messages),
        "timeout": LLM_TIMEOUT_SECONDS,
        "max_tokens": max_tokens if max_tokens is not None else LLM_MAX_TOKENS,
    }
    if deepseek:
        kwargs["extra_body"] = {"thinking": {"type": "enabled" if wants_thinking else "disabled"}}
    if wants_thinking:
        kwargs["reasoning_effort"] = LLM_REASONING_EFFORT
    else:
        kwargs["temperature"] = temperature
    if response_format:
        kwargs["response_format"] = response_format
    return kwargs


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

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        response_format: dict | None = None,
        thinking: bool | None = None,
        max_tokens: int | None = None,
    ):
        kwargs = build_chat_kwargs(
            messages,
            temperature=temperature,
            response_format=response_format,
            thinking=thinking,
            max_tokens=max_tokens,
        )
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
                    # The JSON Output contract requires the prompt to mention JSON
                    # and to show the expected shape, not just to ask for "no
                    # markdown". Truncated or empty output is a provider failure.
                    "content": (
                        f"{system_prompt}\n必须只输出一个合法 JSON object，不要输出 markdown 或解释。"
                        "如果无法完成，返回空对象而不是解释文字。"
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            # DeepSeek documents that JSON Output can occasionally return empty
            # content; that is a provider failure, never a valid evaluation.
            raise ValueError("LLM returned empty JSON content")
        parsed = json.loads(content)
        return parsed if isinstance(parsed, (dict, list)) else fallback

    def _with_retries(self, operation, fallback: Any, operation_name: str = "chat") -> Any:
        last_error: Exception | None = None
        last_error_type: str | None = None
        started = time.monotonic()
        max_attempts = max(1, LLM_MAX_RETRIES + 1)
        for attempt in range(max_attempts):
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
                last_error_type, retryable = "EmptyResponse", True
            except Exception as error:
                last_error = error
                last_error_type, retryable = classify_provider_error(error)
            ai_audit.report_call(
                success=False,
                fallback_used=False,
                latency_ms=round((time.monotonic() - attempt_started) * 1000),
                error_type=last_error_type,
            )
            logger.warning(
                "LLM degraded provider=%s model=%s operation=%s failure_type=%s attempt=%s retryable=%s latency_ms=%s",
                LLM_PROVIDER, LLM_MODEL, operation_name, last_error_type, attempt, retryable,
                round((time.monotonic() - started) * 1000),
            )
            if not retryable:
                logger.warning("LLM permanent failure, not retrying operation=%s", operation_name)
                break
            if attempt < max_attempts - 1:
                time.sleep(min(RETRY_BACKOFF_SECONDS * (2**attempt), RETRY_BACKOFF_CAP_SECONDS))
        if last_error:
            logger.warning("LLM fallback used operation=%s", operation_name)
            ai_runtime.record_call("rule_fallback", last_error_type)
            ai_audit.report_call(
                success=False,
                fallback_used=True,
                latency_ms=0,
                error_type=last_error_type,
            )
        return fallback

    def probe(self) -> dict:
        """One real, minimal, non-thinking request. Never returns provider output."""

        if not LLM_API_KEY:
            ai_runtime.record_probe(False, None, "NotConfigured")
            return {"reachable": False, "latency_ms": None, "error_type": "NotConfigured"}
        started = time.monotonic()
        try:
            self._client().chat(
                [{"role": "user", "content": PROBE_PROMPT}],
                temperature=0,
                thinking=False,
                max_tokens=PROBE_MAX_TOKENS,
            )
            latency_ms = round((time.monotonic() - started) * 1000)
            ai_runtime.record_probe(True, latency_ms, None)
            return {"reachable": True, "latency_ms": latency_ms, "error_type": None}
        except Exception as error:
            latency_ms = round((time.monotonic() - started) * 1000)
            error_type, _ = classify_provider_error(error)
            ai_runtime.record_probe(False, latency_ms, error_type)
            return {"reachable": False, "latency_ms": latency_ms, "error_type": error_type}

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
