#!/usr/bin/env python3
"""Bounded real-provider concurrency for one AI task at a time.

    cd backend
    uv run --python 3.11 --with-requirements requirements.txt \
        python tools/ai_concurrency.py --base-url http://127.0.0.1:8200 \
        --task case_evaluation --levels 2,5,10

Run it against a staging copy — it creates real case sessions. It reports the
latency distribution, the rate-limit / server-error counts, and how often the
application degraded to the rule fallback, which is the number that says whether
saturating the provider actually breaks the teaching flow.

It never prints a prompt, a response body or a credential.
"""

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request

ANSWERS = {
    "key_information": "发热、皮疹、ANA阳性、蛋白尿，需要评估器官受累与感染筛查。",
    "initial_diagnosis": "考虑系统性红斑狼疮，依据症状、抗体与器官受累。",
    "differential_diagnosis": "需排除感染、AOSD、HLH、淋巴瘤与其他结缔组织病。",
    "examination": "补充补体、抗dsDNA、尿蛋白定量与肺功能评估活动度。",
    "treatment": "激素联合免疫抑制剂，治疗前感染筛查，随访监测不良反应。",
}


def call(method: str, url: str, cookie: str | None = None, payload: dict | None = None, timeout: float = 300.0):
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode() if payload is not None else None, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return response.status, json.loads(body) if body else {}, response.headers.get_all("Set-Cookie") or []
    except urllib.error.HTTPError as error:
        return error.code, {}, []
    except Exception as error:  # network-level failure counts as a failed attempt
        return 0, {"error": type(error).__name__}, []


def login(base_url: str, username: str, password: str) -> str | None:
    _status, _body, cookies = call("POST", f"{base_url}/api/auth/login", payload={"username": username, "password": password})
    for cookie in cookies:
        if cookie.startswith("access_token="):
            return cookie.split(";", 1)[0]
    return None


def prepare_session(base_url: str, cookie: str, case_id: int) -> int | None:
    status, body, _ = call("POST", f"{base_url}/api/sessions/start", cookie, {"case_id": case_id})
    if status != 200 or "id" not in body:
        return None
    session_id = body["id"]
    for step, text in ANSWERS.items():
        call("POST", f"{base_url}/api/sessions/{session_id}/answers", cookie, {"step": step, "answer_text": text})
    return session_id


def one_request(base_url: str, cookie: str, task: str, session_id: int) -> dict:
    started = time.monotonic()
    if task == "tutor":
        status, body, _ = call(
            "POST", f"{base_url}/api/sessions/{session_id}/tutor", cookie, {"step": "differential_diagnosis"}
        )
        degraded = bool(body.get("tutor_question")) is False
    else:
        status, body, _ = call("POST", f"{base_url}/api/sessions/{session_id}/submit", cookie)
        summary = body.get("summary", body) if isinstance(body, dict) else {}
        degraded = str(summary.get("evaluation_mode", "")) == "rule_fallback"
    return {"status": status, "latency_ms": (time.monotonic() - started) * 1000, "degraded": degraded}


def run_level(base_url: str, accounts: list[tuple[str, str]], task: str, level: int, case_id: int) -> dict:
    prepared: list[tuple[str, int]] = []
    for index in range(level):
        username, password = accounts[index % len(accounts)]
        cookie = login(base_url, username, password)
        if not cookie:
            print(f"  could not authenticate {username}", file=sys.stderr)
            continue
        session_id = prepare_session(base_url, cookie, case_id)
        if session_id:
            prepared.append((cookie, session_id))
    if not prepared:
        return {"concurrency": level, "requests": 0}

    results: list[dict] = []
    lock = threading.Lock()

    def worker(item):
        outcome = one_request(base_url, item[0], task, item[1])
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(item,)) for item in prepared]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    wall = time.monotonic() - started

    latencies = sorted(item["latency_ms"] for item in results)
    percentile = lambda q: round(latencies[min(len(latencies) - 1, int(q * (len(latencies) - 1)))]) if latencies else None
    return {
        "concurrency": level,
        "requests": len(results),
        "wall_seconds": round(wall, 1),
        "latency_ms_p50": percentile(0.5),
        "latency_ms_p95": percentile(0.95),
        "latency_ms_max": round(latencies[-1]) if latencies else None,
        "http_429": sum(1 for item in results if item["status"] == 429),
        "http_5xx": sum(1 for item in results if 500 <= item["status"] < 600),
        "transport_errors": sum(1 for item in results if item["status"] == 0),
        "degraded": sum(1 for item in results if item["degraded"]),
        "mean_ms": round(statistics.mean(latencies)) if latencies else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8200")
    parser.add_argument("--task", choices=["tutor", "case_evaluation"], default="tutor")
    parser.add_argument("--levels", default="2,5,10")
    parser.add_argument("--accounts", default="student1,student2,student3,student4")
    parser.add_argument("--password", default="student123")
    parser.add_argument("--case-id", type=int, default=1)
    parser.add_argument("--json-out")
    args = parser.parse_args()

    accounts = [(name.strip(), args.password) for name in args.accounts.split(",") if name.strip()]
    rows = []
    print(f"task={args.task} base_url={args.base_url}")
    for level in [int(value) for value in args.levels.split(",")]:
        row = run_level(args.base_url, accounts, args.task, level, args.case_id)
        rows.append(row)
        print(
            f"concurrency={row['concurrency']:<3} requests={row.get('requests', 0):<3} "
            f"p50={row.get('latency_ms_p50')}ms p95={row.get('latency_ms_p95')}ms max={row.get('latency_ms_max')}ms "
            f"wall={row.get('wall_seconds')}s 429={row.get('http_429')} 5xx={row.get('http_5xx')} "
            f"transport_errors={row.get('transport_errors')} degraded={row.get('degraded')}"
        )

    if args.json_out:
        from pathlib import Path

        Path(args.json_out).write_text(json.dumps({"task": args.task, "results": rows}, ensure_ascii=False, indent=2))
        print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
