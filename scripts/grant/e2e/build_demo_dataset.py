#!/usr/bin/env python3
"""Build the demo teaching dataset for the ISOLATED acceptance stack, offline.

Why this exists
---------------
``frontend/tests/e2e/demo-readiness.spec.ts`` asserts what a clinical teacher
reads on the demo surfaces: a learner's growth-trend chart, an anonymised
research export that describes a class rather than one test run, and a learner's
own case history. A freshly seeded stack has none of those records (and only
three of the four demo students), so those assertions fail there even though the
product and the read paths behind them are correct -- the backend proves each one
offline with fixed data (``backend/tests/test_presentation_surfaces.py``).

``scripts/prepare_presentation_data.py`` is the tool that builds this dataset for
the *real* demo database. It deliberately refuses to run without a configured
model, because a presentation dataset scored by the rule engine would
misrepresent what the platform does when a model is available.

This script is the acceptance-stack counterpart, built on the opposite premise:
the acceptance stack is **keyless by construction** (``stack.build_env`` blanks
every provider key). Therefore it

* reuses the *same* plan and the *same* route functions as the operator tool, so
  there is one definition of the demo timeline rather than two;
* refuses to run when a model provider **is** configured, so a rule-fallback
  dataset can never be written where an AI dataset was intended;
* refuses any database outside ``/tmp`` and never reads operator secrets
  (``CLINPATH_SKIP_OPERATOR_ENV=1``);
* records ``rule_fallback`` provenance in its manifest instead of calling it AI.

Run it **before** ``build_fixture.py``: the operator tool's audit refuses to
touch a database that holds students it cannot classify as demo data, and the 7x7
fixture is exactly 49 such students.

    uv run --python 3.11 --with-requirements backend/requirements.txt \\
        python scripts/grant/e2e/build_demo_dataset.py \\
        --database-url sqlite:////tmp/clinpath-e2e/accept.db \\
        --manifest /tmp/clinpath-e2e/demo_dataset.json

The dataset is synthetic software-acceptance data. It is not teaching effect, and
the manifest it writes says so.
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import os
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BACKEND = REPO / "backend"
PLAN_SCRIPT = REPO / "scripts" / "prepare_presentation_data.py"

sys.path.insert(0, str(HERE))
import guard  # noqa: E402 - the same isolation rules the stack uses

# The plan's catalog references (knowledge unit / skill / case / guideline /
# SP case) are calibrated against the long-lived demo catalogue. A freshly
# seeded acceptance database carries a smaller catalogue, so references that do
# not resolve are substituted deterministically instead of inventing teaching
# content. See ``resolve_activities``.
CATALOG_MODEL = {
    "knowledge": "KnowledgeUnit",
    "skill": "ClinicalSkill",
    "case": "Case",
    "guideline": "GuidelineDocument",
    "sp": "SPCase",
}
DEFAULT_STUDENT_PASSWORD = "test-student-pw"


def refuse(message: str) -> "SystemExit":
    return SystemExit(f"refusing to build the demo dataset: {message}")


def require_keyless() -> None:
    """A rule-fallback dataset may only be written where no model is available.

    The inverse of the operator tool's guard: it stops without a model, this one
    stops *with* one. Together they make it impossible for a run to be silent
    about which engine produced a demo score.
    """

    for name in ("LLM_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        if os.environ.get(name, "").strip():
            raise refuse(f"{name} is set; this stack must be keyless so every score is provenance-labelled")

    from app.core import llm_config

    if llm_config.LLM_CONFIGURED:
        raise refuse(
            f"a model provider is configured ({llm_config.LLM_PROVIDER}/{llm_config.LLM_MODEL}); "
            "use scripts/prepare_presentation_data.py for a real-AI presentation dataset"
        )


def load_plan():
    """Import the shared plan with the operator's own environment walled off.

    The plan module reads ``~/.config/clinpath/backend.env`` at import time unless
    ``CLINPATH_SKIP_OPERATOR_ENV=1``. It must never be read here: those are the
    production keys, and this process writes to a throwaway database.
    """

    os.environ["CLINPATH_SKIP_OPERATOR_ENV"] = "1"
    name = "prepare_presentation_data"
    spec = importlib.util.spec_from_file_location(name, PLAN_SCRIPT)
    if spec is None or spec.loader is None:  # pragma: no cover - the file is in the repo
        raise SystemExit(f"cannot load the demo plan from {PLAN_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    # Register before executing: ``@dataclass`` resolves annotations through
    # ``sys.modules[cls.__module__]``, which an unregistered module does not have.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def bind_database(database_url: str) -> None:
    """Point the app at the throwaway database *before* any app import.

    ``app.database`` resolves ``DATABASE_URL`` once, at import. Any lazily-opened
    session would otherwise fall back to ``sqlite:///./clinical_learning.db``,
    which inside ``backend/`` is the production database.
    """

    path = Path(database_url.replace("sqlite:///", "", 1)).resolve()
    os.environ["DATABASE_URL"] = database_url
    os.environ["CLINPATH_DB_PATH"] = str(path)
    sys.path.insert(0, str(BACKEND))

    from app.database import DATABASE_URL as resolved

    if resolved != database_url:
        raise refuse(f"the app resolved its database to {resolved!r}, not {database_url!r}")


def available_catalog(db) -> dict[str, list[int]]:
    from app import models

    return {
        kind: sorted(row_id for (row_id,) in db.query(getattr(models, model_name).id).all())
        for kind, model_name in CATALOG_MODEL.items()
    }


def resolve_activities(db, activities) -> tuple[tuple, list[dict]]:
    """Map the plan's catalog references onto the catalogue this database has.

    An exact hit is always used, so against the real demo database this is the
    identity. A missing reference (the acceptance catalogue is smaller) is
    replaced by a deterministic pick from the ids that do exist -- never by
    authoring a new case, which would need real teacher review.
    """

    catalog = available_catalog(db)
    resolved, substitutions = [], []
    for activity in activities:
        ids = catalog[activity.kind]
        if not ids:
            raise refuse(f"no {activity.kind} rows exist, so the plan cannot be replayed")
        if activity.catalog_id in ids:
            resolved.append(activity)
            continue
        substitute = ids[(activity.catalog_id - 1) % len(ids)]
        substitutions.append(
            {"student_no": activity.student_no, "kind": activity.kind, "when": activity.when,
             "requested": activity.catalog_id, "substituted": substitute, "available": len(ids),
             "note": activity.note}
        )
        resolved.append(dataclasses.replace(activity, catalog_id=substitute))
    return tuple(resolved), substitutions


def ensure_demo_student(db, entry, *, password: str) -> dict:
    """Create the demo student the seed does not know about yet (赵敏).

    The seed creates three demo students; the plan describes four. The fourth is
    a demo student in the real database too, so the acceptance stack needs one.
    Creating it here is the only direct write this script does, and it is limited
    to an account that carries no learning record and no study enrolment.
    """

    from app.auth import hash_password
    from app.models import CompetencyProfile, Student, User
    from app.services.recommendation_service import determine_pathway_stage

    wanted = {entry.student_no}
    if entry.display_student_no:
        wanted.add(entry.display_student_no)
    student = db.query(Student).filter(Student.student_no.in_(wanted)).first()
    created = False
    if student is None:
        student = Student(
            name=entry.name,
            student_no=entry.display_student_no or entry.student_no,
            class_name=entry.class_name,
            current_stage=determine_pathway_stage(entry.baseline),
        )
        db.add(student)
        db.flush()
        created = True
    elif student.name != entry.name:
        raise refuse(
            f"student {student.student_no!r} is named {student.name!r}, not {entry.name!r}; "
            "this database does not hold the demo cohort"
        )

    if student.competency_profile is None:
        db.add(CompetencyProfile(student_id=student.id, **{key: float(value) for key, value in entry.baseline.items()}))
        db.flush()

    login = f"student{student.id}"
    user = db.query(User).filter(User.role == "student", User.student_id == student.id).first()
    if user is None:
        db.add(User(username=login, password_hash=hash_password(password), role="student", student_id=student.id))
        db.flush()
    db.commit()
    return {"student_id": student.id, "name": entry.name, "student_no": student.student_no,
            "login": user.username if user else login, "created": created}


def verify_rule_fallback_only(db, student_ids: list[int]) -> dict:
    """Read the stored provenance of the replay back out of the database.

    ``require_keyless`` already makes a provider call impossible. This is the
    second half of the claim: what the *database* says. The case scores are the
    student-visible provenance (the history page and the CSV both show it), so a
    single non-fallback score means the run must not be recorded as synthetic
    rule output.
    """

    from app.models import CaseSession, Score

    scores = (
        db.query(Score)
        .join(CaseSession, Score.session_id == CaseSession.id)
        .filter(CaseSession.student_id.in_(student_ids))
        .all()
    )
    by_mode: dict[str, int] = {}
    for score in scores:
        by_mode[score.evaluation_mode] = by_mode.get(score.evaluation_mode, 0) + 1
    not_fallback = [
        {"score_id": score.id, "evaluation_mode": score.evaluation_mode,
         "provider": score.provider, "model": score.model}
        for score in scores
        if score.evaluation_mode != "rule_fallback" or score.provider or score.model
    ]
    if not_fallback:
        raise refuse(f"these case scores are not rule fallbacks: {json.dumps(not_fallback, ensure_ascii=False)}")
    return {"case_scores": len(scores), "evaluation_modes": by_mode,
            "student_visible_label": "规则降级评价（AI 当前不可用）"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database-url", required=True, help="the throwaway SQLite the stack is running on")
    parser.add_argument("--api", default="http://127.0.0.1:8400", help="isolated backend base URL (loopback only)")
    parser.add_argument("--student-password", default=DEFAULT_STUDENT_PASSWORD,
                        help="password for a demo student login this script has to create")
    parser.add_argument("--manifest", default=None, help="write the provenance manifest here as JSON")
    args = parser.parse_args()

    database_url = guard.check_database_url(args.database_url)
    host = urllib.parse.urlsplit(args.api).hostname
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise refuse(f"--api must be loopback, got {args.api!r}")
    if os.environ.get("CLINPATH_ENV") == "production":
        raise refuse("CLINPATH_ENV=production; this dataset is for a disposable stack only")

    # The plan module defaults CLINPATH_ENV to "production" (it is written for the
    # operator's real database). Pin the environment the running stack itself uses
    # before importing it: app.auth refuses to import in production without a JWT
    # secret, and the acceptance stack deliberately has none of its own.
    os.environ["CLINPATH_ENV"] = "development"

    plan = load_plan()
    bind_database(database_url)
    require_keyless()

    from app.database import SessionLocal

    students: list[dict] = []
    db = SessionLocal()
    try:
        print(f"数据库：{database_url}（一次性，keyless）")
        for entry in plan.DEMO_STUDENTS:
            students.append(ensure_demo_student(db, entry, password=args.student_password))
        for row in students:
            print(f"  演示学生 {row['name']}（{row['student_no']}）登录 {row['login']}"
                  f"{' · 本次创建' if row['created'] else ' · 已存在'}")

        activities, substitutions = resolve_activities(db, plan.ACTIVITIES)
        if substitutions:
            print("== 目录替换（验收库目录较小，未新增任何教学病例） ==")
            for row in substitutions:
                print(f"  {row['when']} {row['kind']} #{row['requested']} -> #{row['substituted']}"
                      f"（可用 {row['available']} 项；{row['note']}）")
    finally:
        db.close()

    # ``apply`` iterates the plan module's ACTIVITIES global and preflights every
    # catalog id, so the resolved plan replaces it for this run only. Deliberate
    # attribute assignment: the operator tool's own plan stays untouched.
    setattr(plan, "ACTIVITIES", activities)
    outcome = plan.apply(SessionLocal, skip_enrichment=True)

    student_ids = [row["student_id"] for row in students]
    db = SessionLocal()
    try:
        provenance = verify_rule_fallback_only(db, student_ids)
    finally:
        db.close()

    manifest = {
        "label": "SYNTHETIC / SIMULATED_NOT_HUMAN — acceptance demo dataset, not real students",
        "provenance": "rule_fallback",
        "model_calls": 0,
        "reason": "the acceptance stack runs with no provider key, so every score is the rule engine's",
        "database_url": database_url,
        "plan_source": str(PLAN_SCRIPT.relative_to(REPO)),
        "activities_replayed": outcome["activities"],
        # The plan's own field name is about the *path*, not the engine: these are
        # the activities whose code can call a model at all. Keyless they all fall
        # back, which ``provenance`` above and ``scores`` below are the evidence for.
        "activities_on_an_ai_capable_path": outcome["provider_activities"],
        "activities_that_reported_degraded": outcome["degraded_activities"],
        "scores": provenance,
        "catalog_substitutions": substitutions,
        "demo_students": students,
        "pathway_stages": outcome["stages"],
        "final_counts": outcome["final"],
    }
    if args.manifest:
        Path(args.manifest).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    print(f"\n== 完成 == 重放 {outcome['activities']} 次学习活动；"
          f"病例评分 {provenance['case_scores']} 份，来源 {provenance['evaluation_modes']}")
    print(f"   学生可见标注：{provenance['student_visible_label']}；真实模型调用 0 次")
    print(f"   数据来源标注：{manifest['label']}")
    if args.manifest:
        print(f"   清单：{args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
