#!/usr/bin/env python3
"""Build a disposable acceptance dataset for the round-2 browser acceptance run.

The acceptance stack for `frontend/tests/e2e/demo-readiness.spec.ts` must show a
*class*, not a single learner: the research-export preview asserts at least three
students, three learning modules and three distinct dates of evidence, and the
student history test needs a finished case with a score and a stored tutor
dialogue.  The one-off verification database only ever had one of each, so the
precondition was never met.

This script creates that dataset in a **throwaway** SQLite file under /tmp and
refuses to run anywhere else.  It uses the application's own code paths:

* ``app.seed_data.init_db``         — schema + teaching catalog + demo logins
* ``app.auth.hash_password``        — student/teacher credentials
* ``app.core.llm_config``           — the provider is removed from the process
* HTTP endpoints on a *separate* backend started against this file:
    - ``POST /api/sessions/start|answers|tutor|submit``   (case module)
    - ``POST /api/knowledge/{id}/quiz``                    (knowledge module)
    - ``POST /api/skills/{id}/sessions/start|submit``      (skill module)
    - ``POST /api/guidelines/{id}/pico``                   (guideline module)
    - ``POST /api/sp-sessions/start|submit``               (SP module)
    - ``POST /api/teacher/evidence/{id}/review``           (teacher confirmation)

The only rows written directly are the ``created_at`` timestamps of the evidence
events: the HTTP routes stamp ``datetime.utcnow()`` and a single run happens on a
single day, so the "three distinct dates" precondition cannot be produced through
the API.  Those UPDATE statements touch only ``learning_evidence_events`` and
``case_sessions`` of this throwaway file and are announced in the output.

Usage::

    # 1. build the database (backend must be importable; no server needed)
    uv run --python 3.11 --with-requirements backend/requirements.txt \\
        python scripts/grant/make_acceptance_dataset.py build \\
        --db /tmp/clinpath-accept/acceptance.db

    # 2. start a backend against it, then run the module submissions
    DATABASE_URL=sqlite:////tmp/clinpath-accept/acceptance.db \\
    CLINPATH_ENV=development JWT_SECRET=<throwaway> \\
        uv run ... uvicorn app.main:app --host 127.0.0.1 --port 8203 &
    uv run ... python scripts/grant/make_acceptance_dataset.py run \\
        --db /tmp/clinpath-accept/acceptance.db \\
        --base-url http://127.0.0.1:8203

    # or both at once, with --start-server (build, spawn, submit, report)
    uv run ... python scripts/grant/make_acceptance_dataset.py all \\
        --db /tmp/clinpath-accept/acceptance.db --port 8203

Exit codes: 0 success, 2 refused path, 3 bad state, 4 HTTP failure.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"

# Refuse anything that is not a throwaway file.  Both the production database and
# the operator's staging copy live outside /tmp, but the check is explicit about
# the known production path so the refusal reads clearly in a log.
FORBIDDEN_PATHS = {
    (BACKEND_DIR / "clinical_learning.db").resolve(),
    Path("/home/jcshi/workspace/clinical_learning_system/backend/clinical_learning.db"),
}

# Throwaway only: this password never exists outside the /tmp database the
# script creates, and it is not a credential for any deployed environment.
DEMO_PASSWORD = "acceptance-throwaway-not-a-credential"
TEACHER_USERNAME = "accept_teacher"
TEACHER_NO = "T-ACCEPT-001"

# The evidence the spec's preconditions ask for: three students, at least three
# learning modules, three distinct dates, and one finished case with a score.
# Each entry is (module, case|unit|skill|guideline|sp id) executed as a student.
PLAN = {
    1: [  # 李明 — the profile the demo-readiness spec opens from the student list
        ("case", 1),
        ("knowledge", 1),
        ("skill", 1),
    ],
    2: [  # 王佳
        ("case", 2),
        ("guideline", 1),
        ("sp", 1),
    ],
    3: [  # 陈晨
        ("knowledge", 2),
        ("skill", 2),
        ("case", 3),
    ],
}

CASE_ANSWERS = {
    "key_information": (
        "关键信息：反复发热、面部蝶形红斑、关节痛，ANA 阳性、补体下降、蛋白尿，"
        "提示需评估肾脏与血液系统器官受累。"
    ),
    "initial_diagnosis": (
        "初步诊断：系统性红斑狼疮。依据：年轻女性、光敏性皮疹、ANA 阳性、"
        "补体降低及蛋白尿，符合 2019 EULAR/ACR 分类标准。"
    ),
    "differential_diagnosis": (
        "鉴别诊断：需排除感染（EBV、结核）、成人 Still 病、HLH、淋巴瘤、"
        "ANCA 相关血管炎、MCTD 与抗磷脂综合征。"
    ),
    "examination": (
        "进一步检查：抗 dsDNA、补体 C3/C4 动态、24 小时尿蛋白定量、肾穿刺活检、"
        "血细胞减少评估、肺功能与心脏超声评估器官受累。"
    ),
    "treatment": (
        "治疗方案：羟氯喹为基础，激素联合免疫抑制剂（霉酚酸酯或环磷酰胺）诱导缓解；"
        "治疗前筛查乙肝、结核等感染；监测血常规、肝肾功能与不良反应，规律随访。"
    ),
}

KNOWLEDGE_ANSWERS = {
    1: [
        "重点评估肾脏受累，警惕狼疮肾炎，需查尿蛋白定量与肾活检。",
        "抗 dsDNA 抗体升高与补体 C3/C4 下降提示疾病活动。",
    ],
    2: [
        "发热伴皮疹需先排除感染，再考虑自身免疫病与肿瘤。",
        "补体下降、抗 dsDNA 阳性支持 SLE 活动。",
    ],
}

SKILL_STEPS = {
    1: ["手卫生并解释检查", "视诊关节肿胀和畸形", "触诊压痛和皮温", "评估主动和被动活动度", "记录受累关节分布"],
    2: ["核对适应证和禁忌证", "取得知情同意", "无菌铺巾和消毒", "定位穿刺点", "抽取关节液并送检", "压迫止血并告知注意事项"],
}

GUIDELINE_PICO = {
    "clinical_question": "SLE 合并蛋白尿的本科见习患者，诱导缓解方案如何选择？",
    "pico": "P：SLE 合并蛋白尿的年轻女性；I：激素联合霉酚酸酯；C：激素联合环磷酰胺；O：完全肾脏缓解率与感染风险。",
    "answer": "指南建议根据器官受累与生育需求个体化选择，霉酚酸酯在生育期女性中优先，需同时使用羟氯喹并监测感染。",
}

SP_DIAGNOSIS = (
    "诊断：系统性红斑狼疮。问诊要点：发热与皮疹的时间关系、光敏、口腔溃疡、关节痛、"
    "脱发、浆膜炎；需排除感染与肿瘤。"
)


class DatasetError(RuntimeError):
    """A step that should have succeeded did not; the caller must report it."""


def _guard_db_path(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise SystemExit(f"refused: --db must be an absolute path (got {raw!r})")
    resolved = path.resolve()
    if resolved in FORBIDDEN_PATHS or resolved.name == "clinical_learning.db":
        raise SystemExit(f"refused: {resolved} is the production database")
    try:
        resolved.relative_to("/tmp")
    except ValueError:
        raise SystemExit(
            f"refused: {resolved} is not under /tmp; this script only writes throwaway databases"
        ) from None
    return resolved


def _import_backend():
    """Import the application with a database URL this script owns."""

    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))
    # Never let an ambient provider key turn this into a real model run: the
    # dataset is rule-produced and must be labelled that way.
    for name in (
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "LLM_PROVIDER",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
    ):
        os.environ.pop(name, None)


def build_database(db_path: Path) -> dict:
    """Create the schema, the teaching catalog and the acceptance accounts."""

    if db_path.exists():
        raise SystemExit(f"refused: {db_path} already exists; delete it or pass a new path")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ.setdefault("CLINPATH_ENV", "development")
    os.environ["SEED_DEMO_STUDENT_ACCOUNTS"] = "true"
    os.environ["SEED_DEMO_STUDENT_PASSWORD"] = DEMO_PASSWORD

    _import_backend()

    from app.auth import hash_password
    from app.database import SessionLocal
    from app.models import Student, Teacher, User

    # Imported only after DATABASE_URL points at this throwaway file.
    from app.seed_data import init_db

    init_db(reset=False)

    db = SessionLocal()
    try:
        teacher = db.query(Teacher).filter(Teacher.teacher_no == TEACHER_NO).first()
        if teacher is None:
            teacher = Teacher(name="验收教师", teacher_no=TEACHER_NO, department="风湿免疫科")
            db.add(teacher)
            db.flush()
        if db.query(User).filter(User.username == TEACHER_USERNAME).first() is None:
            db.add(
                User(
                    username=TEACHER_USERNAME,
                    password_hash=hash_password(DEMO_PASSWORD),
                    role="teacher",
                    teacher_id=teacher.id,
                )
            )
        db.commit()
        students = db.query(Student).all()
        return {
            "students": [(s.id, s.name) for s in students],
            "teacher": TEACHER_USERNAME,
            "password": DEMO_PASSWORD,
        }
    finally:
        db.close()


class Client:
    """Minimal cookie-keeping JSON client; no third-party dependency."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookie: str | None = None

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                set_cookie = response.headers.get("set-cookie")
                if set_cookie:
                    self.cookie = set_cookie.split(";", 1)[0]
                body = response.read().decode()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()
            raise DatasetError(f"{method} {path} -> {exc.code}: {detail[:400]}") from exc

    def login(self, username: str, password: str) -> None:
        self.request("POST", "/api/auth/login", {"username": username, "password": password})


def _submit_case(client: Client, case_id: int) -> dict:
    session = client.request("POST", "/api/sessions/start", {"case_id": case_id})
    session_id = session["session_id"]
    for step, text in CASE_ANSWERS.items():
        client.request(
            "POST",
            f"/api/sessions/{session_id}/answers",
            {"step": step, "answer_text": text},
        )
    # One tutor turn on the first step: the history page's review panel expects
    # a stored dialogue, not just answers.
    client.request(
        "POST",
        f"/api/sessions/{session_id}/tutor",
        {"step": "key_information", "message": "因为患者发热伴皮疹和ANA阳性，我优先考虑自身免疫病，但需要先排除感染。"},
    )
    result = client.request("POST", f"/api/sessions/{session_id}/submit")
    summary = result.get("summary", {})
    return {
        "module": "case",
        "session_id": session_id,
        "score": summary.get("total_score"),
        "evaluation_mode": summary.get("evaluation_mode"),
        "degraded": summary.get("degraded"),
    }


def _submit_knowledge(client: Client, unit_id: int) -> dict:
    result = client.request(
        "POST",
        f"/api/knowledge/{unit_id}/quiz",
        {"answers": KNOWLEDGE_ANSWERS[unit_id]},
    )
    return {"module": "knowledge", "score": result["quiz_score"]}


def _submit_skill(client: Client, skill_id: int) -> dict:
    session = client.request("POST", f"/api/skills/{skill_id}/sessions/start", {})
    result = client.request(
        "POST",
        f"/api/skill-sessions/{session['id']}/submit",
        {"submitted_steps": SKILL_STEPS[skill_id]},
    )
    return {"module": "skill", "session_id": session["id"], "score": result["score"]}


def _submit_guideline(client: Client, guideline_id: int) -> dict:
    result = client.request("POST", f"/api/guidelines/{guideline_id}/pico", GUIDELINE_PICO)
    return {"module": "guideline", "score": result["score"]}


def _submit_sp(client: Client, sp_case_id: int) -> dict:
    session = client.request("POST", "/api/sp-sessions/start", {"sp_case_id": sp_case_id})
    result = client.request(
        "POST",
        f"/api/sp-sessions/{session['session_id']}/submit",
        {"diagnosis_summary": SP_DIAGNOSIS},
    )
    return {"module": "sp", "session_id": session["session_id"], "score": result["total_score"]}


SUBMITTERS = {
    "case": _submit_case,
    "knowledge": _submit_knowledge,
    "skill": _submit_skill,
    "guideline": _submit_guideline,
    "sp": _submit_sp,
}


def run_learning(base_url: str, db_path: Path) -> list[dict]:
    """Drive every module through its HTTP route, one login per student."""

    # DATABASE_URL is read when app.database is imported, so set it first.
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    _import_backend()

    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        student_users = {
            user.student_id: user.username
            for user in db.query(User).filter(User.role == "student").all()
        }
    finally:
        db.close()

    created: list[dict] = []
    for student_id, actions in PLAN.items():
        username = student_users.get(student_id)
        if not username:
            raise DatasetError(f"student {student_id} has no login; build the database first")
        client = Client(base_url)
        client.login(username, DEMO_PASSWORD)
        for module, item_id in actions:
            try:
                row = SUBMITTERS[module](client, item_id)
            except DatasetError as exc:
                raise DatasetError(f"student {student_id} / {module} {item_id}: {exc}") from exc
            row.update({"student_id": student_id, "username": username, "item_id": item_id})
            created.append(row)
            print(f"  student {student_id} ({username}) {module} {item_id} -> score {row['score']}")
    return created


def spread_dates(db_path: Path) -> dict:
    """Give the evidence events three distinct calendar dates.

    This is the one part the HTTP API cannot do: every route stamps
    ``datetime.utcnow()``, so a single acceptance run lands on a single day.  The
    UPDATEs below touch only this throwaway file and only timestamp columns.
    """

    import sqlite3

    connection = sqlite3.connect(db_path)
    try:
        rows = connection.execute(
            "SELECT id, student_id, module_type FROM learning_evidence_events ORDER BY id"
        ).fetchall()
        if len(rows) < 3:
            raise DatasetError(f"expected at least 3 evidence events, found {len(rows)}")
        base = datetime(2026, 10, 14, 9, 0, 0)  # three days before the acceptance run
        offsets = {1: timedelta(days=0), 2: timedelta(days=1), 3: timedelta(days=2)}
        touched = []
        for event_id, student_id, module_type in rows:
            stamp = base + offsets.get(student_id, timedelta(days=2)) + timedelta(hours=event_id % 8)
            connection.execute(
                "UPDATE learning_evidence_events SET created_at = ? WHERE id = ?",
                (stamp.isoformat(sep=" "), event_id),
            )
            touched.append({"id": event_id, "student_id": student_id, "module": module_type, "created_at": stamp.isoformat(sep=" ")})
        # Keep each case session's own timestamps consistent with its evidence.
        connection.execute(
            "UPDATE case_sessions SET started_at = '2026-10-14 08:45:00', "
            "completed_at = '2026-10-14 09:00:00' WHERE id IN "
            "(SELECT session_id FROM learning_evidence_events WHERE module_type = 'case')"
        )
        connection.commit()
        return {"events": touched}
    finally:
        connection.close()


def report(db_path: Path) -> dict:
    """Prove the preconditions the acceptance spec asserts."""

    import sqlite3

    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        students = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        modules = connection.execute(
            "SELECT COUNT(DISTINCT module_type) FROM learning_evidence_events"
        ).fetchone()[0]
        dates = connection.execute(
            "SELECT COUNT(DISTINCT substr(created_at, 1, 10)) FROM learning_evidence_events"
        ).fetchone()[0]
        scored = connection.execute(
            "SELECT COUNT(*) FROM case_sessions s JOIN scores sc ON sc.session_id = s.id "
            "WHERE s.status = 'completed'"
        ).fetchone()[0]
        modes = connection.execute(
            "SELECT evaluation_mode, COUNT(*) FROM scores GROUP BY evaluation_mode"
        ).fetchall()
        labels = connection.execute(
            "SELECT module_type, COUNT(*) FROM learning_evidence_events GROUP BY module_type ORDER BY module_type"
        ).fetchall()
        return {
            "students": students,
            "modules": modules,
            "module_counts": dict(labels),
            "dates": dates,
            "completed_scored_cases": scored,
            "evaluation_modes": dict(modes),
        }
    finally:
        connection.close()


def start_server(db_path: Path, port: int, log_path: Path) -> subprocess.Popen:
    """Start an isolated backend on `port`; the caller must stop it."""

    env = dict(os.environ)
    for name in list(env):
        if name.startswith(("LLM_", "DEEPSEEK_", "OPENAI_")):
            env.pop(name)
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "CLINPATH_ENV": "development",
            "JWT_SECRET": "acceptance-throwaway-secret",
            "RATE_LIMIT_LOGIN_PER_HOUR": "1000",
            "RATE_LIMIT_COACH_PER_HOUR": "1000",
            "RATE_LIMIT_SUBMIT_PER_HOUR": "1000",
            "SEED_DEMO_STUDENT_PASSWORD": DEMO_PASSWORD,
        }
    )
    log = log_path.open("wb")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=BACKEND_DIR,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            with urllib.request.urlopen(base + "/api/health", timeout=2):
                return process
        except OSError:
            # Connection refused while uvicorn is still importing the app.
            time.sleep(0.5)
    process.terminate()
    raise DatasetError(f"backend on {base} did not become healthy; see {log_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("command", choices=["build", "run", "spread", "report", "all"])
    parser.add_argument("--db", required=True, help="throwaway SQLite file under /tmp")
    parser.add_argument("--base-url", help="existing isolated backend (for 'run')")
    parser.add_argument("--port", type=int, default=8203, help="port for 'all'")
    parser.add_argument("--log", help="server log for 'all' (default: next to the db)")
    args = parser.parse_args()

    db_path = _guard_db_path(args.db)

    if args.command == "build":
        summary = build_database(db_path)
        print(f"built {db_path}")
        print(f"  students: {summary['students']}")
        print(f"  teacher:  {summary['teacher']} (throwaway password in the /tmp DB only)")
        return 0

    if args.command == "spread":
        print(json.dumps(spread_dates(db_path), ensure_ascii=False, indent=2))
        return 0

    if args.command == "report":
        print(json.dumps(report(db_path), ensure_ascii=False, indent=2))
        return 0

    if args.command == "run":
        if not args.base_url:
            raise SystemExit("'run' needs --base-url for the isolated backend")
        created = run_learning(args.base_url, db_path)
        print(f"{len(created)} learning events submitted through the HTTP routes")
        return 0

    # 'all': build, spawn, submit, spread, report, stop.
    log_path = Path(args.log) if args.log else db_path.with_suffix(".log")
    build_database(db_path)
    process = start_server(db_path, args.port, log_path)
    try:
        run_learning(f"http://127.0.0.1:{args.port}", db_path)
    finally:
        process.terminate()
        process.wait(timeout=15)
    spread_dates(db_path)
    print(json.dumps(report(db_path), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DatasetError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(4)
