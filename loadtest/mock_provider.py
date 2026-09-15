#!/usr/bin/env python3
"""Deterministic OpenAI-compatible provider for capacity testing.

ClinPath's capacity and DeepSeek's capacity are different questions. This server
answers the first one without spending quota: it can simulate a slow model, a
rate limit, a 5xx, a timeout, an unparseable body or an empty body, so the
application's own behaviour (isolation, fallback, SQLite health, read latency)
can be measured on its own.

    python3 loadtest/mock_provider.py --port 8300 --mode slow --latency-ms 8000
    python3 loadtest/mock_provider.py --port 8300 --mode 429

Modes: ok | slow | 429 | 500 | timeout | invalid_json | empty
The mode can also be changed at runtime: POST /control/mode?mode=429
"""

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CASE_DIMENSIONS = {
    key: {
        "score": 72.0,
        "confidence": 0.7,
        "evidence": ["合成证据：学生提到了发热与皮疹"],
        "missing_points": ["合成缺口：未提及补体"],
        "feedback": "补充证据权重说明。",
    }
    for key in (
        "medical_knowledge",
        "key_information",
        "differential_diagnosis",
        "evidence_integration",
        "clinical_decision",
        "evidence_based_medicine",
    )
}

JSON_BODY = {
    "explanations": {"case:1": "合成理由：鉴别诊断链条需要拓宽。"},
    "insight": "合成洞察：班级共性短板为鉴别诊断。",
    "dimensions": CASE_DIMENSIONS,
    "strengths": ["合成优点"],
    "priority_gaps": ["合成缺口"],
    "overall_feedback": "合成形成性反馈。",
    "safety_flags": [],
    "communication_score": 70,
    "reasoning_score": 70,
    "history_taking_score": 70,
    "humanistic_care_score": 70,
    "total_score": 70,
    "feedback": "合成反馈",
}

TEXT_BODY = "请说明你目前的判断依据，以及还有哪些证据与它矛盾？为什么？"

STATE = {"mode": "ok", "latency_ms": 0}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args) -> None:  # keep the load-test console readable
        return

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path.startswith("/health"):
            self._json(200, {"status": "ok", "mode": STATE["mode"], "latency_ms": STATE["latency_ms"]})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path.startswith("/control/mode"):
            if "mode=" in self.path:
                STATE["mode"] = self.path.split("mode=", 1)[1].split("&", 1)[0]
            if "latency_ms=" in self.path:
                STATE["latency_ms"] = int(self.path.split("latency_ms=", 1)[1].split("&", 1)[0])
            self._json(200, dict(STATE))
            return
        if not self.path.endswith("/chat/completions"):
            self._json(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        raw_request = self.rfile.read(length) if length else b"{}"
        try:
            request = json.loads(raw_request)
        except json.JSONDecodeError:
            request = {}

        mode = STATE["mode"]
        latency = STATE["latency_ms"] / 1000.0
        if mode == "timeout":
            time.sleep(max(latency, 120.0))
        elif latency:
            time.sleep(latency)

        if mode == "429":
            self._json(429, {"error": {"message": "rate limited", "type": "rate_limit_error"}})
            return
        if mode == "500":
            self._json(500, {"error": {"message": "provider failure", "type": "server_error"}})
            return

        wants_json = bool(request.get("response_format"))
        if mode == "invalid_json":
            content = "这不是 JSON"
        elif mode == "empty":
            content = ""
        elif wants_json:
            content = json.dumps(JSON_BODY, ensure_ascii=False)
        else:
            content = TEXT_BODY

        self._json(
            200,
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.get("model", "mock-model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8300)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--mode", default="ok")
    parser.add_argument("--latency-ms", type=int, default=0)
    args = parser.parse_args()
    STATE["mode"] = args.mode
    STATE["latency_ms"] = args.latency_ms

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    print(f"mock provider listening on http://{args.host}:{args.port} mode={args.mode} latency_ms={args.latency_ms}")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
