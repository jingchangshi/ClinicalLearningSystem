"""The task-aware policy layer: one place decides how much a task may spend."""

from pathlib import Path

import pytest

from app.core import ai_audit
from app.core.ai_policy import (
    AI_TASK_POLICIES,
    CASE_EVALUATION,
    RECOMMENDATION_EXPLANATION,
    TEACHER_INSIGHT,
    AITaskPolicy,
    policy_summary,
    with_overrides,
)
from app.core.llm_config import LLM_MAX_TOKENS, LLM_REASONING_EFFORT
from app.services.llm_service import build_chat_kwargs

APP_ROOT = Path(__file__).resolve().parent.parent / "app"


def test_every_audited_capability_has_a_policy():
    """A missing policy would silently fall back to the deployment-wide budget."""

    assert set(ai_audit.PROMPT_VERSIONS) == set(AI_TASK_POLICIES)


def test_policy_table_is_self_consistent():
    for policy in AI_TASK_POLICIES.values():
        assert isinstance(policy, AITaskPolicy)
        assert policy.max_tokens >= 16
        assert policy.timeout_seconds > 0
        assert policy.max_retries >= 0


def test_thinking_and_temperature_cannot_contradict_each_other():
    with pytest.raises(ValueError):
        AITaskPolicy(task_type="x", thinking=True, max_tokens=10, timeout_seconds=1, max_retries=0)
    with pytest.raises(ValueError):
        AITaskPolicy(
            task_type="x", thinking=False, reasoning_effort="high", max_tokens=10, timeout_seconds=1, max_retries=0
        )
    with pytest.raises(ValueError):
        AITaskPolicy(
            task_type="x", thinking=True, reasoning_effort="high", temperature=0.3,
            max_tokens=10, timeout_seconds=1, max_retries=0,
        )


def test_correctness_critical_evaluation_keeps_the_full_reasoning_envelope():
    assert CASE_EVALUATION.thinking is True
    assert CASE_EVALUATION.max_tokens == LLM_MAX_TOKENS
    assert CASE_EVALUATION.reasoning_effort == LLM_REASONING_EFFORT
    assert CASE_EVALUATION.temperature is None


@pytest.mark.parametrize("policy", [RECOMMENDATION_EXPLANATION, TEACHER_INSIGHT])
def test_cheap_tasks_do_not_run_the_expensive_configuration(policy):
    """Optimising latency must not mean quietly spending the evaluation budget."""

    assert policy.thinking is False
    assert policy.max_tokens < LLM_MAX_TOKENS / 4
    assert policy.max_tokens <= 900


@pytest.mark.parametrize("task_type", ["tutor_question", "sp_patient"])
def test_short_interactive_turns_do_not_pay_for_a_reasoning_trace(task_type):
    """Measured on the live provider: thinking mode made a 1-2 sentence answer
    ~3-5x slower with identical quality gates (tools/ai_benchmark.py)."""

    assert AI_TASK_POLICIES[task_type].thinking is False


def test_policy_reaches_the_outgoing_request(monkeypatch):
    from app.services import llm_service as llm_module

    monkeypatch.setattr(llm_module, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(llm_module, "LLM_MODEL", "deepseek-flash")

    thinking = build_chat_kwargs([{"role": "user", "content": "hi"}], policy=CASE_EVALUATION)
    assert thinking["extra_body"] == {"thinking": {"type": "enabled"}}
    assert thinking["reasoning_effort"] == CASE_EVALUATION.reasoning_effort
    assert thinking["max_tokens"] == CASE_EVALUATION.max_tokens
    assert thinking["timeout"] == CASE_EVALUATION.timeout_seconds
    assert "temperature" not in thinking

    cheap = build_chat_kwargs([{"role": "user", "content": "hi"}], policy=TEACHER_INSIGHT)
    assert cheap["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in cheap
    assert cheap["max_tokens"] == TEACHER_INSIGHT.max_tokens
    assert cheap["temperature"] == TEACHER_INSIGHT.temperature


def test_policy_overrides_are_how_the_benchmark_compares_options():
    variant = with_overrides(
        "tutor_question", thinking=True, reasoning_effort="low", temperature=None, max_tokens=200
    )
    assert variant.thinking is True
    assert variant.max_tokens == 200
    assert AI_TASK_POLICIES["tutor_question"] != variant, "the default table stays immutable"


def test_only_the_transport_module_touches_the_raw_provider_payload():
    """Routes and services describe task needs; they never build wire payloads."""

    raw_payload_offenders = []
    client_offenders = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if path.name == "llm_service.py":
            continue
        source = path.read_text()
        if "extra_body" in source:
            raw_payload_offenders.append(str(path.relative_to(APP_ROOT)))
        if path.parent.name == "routes" and ("build_chat_kwargs" in source or "from openai" in source):
            client_offenders.append(str(path.relative_to(APP_ROOT)))
    assert raw_payload_offenders == []
    assert client_offenders == []


def test_policy_summary_is_serialisable_and_secret_free():
    summary = policy_summary()
    assert {row["task_type"] for row in summary} == set(AI_TASK_POLICIES)
    for row in summary:
        assert "key" not in row and "api_key" not in row
