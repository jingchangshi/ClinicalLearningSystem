"""The web tier must outwait the model transport it proxies.

Next.js aborts every rewrite-proxied request after ``experimental.proxyTimeout``
(30s when unset, see ``next/dist/server/lib/router-utils/proxy-request.js``). The
backend's own worst case is ``LLM_TIMEOUT_SECONDS * (LLM_MAX_RETRIES + 1)`` plus
backoff. When the proxy budget is the smaller of the two, a real evaluation that
the backend completes is reported to the browser as a 500 — which is exactly how
one production submit failed while its Score row was already written.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
NEXT_CONFIG = REPO_ROOT / "frontend" / "next.config.ts"
BACKEND_ENV_EXAMPLE = REPO_ROOT / "deploy" / "env" / "backend.env.example"


def _proxy_timeout_ms() -> int:
    match = re.search(r"proxyTimeout:\s*([0-9_]+)", NEXT_CONFIG.read_text())
    assert match, "next.config.ts must configure experimental.proxyTimeout"
    return int(match.group(1).replace("_", ""))


def _env_value(name: str) -> int:
    match = re.search(rf"^{name}=(\d+)$", BACKEND_ENV_EXAMPLE.read_text(), re.MULTILINE)
    assert match, f"{name} must be set numerically in {BACKEND_ENV_EXAMPLE.name}"
    return int(match.group(1))


def test_proxy_timeout_outlasts_the_transport_worst_case():
    proxy_ms = _proxy_timeout_ms()
    attempt_ms = _env_value("LLM_TIMEOUT_SECONDS") * 1000
    retries = _env_value("LLM_MAX_RETRIES")

    assert proxy_ms > attempt_ms * (retries + 1), (
        f"proxyTimeout {proxy_ms}ms must exceed the transport worst case of "
        f"{attempt_ms * (retries + 1)}ms ({retries + 1} attempts x {attempt_ms}ms)"
    )


def test_proxy_timeout_is_a_finite_positive_budget():
    proxy_ms = _proxy_timeout_ms()

    assert proxy_ms > 0
    # Not `null`/`0`: a hung backend must still end, it just must not end before
    # the transport's own bound.
    assert proxy_ms < 600_000
