"""Canonical LLM configuration.

Canonical variables (provider-neutral, preferred everywhere):

    LLM_PROVIDER, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    LLM_TIMEOUT_SECONDS, LLM_MAX_RETRIES

Legacy provider-specific aliases stay honoured so existing deployments keep
working, but they are deprecated and reported as such by ``llm_config_summary``:

    DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL
    OPENAI_API_KEY   / OPENAI_BASE_URL   / OPENAI_MODEL

Resolution order per value: canonical name, then the provider-specific alias. A
newer canonical variable always wins, so a configuration can no longer look
successful while actually calling a different endpoint or model.
"""

import os
from urllib.parse import urlparse

DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
}

DEFAULT_MODELS = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
}

DEPRECATED_ALIASES = {
    "LLM_API_KEY": ("DEEPSEEK_API_KEY", "OPENAI_API_KEY"),
    "LLM_BASE_URL": ("DEEPSEEK_BASE_URL", "OPENAI_BASE_URL"),
    "LLM_MODEL": ("DEEPSEEK_MODEL", "OPENAI_MODEL"),
}


def _resolve(canonical: str, aliases: tuple[str, ...]) -> tuple[str | None, str | None]:
    for name in (canonical, *aliases):
        value = os.getenv(name)
        if value and value.strip():
            return value.strip(), name
    return None, None


LLM_API_KEY, LLM_API_KEY_SOURCE = _resolve("LLM_API_KEY", DEPRECATED_ALIASES["LLM_API_KEY"])
LLM_BASE_URL, LLM_BASE_URL_SOURCE = _resolve("LLM_BASE_URL", DEPRECATED_ALIASES["LLM_BASE_URL"])
LLM_MODEL, LLM_MODEL_SOURCE = _resolve("LLM_MODEL", DEPRECATED_ALIASES["LLM_MODEL"])


def _infer_provider() -> tuple[str | None, str]:
    explicit = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if explicit:
        return explicit, "LLM_PROVIDER"
    for source in (LLM_API_KEY_SOURCE, LLM_BASE_URL_SOURCE, LLM_MODEL_SOURCE):
        if not source:
            continue
        prefix = source.split("_", 1)[0].lower()
        if prefix in DEFAULT_BASE_URLS:
            return prefix, f"inferred:{source}"
    host = (urlparse(LLM_BASE_URL or "").hostname or "").lower()
    for name in DEFAULT_BASE_URLS:
        if name in host:
            return name, "inferred:LLM_BASE_URL host"
    return ("openai-compatible", "inferred:custom host") if LLM_BASE_URL else (None, "unset")


LLM_PROVIDER, LLM_PROVIDER_SOURCE = _infer_provider()

if LLM_BASE_URL is None and LLM_PROVIDER in DEFAULT_BASE_URLS:
    LLM_BASE_URL = DEFAULT_BASE_URLS[LLM_PROVIDER]
    LLM_BASE_URL_SOURCE = f"default:{LLM_PROVIDER}"

if LLM_MODEL is None and LLM_PROVIDER in DEFAULT_MODELS:
    LLM_MODEL = DEFAULT_MODELS[LLM_PROVIDER]
    LLM_MODEL_SOURCE = f"default:{LLM_PROVIDER}"

LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "12"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

LLM_CONFIGURED = bool(LLM_API_KEY and LLM_BASE_URL and LLM_MODEL)


def llm_config_summary() -> dict:
    """Non-secret diagnostics for logs and the teacher runtime card."""

    deprecated_in_use = sorted(
        source
        for source in (
            LLM_API_KEY_SOURCE,
            LLM_BASE_URL_SOURCE,
            LLM_MODEL_SOURCE,
        )
        if source in {alias for aliases in DEPRECATED_ALIASES.values() for alias in aliases}
    )
    return {
        "configured": LLM_CONFIGURED,
        "provider": LLM_PROVIDER,
        "provider_source": LLM_PROVIDER_SOURCE,
        "model": LLM_MODEL,
        "base_url_host": urlparse(LLM_BASE_URL).hostname if LLM_BASE_URL else None,
        "api_key_source": LLM_API_KEY_SOURCE,
        "timeout_seconds": LLM_TIMEOUT_SECONDS,
        "max_retries": LLM_MAX_RETRIES,
        "deprecated_variables_in_use": deprecated_in_use,
    }
