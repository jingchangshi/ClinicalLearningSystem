"""Provision clearly-labelled SYNTHETIC test accounts and the 7x7 / 98-sitting study.

Everything created here is test data for *software acceptance*:

    data_origin = "pilot_test"       (never "real_study")
    student names / class names carry "TEST"
    every student gets a CompetencyProfile (a Student without one 500s the
    teacher dashboard, so the fixture must never create one)

The study itself is built over HTTP with the same API a real administrator uses;
the script never writes assessment tables directly. If the API refuses, the
harness fails instead of fabricating a state the product cannot produce.

Re-running is safe: existing accounts/records are reused, and every creation
step checks the API's own listing first.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
WORKPACKAGES = REPO / "docs" / "teaching_grant_2026" / "workpackages" / "A_cases"

STUDENT_PASSWORD = "test-student-pw"
TEACHER_PASSWORD = "test-teacher-pw"
ADMIN_PASSWORD = "test-admin-pw"
TEST_COHORT_CODES = [f"TEST-C{i:02d}" for i in range(1, 8)]
ORIGIN = "pilot_test"
PROTOCOL = "TEST-PROTOCOL-2026-10-18"

STAFF_SPECS = [
    {"username": "test_teacher_a", "role": "teacher", "display": "TEST 测试教师A（非真实教师）", "teacher_no": "TEST-TA"},
    {"username": "test_teacher_b", "role": "teacher", "display": "TEST 测试教师B（非真实教师）", "teacher_no": "TEST-TB"},
    {"username": "test_adjudicator", "role": "teacher", "display": "TEST 测试裁决人（非真实教师）", "teacher_no": "TEST-TC"},
    {"username": "test_admin", "role": "admin", "display": "TEST 研究管理员", "teacher_no": None},
]


class Api:
    """A cookie-jar HTTP client; one instance == one logged-in browser session."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, object]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("content-type", "application/json")
        try:
            with self.opener.open(req, timeout=180) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except Exception:  # noqa: BLE001 - a non-JSON error body is still an error
                return exc.code, raw.decode(errors="replace")

    def ok(self, method: str, path: str, body: dict | None = None):
        status, payload = self.request(method, path, body)
        if status >= 400:
            raise SystemExit(f"{method} {path} -> {status}: {json.dumps(payload, ensure_ascii=False)[:800]}")
        return payload

    def login(self, username: str, password: str) -> "Api":
        self.ok("POST", "/api/auth/login", {"username": username, "password": password})
        return self


def _backend_python(args: list[str], *, database_url: str, jwt_secret: str, stdin: str = "") -> None:
    """Run a backend module (manage_users) against the throwaway database.

    The fixture is itself started through ``uv run --with-requirements`` so
    bcrypt/fastapi are importable; in that case reuse this interpreter. Falling
    back to ``uv run`` keeps a bare ``python3 build_fixture.py`` working too.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        "DATABASE_URL": database_url,
        "JWT_SECRET": jwt_secret,
        "CLINPATH_ENV": "development",
    }
    try:
        import fastapi  # noqa: F401 - probe for the backend environment
        # args is ["python", "-m", "app.manage_users", ...]; reuse this interpreter.
        assert args[:2] == ["python", "-m"], f"unexpected command shape: {args}"
        command = [sys.executable, *args[1:]]
    except ModuleNotFoundError:
        uv = os.environ.get("UV_BIN", "uv")
        command = [uv, "run", "--python", "3.11", "--with-requirements", "requirements.txt", *args]
    proc = subprocess.run(command, cwd=str(REPO / "backend"), env=env, input=stdin,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        message = (proc.stdout + proc.stderr).strip()
        if "already exists" in message.lower():
            return  # idempotent re-run
        raise SystemExit(f"{' '.join(args)} failed:\n{message}")


def provision_staff(args, spec: dict) -> None:
    """Staff accounts exist only through manage_users (never seeded)."""
    if spec["role"] == "teacher":
        cmd = ["python", "-m", "app.manage_users", "create-teacher", spec["username"],
               "--name", spec["display"], "--teacher-no", spec["teacher_no"], "--department", "TEST 测试科室"]
        password = TEACHER_PASSWORD
    else:
        cmd = ["python", "-m", "app.manage_users", "create-admin", spec["username"]]
        password = ADMIN_PASSWORD
    _backend_python(cmd, database_url=args.database_url, jwt_secret=args.jwt_secret, stdin=password + "\n")


def resolve_staff(admin_api: Api) -> dict[str, dict]:
    """Resolve staff ids through the product's own directory endpoint.

    ``GET /api/assessments/admin/staff`` (added in 4cd4a18) is the contract the UI
    itself uses, so the fixture exercises it rather than reading ids out of the
    throwaway database. There is deliberately no DB fallback: if the endpoint is
    missing or wrong, the fixture must fail loudly instead of hiding it.

    The response carries exactly {user_id, display_name, role, teacher_no} and no
    username, so staff are matched by teacher_no (teachers) or display_name (the
    admin, whose display_name falls back to its username).
    """
    status, rows = admin_api.request("GET", "/api/assessments/admin/staff")
    if status >= 400:
        raise SystemExit(
            f"GET /api/assessments/admin/staff -> {status}: {rows}. "
            "The fixture needs the staff directory; it will not read ids from the database."
        )
    staff: dict[str, dict] = {}
    for spec in STAFF_SPECS:
        wanted = {spec["display"], spec["username"]}
        match = next((r for r in rows if spec["teacher_no"] and r.get("teacher_no") == spec["teacher_no"]), None)
        if match is None:
            match = next((r for r in rows if r.get("display_name") in wanted), None)
        if match is None:
            raise SystemExit(f"could not resolve staff id for {spec['username']}: {rows}")
        staff[spec["username"]] = match
    return staff


def ensure_students(db_path: Path, count: int) -> list[int]:
    """Create TEST students directly in the throwaway SQLite (the API has no POST /students).

    A CompetencyProfile is created for every student: the teacher dashboard 500s
    on a Student without one, and the research fixture must not reproduce that.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        ids: list[int] = []
        for i in range(1, count + 1):
            student_no = f"TEST2026{i:03d}"
            row = conn.execute("SELECT id FROM students WHERE student_no = ?", (student_no,)).fetchone()
            if row is None:
                cur = conn.execute(
                    "INSERT INTO students (name, student_no, class_name, current_stage) VALUES (?, ?, ?, ?)",
                    (f"TEST测试学生{i:02d}", student_no, "TEST 临床医学测试班", "基础"),
                )
                student_id = int(cur.lastrowid)
            else:
                student_id = int(row[0])
            if conn.execute("SELECT id FROM competency_profiles WHERE student_id = ?", (student_id,)).fetchone() is None:
                conn.execute(
                    "INSERT INTO competency_profiles (student_id, medical_knowledge, skill_operation, key_information,"
                    " differential_diagnosis, evidence_integration, clinical_decision, evidence_based_medicine,"
                    " communication, humanistic_care, learning_engagement, updated_at)"
                    " VALUES (?, 60, 75, 60, 60, 60, 60, 60, 75, 75, 60, datetime('now'))",
                    (student_id,),
                )
            ids.append(student_id)
        conn.commit()
        return ids
    finally:
        conn.close()


def ensure_student_logins(db_path: Path, student_ids: list[int]) -> dict[int, str]:
    """Give each TEST student a login using the backend's own bcrypt hash."""
    sys.path.insert(0, str(REPO / "backend"))
    from app.auth import hash_password  # noqa: E402 - backend package import

    conn = sqlite3.connect(str(db_path))
    try:
        out: dict[int, str] = {}
        for student_id in student_ids:
            row = conn.execute("SELECT username FROM users WHERE student_id = ?", (student_id,)).fetchone()
            if row is None:
                username = f"test_student_{student_id:03d}"
                conn.execute(
                    "INSERT INTO users (username, password_hash, role, student_id, created_at)"
                    " VALUES (?, ?, 'student', ?, datetime('now'))",
                    (username, hash_password(STUDENT_PASSWORD), student_id),
                )
                out[student_id] = username
            else:
                out[student_id] = str(row[0])
        conn.commit()
        return out
    finally:
        conn.close()


def load_form_payloads() -> dict[str, dict]:
    """The A01/A02 drafts are labelled PENDING_REAL_REVIEW: they are test payloads here."""
    payloads = {}
    for label, filename in (("A01", "A01_assessment_payload_DRAFT.json"), ("A02", "A02_assessment_payload_DRAFT.json")):
        payload = json.loads((WORKPACKAGES / filename).read_text())
        payload["code"] = "TEST-" + payload["code"]  # never collide with a future real form code
        payload["title"] = "[TEST 合成验收] " + payload["title"]
        payloads[label] = payload
    return payloads


def ensure_forms(admin_api: Api, staff: dict, payloads: dict[str, dict], base: str) -> dict[str, int]:
    """Create, get two distinct teacher approvals, then publish A01 and A02."""
    teacher_a = staff["test_teacher_a"]["user_id"]
    teacher_b = staff["test_teacher_b"]["user_id"]
    form_ids: dict[str, int] = {}
    existing = {row["code"]: row for row in admin_api.ok("GET", "/api/assessments/forms/admin/all")}

    for label, payload in payloads.items():
        row = existing.get(payload["code"])
        if row is None:
            row = admin_api.ok("POST", "/api/assessments/forms", payload)
        form_id = row["id"]
        detail = admin_api.ok("GET", f"/api/assessments/forms/{form_id}/admin")
        if detail["review_status"] != "APPROVED_FOR_ASSESSMENT":
            if not detail["assigned_reviewers"]:
                admin_api.ok("POST", f"/api/assessments/forms/{form_id}/reviewers",
                             {"teacher_user_ids": [teacher_a, teacher_b]})
            for username in ("test_teacher_a", "test_teacher_b"):
                teacher_api = Api(base).login(username, TEACHER_PASSWORD)
                reviewable = teacher_api.ok("GET", "/api/assessments/forms/reviewable")
                mine = next((f for f in reviewable if f["id"] == form_id), None)
                if mine is None or mine["reviewed_by_me"]:
                    continue
                teacher_api.ok("POST", f"/api/assessments/forms/{form_id}/review",
                               {"decision": "approve",
                                "comment": f"TEST 合成验收：{username} 独立审核通过（非真实教师审核）"})
            admin_api.ok("POST", f"/api/assessments/forms/{form_id}/approve")
        form_ids[label] = form_id
    return form_ids


def verify_my_forms(admin_api: Api, base: str, form_ids: dict[str, int]) -> dict:
    """Exercise ``GET /api/assessments/forms/mine`` against the fixture it just made.

    Two things must hold, and both are about the confidentiality the endpoint
    exists to protect: the authoring admin sees the forms it created, and a
    teacher who merely *reviewed* them sees none of them in their own list.
    """
    mine = admin_api.ok("GET", "/api/assessments/forms/mine")
    mine_ids = {row["id"] for row in mine}
    missing = sorted(set(form_ids.values()) - mine_ids)
    if missing:
        raise SystemExit(f"/forms/mine is missing forms the admin authored: {missing}")

    teacher_api = Api(base).login("test_teacher_a", TEACHER_PASSWORD)
    teacher_mine = teacher_api.ok("GET", "/api/assessments/forms/mine")
    leaked = sorted(row["code"] for row in teacher_mine if row["code"] in {"TEST-CASE-A01-UA-V1", "TEST-CASE-A02-SICCA-V1"})
    if leaked:
        raise SystemExit(f"/forms/mine showed a reviewer forms they did not author: {leaked}")
    return {"admin_forms": len(mine), "teacher_forms": len(teacher_mine),
            "teacher_sees_reviewed_forms": bool(leaked)}


def ensure_cohorts(admin_api: Api, student_ids: list[int], staff: dict) -> None:
    existing = {c["cohort_code"] for c in admin_api.ok("GET", "/api/assessments/admin/cohorts")}
    teacher_a = staff["test_teacher_a"]["user_id"]
    for i, code in enumerate(TEST_COHORT_CODES, start=1):
        if code not in existing:
            admin_api.ok("POST", "/api/assessments/admin/cohorts", {
                "cohort_code": code,
                "label": f"TEST 合成验收批次 {i}（非真实轮转批次）",
                "expected_size": 7,
                "teaching_user_ids": [teacher_a],
                "data_origin": ORIGIN,
            })
    cohorts = {c["cohort_code"]: c for c in admin_api.ok("GET", "/api/assessments/admin/cohorts")}
    for i, code in enumerate(TEST_COHORT_CODES):
        if cohorts[code]["enrolled"] < 7:
            admin_api.ok("POST", f"/api/assessments/admin/cohorts/{code}/enrollments",
                         {"student_ids": student_ids[i * 7:(i + 1) * 7]})


def ensure_allocations(admin_api: Api) -> dict:
    """Form order first, then the group draw: the order is the study's own invariant."""
    existing = {a["kind"] for a in admin_api.ok("GET", "/api/assessments/admin/allocations")}
    if "form_order" not in existing:
        admin_api.ok("POST", "/api/assessments/admin/allocations/form-order",
                     {"data_origin": ORIGIN, "protocol_version": PROTOCOL, "seed": "test-form-order-seed-20261018"})
    if "cluster_group" not in existing:
        admin_api.ok("POST", "/api/assessments/admin/allocations/cluster",
                     {"data_origin": ORIGIN, "protocol_version": PROTOCOL, "mode": "randomized",
                      "seed": "test-cluster-seed-20261018"})
    return {a["kind"]: a for a in admin_api.ok("GET", "/api/assessments/admin/allocations")}


def study_arms(allocations: dict) -> dict[str, list[str]]:
    """Which batch is which arm, read from the product's own frozen draw.

    The draw is the only authority on the arms, so the fixture reads it rather than
    assuming a split. ``GET /api/assessments/admin/allocations`` returns the full
    stored record, which is what ``app.research.study_access`` resolves a cohort
    through as well -- one source, so the two cannot disagree.
    """
    record = allocations["cluster_group"].get("record") or {}
    return {
        "clinpath": list(record.get("clinpath_cohorts") or []),
        "cbl": list(record.get("cbl_cohorts") or []),
    }


def ensure_schedule(admin_api: Api, form_ids: dict[str, int], staff: dict, demo_cohort: str) -> dict:
    """98 sittings: T0 open now, T1 the next day.

    The end-to-end browser flow that runs against this stack (R8.2) sits T0, trains
    through the *ClinPath formative intervention*, and sits T1 in one automated run.
    So the demo batch must be a batch whose students may train at all: under the
    study access policy a CBL batch may not, so the caller passes a ClinPath batch
    here. Its timeline is compressed (T0 closes T1_GAP_SECONDS after scheduling, T1
    opens immediately after) while the other six batches keep the realistic D1 -> D6
    spacing.

    A re-run reuses the recorded windows: the planner refuses a changed schedule
    for an existing sitting, which is the behaviour we want to see, not bypass.
    """
    now = time.time()
    t1_gap = int(os.environ.get("E2E_T1_GAP_SECONDS", "90"))

    def stamp(offset: float) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + offset))

    windows = {}
    for code in TEST_COHORT_CODES:
        if code == demo_cohort:
            windows[code] = {"T0": {"start": stamp(-3600), "end": stamp(t1_gap)},
                             "T1": {"start": stamp(t1_gap + 1), "end": stamp(t1_gap + 1 + 6 * 3600)}}
        else:
            windows[code] = {"T0": {"start": stamp(-3600), "end": stamp(6 * 3600)},
                             "T1": {"start": stamp(24 * 3600), "end": stamp(30 * 3600)}}
    return admin_api.ok("POST", "/api/assessments/admin/design/schedule", {
        "data_origin": ORIGIN,
        "forms": {"A01": form_ids["A01"], "A02": form_ids["A02"]},
        "windows": windows,
        "rater_a_id": staff["test_teacher_a"]["user_id"],
        "rater_b_id": staff["test_teacher_b"]["user_id"],
        "adjudicator_user_id": staff["test_adjudicator"]["user_id"],
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision the synthetic 7x7 study fixture over the live API")
    parser.add_argument("--api", default="http://127.0.0.1:8400", help="isolated backend base URL")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--jwt-secret", required=True)
    parser.add_argument("--students", type=int, default=49)
    parser.add_argument("--manifest", default=None, help="write created ids here as JSON")
    args = parser.parse_args()

    db_path = Path(args.database_url.replace("sqlite:///", "", 1))
    if "/tmp/" not in str(db_path):
        raise SystemExit("refusing to provision a database outside /tmp")
    base = args.api.rstrip("/")
    if base.endswith("/api"):
        base = base[:-4]

    for spec in STAFF_SPECS:
        provision_staff(args, spec)
    admin_api = Api(base).login("test_admin", ADMIN_PASSWORD)
    staff = resolve_staff(admin_api)

    student_ids = ensure_students(db_path, args.students)
    logins = ensure_student_logins(db_path, student_ids)

    form_ids = ensure_forms(admin_api, staff, load_form_payloads(), base)
    my_forms_check = verify_my_forms(admin_api, base, form_ids)
    ensure_cohorts(admin_api, student_ids, staff)
    allocations = ensure_allocations(admin_api)
    arms = study_arms(allocations)
    cohort_students = {
        code: student_ids[index * 7:(index + 1) * 7] for index, code in enumerate(TEST_COHORT_CODES)
    }
    # The end-to-end flow trains through the ClinPath intervention, so its demo
    # batch has to be a ClinPath batch. Refuse loudly rather than hand it a batch
    # the access policy will (correctly) refuse mid-flow.
    demo_cohort = arms["clinpath"][0] if arms["clinpath"] else None
    if demo_cohort is None:
        raise SystemExit(
            f"the frozen draw names no ClinPath batch ({arms}); the R8.2 flow cannot be exercised on this fixture"
        )
    schedule = ensure_schedule(admin_api, form_ids, staff, demo_cohort)

    manifest = {
        "data_origin": ORIGIN,
        "label": "SYNTHETIC / SIMULATED_NOT_HUMAN — software acceptance only, not real students",
        "staff_resolved_via": "GET /api/assessments/admin/staff",
        "my_forms_check": my_forms_check,
        "student_ids": student_ids,
        "student_logins": {str(k): v for k, v in logins.items()},
        "student_password": STUDENT_PASSWORD,
        "staff": staff,
        "form_ids": form_ids,
        "study_groups": arms,
        "cohort_students": cohort_students,
        "demo_cohort": demo_cohort,
        "allocations": {k: {"allocation_version": v["allocation_version"], "mode": v["mode"],
                            "content_hash": v["content_hash"]} for k, v in allocations.items()},
        "schedule": {k: schedule[k] for k in ("created", "existing", "students", "cohorts")},
    }
    if args.manifest:
        Path(args.manifest).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: manifest[k] for k in ("label", "form_ids", "study_groups", "demo_cohort",
                                               "allocations", "schedule")},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
