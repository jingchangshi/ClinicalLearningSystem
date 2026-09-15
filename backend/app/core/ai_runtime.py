"""In-process AI runtime state.

Answers one question without leaking secrets: is the configured model actually
reachable, and was the last evaluation produced by the model or by the
deterministic rule fallback?
"""

import threading
from datetime import datetime, timezone


class AIRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict = {
            "last_probe_at": None,
            "last_probe_ok": None,
            "last_probe_latency_ms": None,
            "last_error_type": None,
            "last_call_at": None,
            "last_call_mode": None,
            "calls": 0,
            "failures": 0,
            "fallbacks": 0,
        }

    def record_probe(self, ok: bool, latency_ms: int | None, error_type: str | None) -> None:
        with self._lock:
            self._state["last_probe_at"] = _now()
            self._state["last_probe_ok"] = ok
            self._state["last_probe_latency_ms"] = latency_ms
            if error_type:
                self._state["last_error_type"] = error_type

    def record_call(self, mode: str, error_type: str | None = None) -> None:
        with self._lock:
            self._state["last_call_at"] = _now()
            self._state["last_call_mode"] = mode
            self._state["calls"] += 1
            if mode == "rule_fallback":
                self._state["fallbacks"] += 1
            if error_type:
                self._state["failures"] += 1
                self._state["last_error_type"] = error_type

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._state)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


ai_runtime = AIRuntime()
