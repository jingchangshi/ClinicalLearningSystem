"""Task-aware AI execution policy.

One place decides how much model effort a task may spend. The transport stays
provider-aware (``llm_service.build_chat_kwargs`` still knows what DeepSeek
Thinking Mode looks like); this module describes the *task's* needs.

Why this exists: a single global ``thinking=enabled / effort=high /
max_tokens=8192 / timeout=60s`` is right for a case evaluation and wrong for a
two-sentence recommendation rationale. Applying the expensive configuration to
cheap tasks made every enrichment call as slow and as costly as a full
evaluation.

Each field is a *policy hypothesis*, not a measured fact; ``tools/ai_benchmark.py``
compares policies per task before a value is treated as final.

``reasoning_effort`` is only sent when ``thinking`` is on. DeepSeek ignores
``temperature`` while thinking, so a thinking task must not pretend to control
it (``temperature=None`` means "omit the field").
"""

from dataclasses import dataclass, replace

from app.core.llm_config import (
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS,
    LLM_REASONING_EFFORT,
    LLM_TIMEOUT_SECONDS,
)


@dataclass(frozen=True)
class AITaskPolicy:
    task_type: str
    thinking: bool
    max_tokens: int
    timeout_seconds: float
    max_retries: int
    reasoning_effort: str | None = None
    temperature: float | None = None

    def __post_init__(self) -> None:
        if self.thinking and self.reasoning_effort is None:
            raise ValueError(f"{self.task_type}: thinking tasks must declare reasoning_effort")
        if not self.thinking and self.reasoning_effort is not None:
            raise ValueError(f"{self.task_type}: reasoning_effort is meaningless with thinking disabled")
        if self.thinking and self.temperature is not None:
            raise ValueError(f"{self.task_type}: temperature is ignored while thinking is on")


def _policy(task_type: str, **overrides) -> AITaskPolicy:
    """Defaults come from the deployment's own LLM_* configuration."""

    base = {
        "task_type": task_type,
        "thinking": True,
        "reasoning_effort": LLM_REASONING_EFFORT,
        "max_tokens": LLM_MAX_TOKENS,
        "timeout_seconds": LLM_TIMEOUT_SECONDS,
        "max_retries": LLM_MAX_RETRIES,
        "temperature": None,
    }
    base.update(overrides)
    return AITaskPolicy(**base)


# Correctness-critical work keeps the full reasoning budget: a wrong formative
# evaluation is worse than a slow one.
CASE_EVALUATION = _policy("case_evaluation")
CASE_GENERATION = _policy("case_generation")

# Interactive, student-facing turns.
#
# Measured on the live provider (tools/ai_benchmark.py, 4 runs each, identical
# quality-gate results and comparable questions):
#
#   thinking=high, 8192 tokens    p50 2140 ms
#   thinking=low,   900 tokens    p50 4672 ms   <- a Thinking trace eats the
#                                                  budget before the answer starts
#   thinking=off,   600 tokens    p50  963 ms
#
# A one-sentence Socratic question does not need a reasoning trace, and 963 ms
# instead of 4.7 s is the difference between a tutoring turn and a stall.
TUTOR_QUESTION = _policy(
    "tutor_question", thinking=False, reasoning_effort=None, temperature=0.3,
    max_tokens=600, timeout_seconds=25,
)
# Measured the same way as the tutor: thinking+900 ms p50 3252 ms, thinking off
# p50 1218 ms, identical quality gates. A simulated patient answers in one or two
# sentences; it does not need a reasoning trace either.
SP_PATIENT = _policy(
    "sp_patient", thinking=False, reasoning_effort=None, temperature=0.3,
    max_tokens=600, timeout_seconds=25,
)

# Structured summaries and short rationales: no chain of thought is needed to
# restate evidence that the deterministic layer already computed.
SP_EVALUATION = _policy(
    "sp_evaluation", thinking=False, reasoning_effort=None, temperature=0.2,
    max_tokens=2600, timeout_seconds=40,
)
GUIDELINE_RATIONALE = _policy(
    "guideline_rationale", thinking=False, reasoning_effort=None, temperature=0.3,
    max_tokens=1200, timeout_seconds=30,
)
SKILL_FEEDBACK = _policy(
    "skill_feedback", thinking=False, reasoning_effort=None, temperature=0.3,
    max_tokens=700, timeout_seconds=25,
)
RECOMMENDATION_EXPLANATION = _policy(
    "recommendation_explanation", thinking=False, reasoning_effort=None, temperature=0.3,
    max_tokens=900, timeout_seconds=25,
)
TEACHER_INSIGHT = _policy(
    "teacher_insight", thinking=False, reasoning_effort=None, temperature=0.3,
    max_tokens=600, timeout_seconds=25,
)
AI_PROBE = _policy(
    "ai_probe", thinking=False, reasoning_effort=None, temperature=0.0,
    max_tokens=16, timeout_seconds=15, max_retries=0,
)

AI_TASK_POLICIES: dict[str, AITaskPolicy] = {
    policy.task_type: policy
    for policy in (
        CASE_EVALUATION,
        CASE_GENERATION,
        TUTOR_QUESTION,
        SP_PATIENT,
        SP_EVALUATION,
        GUIDELINE_RATIONALE,
        SKILL_FEEDBACK,
        RECOMMENDATION_EXPLANATION,
        TEACHER_INSIGHT,
        AI_PROBE,
    )
}


def policy_for(task_type: str) -> AITaskPolicy | None:
    """``None`` means "use the deployment-wide LLM_* configuration"."""

    return AI_TASK_POLICIES.get(task_type)


def with_overrides(task_type: str, **overrides) -> AITaskPolicy:
    """Used by the benchmark harness to compare policies for one task."""

    policy = policy_for(task_type)
    if policy is None:
        raise KeyError(f"unknown AI task: {task_type}")
    return replace(policy, **overrides)


def policy_summary() -> list[dict]:
    """Non-secret view for diagnostics and the readiness report."""

    return [
        {
            "task_type": policy.task_type,
            "thinking": policy.thinking,
            "reasoning_effort": policy.reasoning_effort,
            "max_tokens": policy.max_tokens,
            "timeout_seconds": policy.timeout_seconds,
            "max_retries": policy.max_retries,
        }
        for policy in AI_TASK_POLICIES.values()
    ]
