#!/usr/bin/env python3
"""Measure authenticated page latency for the pilot-readiness report.

    python3 scripts/measure_page_latency.py --samples 3
    python3 scripts/measure_page_latency.py --json

This is evidence tooling, not a test: it is never imported by pytest, and the
browser E2E suite must not assert absolute milliseconds. It reports one row per
endpoint with min/median/p95 so "page latency" and "AI task latency" can be
discussed as separate numbers.

The teacher token is minted from the operator's own ``JWT_SECRET`` (mode-600
file, never printed) so that measurement does not depend on a staff password.
No secret and no response body is ever written to stdout.
"""

import argparse
import hashlib
import hmac
import json
import os
import ssl
import statistics
import sys
import time
import urllib.error
import urllib.request
from base64 import urlsafe_b64encode
from pathlib import Path

# The pilot entry is HTTPS (see docs/ARCH.md §11). Override with
# CLINPATH_MEASURE_BASE_URL=http://127.0.0.1:8101 for a loopback-only run.
DEFAULT_BASE_URL = os.getenv("CLINPATH_MEASURE_BASE_URL", "https://clinpath.1031989.xyz")
DEFAULT_TEACHER_USER_ID = 4

STUDENT_TARGETS = (
    ("/api/student/dashboard", "student dashboard"),
    ("/api/student/pathway", "student pathway"),
    ("/api/student/competency", "student profile"),
)

TEACHER_TARGETS = (
    ("/api/teacher/dashboard", "teacher dashboard"),
    ("/api/teacher/students/{student_id}/learning-profile", "teacher student profile"),
)


def _b64(data: bytes) -> str:
    return urlsafe_b64encode(data).decode("ascii").rstrip("=")


def mint_token(secret: str, user_id: int, username: str, role: str) -> str:
    """HS256 JWT with the same claim shape as ``app.auth.create_access_token``."""

    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(
        json.dumps(
            {
                "sub": str(user_id),
                "username": username,
                "role": role,
                "student_id": None,
                "teacher_id": None,
                "iat": now,
                "exp": now + 3600,
            },
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    signature = _b64(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def read_jwt_secret(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        name, _, value = line.strip().partition("=")
        if name == "JWT_SECRET" and value:
            return value
    return None


def _open(request: urllib.request.Request, timeout: float) -> tuple[int, str]:
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return response.status, response.read(2048).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, ""


def login(base_url: str, username: str, password: str, timeout: float) -> str | None:
    request = urllib.request.Request(
        f"{base_url}/api/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for header, value in response.getheaders():
                if header.lower() == "set-cookie" and value.startswith("access_token="):
                    return value.split(";", 1)[0]
    except urllib.error.HTTPError as error:
        print(f"login failed for {username}: HTTP {error.code}", file=sys.stderr)
    return None


def measure(base_url: str, path: str, cookie: str, samples: int, timeout: float) -> dict:
    timings: list[float] = []
    statuses: list[int] = []
    for _ in range(samples):
        request = urllib.request.Request(f"{base_url}{path}", headers={"Cookie": cookie})
        started = time.monotonic()
        status, _body = _open(request, timeout)
        timings.append((time.monotonic() - started) * 1000)
        statuses.append(status)
    ordered = sorted(timings)
    return {
        "path": path,
        "samples": samples,
        "statuses": statuses,
        "min_ms": round(ordered[0]),
        "median_ms": round(statistics.median(ordered)),
        "max_ms": round(ordered[-1]),
        "p95_ms": round(ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("CLINPATH_MEASURE_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--student-id", type=int, default=1)
    parser.add_argument("--student-username", default=os.getenv("CLINPATH_STUDENT_USERNAME", "student1"))
    parser.add_argument("--student-password", default=os.getenv("CLINPATH_STUDENT_PASSWORD", "student123"))
    parser.add_argument("--teacher-user-id", type=int, default=DEFAULT_TEACHER_USER_ID)
    parser.add_argument(
        "--backend-env",
        default=os.getenv("CLINPATH_BACKEND_ENV", str(Path.home() / ".config" / "clinpath" / "backend.env")),
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    student_cookie = login(base_url, args.student_username, args.student_password, args.timeout)
    if not student_cookie:
        print("could not authenticate the student measurement account", file=sys.stderr)
        return 2

    secret = read_jwt_secret(Path(args.backend_env))
    teacher_cookie = f"access_token={mint_token(secret, args.teacher_user_id, 'measure', 'teacher')}" if secret else None

    results = []
    for path, label in STUDENT_TARGETS:
        results.append({**measure(base_url, path, student_cookie, args.samples, args.timeout), "label": label, "actor": "student"})
    if teacher_cookie:
        for path, label in TEACHER_TARGETS:
            resolved = path.format(student_id=args.student_id)
            results.append({**measure(base_url, resolved, teacher_cookie, args.samples, args.timeout), "label": label, "actor": "teacher"})

    payload = {"base_url": base_url, "samples": args.samples, "results": results}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"base url : {base_url}")
    print(f"samples  : {args.samples}")
    print(f"{'endpoint':<34}{'status':<8}{'min':>8}{'median':>9}{'p95':>8}{'max':>8}")
    for row in results:
        status = "ok" if set(row["statuses"]) == {200} else ",".join(str(code) for code in row["statuses"])
        print(
            f"{row['path']:<34}{status:<8}{row['min_ms']:>7}ms{row['median_ms']:>8}ms{row['p95_ms']:>7}ms{row['max_ms']:>7}ms"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
