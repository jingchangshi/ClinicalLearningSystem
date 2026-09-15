"""The DeepSeek request contract, pinned without spending any API quota.

Every assertion here mirrors a statement in the official documentation
(https://api-docs.deepseek.com): the model name, the Thinking Mode toggle, the
effort control, the temperature behaviour, JSON Output, and the error semantics
that decide whether an attempt is worth retrying.
"""

import importlib
import json
from types import SimpleNamespace

import pytest

from app.core import ai_audit, llm_config
from app.models import AIInvocation
from app.services import llm_service as llm_module
from app.services.llm_service import (
    PROBE_MAX_TOKENS,
    LLMService,
    build_chat_kwargs,
    classify_provider_error,
)


def _reload_config():
    return importlib.reload(importlib.import_module("app.core.llm_config"))


@pytest.fixture
def configure(monkeypatch):
    """Point both the config module and the transport module at test values."""

    def apply(**values):
        for name, value in values.items():
            monkeypatch.setattr(llm_config, name, value)
            if hasattr(llm_module, name):
                monkeypatch.setattr(llm_module, name, value)

    return apply


class _FakeStatusError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


@pytest.fixture
def sdk(monkeypatch):
    """Replace only ``OpenAI(...).chat.completions.create`` and record kwargs.

    The real client and the real kwarg builder stay in the path, so these tests
    describe the request ClinPath would actually send.
    """

    def install(message: SimpleNamespace) -> list[dict]:
        calls: list[dict] = []

        class _Completions:
            def create(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        class _Chat:
            completions = _Completions()

        class _FakeOpenAI:
            def __init__(self, *_args, **_kwargs):
                self.chat = _Chat()

        monkeypatch.setattr(llm_module, "OpenAI", _FakeOpenAI)
        return calls

    return install


# --- current official defaults -------------------------------------------------


@pytest.mark.parametrize("variable", ["LLM_MODEL", "DEEPSEEK_MODEL", "LLM_BASE_URL", "DEEPSEEK_BASE_URL"])
def test_deepseek_defaults_match_the_current_official_contract(monkeypatch, variable):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-style-key")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    for name in ("LLM_MODEL", "DEEPSEEK_MODEL", "LLM_BASE_URL", "DEEPSEEK_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    config = _reload_config()
    try:
        assert config.LLM_MODEL == "deepseek-flash"
        assert config.LLM_MODEL_SOURCE == "default:deepseek"
        assert config.LLM_BASE_URL == "https://api.deepseek.com"
        assert config.LLM_BASE_URL_SOURCE == "default:deepseek"
        # The retired production defaults must not be able to come back silently.
        assert config.DEFAULT_MODELS["deepseek"] not in {"deepseek-chat", "deepseek-reasoner"}
    finally:
        importlib.reload(config)


def test_canonical_key_wins_but_the_legacy_deepseek_alias_still_works(monkeypatch):
    for name in ("LLM_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    config = _reload_config()
    try:
        assert config.LLM_API_KEY == "legacy-key"
        assert config.LLM_API_KEY_SOURCE == "DEEPSEEK_API_KEY"
        assert config.LLM_PROVIDER == "deepseek"
    finally:
        importlib.reload(config)

    monkeypatch.setenv("LLM_API_KEY", "canonical-key")
    config = _reload_config()
    try:
        assert config.LLM_API_KEY == "canonical-key"
        assert config.LLM_API_KEY_SOURCE == "LLM_API_KEY"
    finally:
        importlib.reload(config)


def test_thinking_mode_is_configured_explicitly_and_survives_a_typo(monkeypatch):
    monkeypatch.setenv("LLM_THINKING_ENABLED", "true")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "xhigh")
    config = _reload_config()
    try:
        assert config.LLM_THINKING_ENABLED is True
        # Documented compatibility spelling, mapped onto the real range.
        assert config.LLM_REASONING_EFFORT == "high"
    finally:
        importlib.reload(config)

    monkeypatch.setenv("LLM_REASONING_EFFORT", "very-high-please")
    config = _reload_config()
    try:
        assert config.LLM_REASONING_EFFORT == config.DEFAULT_REASONING_EFFORT
        assert "invalid" in config.LLM_REASONING_EFFORT_SOURCE
    finally:
        importlib.reload(config)


# --- outgoing request kwargs ---------------------------------------------------


def test_thinking_request_sends_effort_and_omits_temperature(configure):
    configure(
        LLM_PROVIDER="deepseek",
        LLM_MODEL="deepseek-flash",
        LLM_THINKING_ENABLED=True,
        LLM_REASONING_EFFORT="high",
        LLM_MAX_TOKENS=4096,
    )

    kwargs = build_chat_kwargs([{"role": "user", "content": "你好"}], temperature=0.3)

    assert kwargs["model"] == "deepseek-flash"
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}
    assert kwargs["reasoning_effort"] == "high"
    assert kwargs["max_tokens"] == 4096
    # Thinking Mode ignores temperature; sending it would imply control we lack.
    assert "temperature" not in kwargs


def test_non_thinking_request_keeps_temperature_and_disables_thinking(configure):
    configure(
        LLM_PROVIDER="deepseek",
        LLM_MODEL="deepseek-flash",
        LLM_THINKING_ENABLED=True,
        LLM_REASONING_EFFORT="high",
    )

    kwargs = build_chat_kwargs([{"role": "user", "content": "ok"}], temperature=0, thinking=False)

    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in kwargs
    assert kwargs["temperature"] == 0


def test_effort_none_disables_thinking_entirely(configure):
    configure(
        LLM_PROVIDER="deepseek",
        LLM_MODEL="deepseek-flash",
        LLM_THINKING_ENABLED=True,
        LLM_REASONING_EFFORT="none",
    )

    kwargs = build_chat_kwargs([{"role": "user", "content": "ok"}])

    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in kwargs


def test_other_providers_get_no_deepseek_thinking_fields(configure):
    configure(
        LLM_PROVIDER="openai",
        LLM_MODEL="gpt-4o-mini",
        LLM_THINKING_ENABLED=True,
        LLM_REASONING_EFFORT="high",
    )

    kwargs = build_chat_kwargs([{"role": "user", "content": "hi"}], temperature=0.3)

    assert "extra_body" not in kwargs
    assert "reasoning_effort" not in kwargs
    assert kwargs["temperature"] == 0.3
    assert kwargs["max_tokens"] == llm_config.LLM_MAX_TOKENS


# --- JSON Output contract ------------------------------------------------------


def test_json_tasks_send_json_object_and_mention_json_in_the_prompt(configure, sdk):
    configure(LLM_API_KEY="test-key", LLM_PROVIDER="deepseek", LLM_MODEL="deepseek-flash")
    calls = sdk(SimpleNamespace(content='{"explanations": {"a": "理由"}}'))

    result = LLMService().chat_json("你是导师", "给出理由", {"_fallback": True})

    assert result == {"explanations": {"a": "理由"}}
    request = calls[0]
    assert request["response_format"] == {"type": "json_object"}
    assert "JSON" in request["messages"][0]["content"]
    assert request["max_tokens"] == llm_config.LLM_MAX_TOKENS


def test_empty_provider_content_is_a_failure_not_an_evaluation(configure, sdk):
    configure(LLM_API_KEY="test-key", LLM_MAX_RETRIES=0)
    sdk(SimpleNamespace(content=""))

    with ai_audit.ai_invocation("case_evaluation") as invocation:
        result = LLMService().chat_json("你是评测者", "请评分", {"_fallback": True})

    assert result == {"_fallback": True}
    assert invocation.fallback_used is True
    assert invocation.error_type == "EmptyResponse"


def test_reasoning_content_is_dropped_and_never_audited(configure, sdk):
    configure(LLM_API_KEY="test-key", LLM_MAX_RETRIES=0)
    sdk(SimpleNamespace(content="最终回答", reasoning_content="这是不应外泄的思维链"))

    answer = LLMService().chat_completion("你是导师", "请回答", "fallback")

    assert answer == "最终回答"
    assert "思维链" not in answer
    # The audit row has no column that could carry a reasoning trace or a body.
    columns = set(AIInvocation.__table__.columns.keys())
    assert not columns & {"reasoning_content", "prompt", "response", "content"}


# --- probe ---------------------------------------------------------------------


def test_probe_is_cheap_non_thinking_and_returns_only_metadata(configure, sdk):
    configure(
        LLM_API_KEY="test-key",
        LLM_PROVIDER="deepseek",
        LLM_MODEL="deepseek-flash",
        LLM_THINKING_ENABLED=True,
        LLM_REASONING_EFFORT="high",
    )
    calls = sdk(SimpleNamespace(content="ok", reasoning_content="a very expensive reasoning trace"))

    outcome = LLMService().probe()

    request = calls[0]
    assert request["extra_body"] == {"thinking": {"type": "disabled"}}
    assert request["max_tokens"] == PROBE_MAX_TOKENS
    assert "reasoning_effort" not in request
    assert request["messages"][0]["content"] == llm_module.PROBE_PROMPT

    assert set(outcome) == {"reachable", "latency_ms", "error_type"}
    assert outcome["reachable"] is True
    assert outcome["error_type"] is None
    assert "expensive reasoning trace" not in json.dumps(outcome)


# --- retry semantics -----------------------------------------------------------


@pytest.mark.parametrize(
    "status,retryable",
    [
        (400, False),  # invalid format
        (401, False),  # authentication
        (402, False),  # insufficient balance
        (422, False),  # invalid parameters
        (429, True),  # rate limited
        (500, True),  # server error
        (503, True),  # overloaded
    ],
)
def test_official_error_codes_map_to_retryable_or_permanent(status, retryable):
    assert classify_provider_error(_FakeStatusError(status)) == (f"HTTP{status}", retryable)


def test_network_and_content_failures_are_transient():
    assert classify_provider_error(TimeoutError("timed out"))[1] is True
    assert classify_provider_error(ValueError("LLM returned an empty response")) == ("EmptyResponse", True)


def test_permanent_provider_failure_is_not_retried(configure, monkeypatch):
    configure(LLM_API_KEY="test-key", LLM_MAX_RETRIES=2)
    monkeypatch.setattr(llm_module, "RETRY_BACKOFF_SECONDS", 0)
    attempts = {"count": 0}

    class _Unauthorised:
        def chat(self, *_args, **_kwargs):
            attempts["count"] += 1
            raise _FakeStatusError(401)

    monkeypatch.setattr(LLMService, "_client", lambda self: _Unauthorised())

    with ai_audit.ai_invocation("case_evaluation") as invocation:
        result = LLMService().chat_completion("你是评测者", "请回答", "rule-fallback")

    assert result == "rule-fallback"
    assert attempts["count"] == 1
    assert invocation.fallback_used is True
    assert invocation.error_type == "HTTP401"


def test_transient_provider_failure_is_retried_within_the_bound(configure, monkeypatch):
    configure(LLM_API_KEY="test-key", LLM_MAX_RETRIES=2)
    monkeypatch.setattr(llm_module, "RETRY_BACKOFF_SECONDS", 0)
    attempts = {"count": 0}

    class _Overloaded:
        def chat(self, *_args, **_kwargs):
            attempts["count"] += 1
            raise _FakeStatusError(503)

    monkeypatch.setattr(LLMService, "_client", lambda self: _Overloaded())

    result = LLMService().chat_completion("你是导师", "请回答", "rule-fallback")

    assert result == "rule-fallback"
    assert attempts["count"] == 3  # the first attempt plus LLM_MAX_RETRIES
