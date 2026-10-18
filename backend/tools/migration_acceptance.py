#!/usr/bin/env python3
"""R8.3 migration acceptance: upgrade / downgrade / re-upgrade on an isolated database.

This tool never migrates anything by itself. It seeds a small *training* fixture into
an already-migrated throwaway database, dumps every table, and compares two dumps, so
the upgrade -> downgrade -> upgrade cycle can be shown to leave pre-existing training
rows byte-identical. It refuses to run against the repository's production database
path unless ``--i-mean-it`` is passed.

    cd backend
    uv run --python 3.11 --with-requirements requirements.txt python tools/migration_acceptance.py seed --db /tmp/x/acc.db
    ...  tools/migration_acceptance.py tables --db /tmp/x/acc.db
    ...  tools/migration_acceptance.py dump   --db /tmp/x/acc.db --out /tmp/x/after_head.json
    ...  tools/migration_acceptance.py compare --before /tmp/x/before.json --after /tmp/x/after_head.json

``dump`` reads with the sqlite3 standard library only, so it works at any schema
revision (including ones older than the ORM definitions). ``seed`` uses the ORM and is
the one command that writes.
"""

import argparse
import json
import sys
from contextlib import closing
from pathlib import Path

REPO_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_BACKEND))

PRODUCTION_DB = REPO_BACKEND / "clinical_learning.db"
SKIP_TABLES = ("alembic_version",)
# Training-domain tables that must survive a schema cycle untouched. The fixture
# below writes exactly these; assessment_* / study_* / research_* tables are expected
# to appear and disappear with the migrations.
TRAINING_TABLES = ("teachers", "students", "users", "competency_profiles", "cases", "case_sessions",
                   "student_answers", "scores", "learning_recommendations", "tutor_turns", "ai_messages",
                   "ai_invocations", "learning_evidence_events", "teacher_score_reviews")


def _guard(db_path: Path, i_mean_it: bool) -> None:
    if db_path.resolve() == PRODUCTION_DB.resolve() and not i_mean_it:
        raise SystemExit(f"refusing to touch the production database {db_path}; use an isolated copy")


def _table_names(conn) -> list[str]:
    rows = conn.execute("select name from sqlite_master where type='table' order by name").fetchall()
    return [r[0] for r in rows if not r[0].startswith("sqlite_") and r[0] not in SKIP_TABLES]


def cmd_tables(args) -> int:
    db_path = Path(args.db)
    _guard(db_path, args.i_mean_it)
    with closing(_connect(db_path)) as conn:
        for name in _table_names(conn):
            n = conn.execute(f'select count(*) from "{name}"').fetchone()[0]
            cols = [r[1] for r in conn.execute(f'pragma table_info("{name}")').fetchall()]
            print(f"{name}\trows={n}\tcolumns={len(cols)}")
            if args.columns:
                print("    " + ", ".join(cols))
    return 0


def cmd_dump(args) -> int:
    db_path = Path(args.db)
    _guard(db_path, args.i_mean_it)
    out = {"database": str(db_path), "tables": {}}
    with closing(_connect(db_path)) as conn:
        try:
            out["alembic_revision"] = conn.execute("select version_num from alembic_version").fetchone()[0]
        except Exception:
            out["alembic_revision"] = None
        for name in _table_names(conn):
            cols = [r[1] for r in conn.execute(f'pragma table_info("{name}")').fetchall()]
            rows = conn.execute(f'select * from "{name}" order by rowid').fetchall()
            out["tables"][name] = {
                "columns": cols,
                "count": len(rows),
                "rows": [[_plain(v) for v in row] for row in rows],
            }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"dumped {len(out['tables'])} tables (revision {out['alembic_revision']}) to {args.out}")
    return 0


def cmd_compare(args) -> int:
    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))
    problems = []
    for name in sorted(set(before["tables"]) | set(after["tables"])):
        b, a = before["tables"].get(name), after["tables"].get(name)
        if b is None:
            print(f"ADDED   {name} ({a['count']} rows)")
            continue
        if a is None:
            print(f"DROPPED {name} ({b['count']} rows)")
            continue
        if b["columns"] != a["columns"]:
            problems.append(f"{name}: columns changed")
            print(f"CHANGED {name}: columns {b['columns']} -> {a['columns']}")
        if b["count"] != a["count"]:
            problems.append(f"{name}: {b['count']} -> {a['count']} rows")
            print(f"CHANGED {name}: rows {b['count']} -> {a['count']}")
        elif b["rows"] != a["rows"]:
            problems.append(f"{name}: same count, different content")
            print(f"CHANGED {name}: same row count, different content")
        else:
            print(f"same    {name} ({b['count']} rows)")
    wanted = [t for t in TRAINING_TABLES if t in before["tables"] and t in after["tables"]]
    identical = [t for t in wanted if before["tables"][t] == after["tables"][t]]
    print(f"\ntraining tables seeded and compared: {len(wanted)}; byte-identical: {len(identical)}")
    if len(identical) != len(wanted):
        problems.append("training tables were not all identical")
    if problems:
        print("NOT EQUIVALENT:\n  " + "\n  ".join(problems))
        return 1
    print(f"tables identical: {len(after['tables'])}, revision "
          f"{before['alembic_revision']} -> {after['alembic_revision']}")
    return 0


def cmd_schema(args) -> int:
    """Every CREATE statement, normalised, so a migrated database can be compared with a fresh install."""
    db_path = Path(args.db)
    _guard(db_path, args.i_mean_it)
    out = {}
    with closing(_connect(db_path)) as conn:
        rows = conn.execute("select type, name, tbl_name, sql from sqlite_master where sql is not null "
                            "order by type, name").fetchall()
        for kind, name, tbl, sql in rows:
            if name.startswith("sqlite_") or tbl == "alembic_version":
                continue
            out[f"{kind}:{name}"] = " ".join(sql.split())
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {len(out)} schema objects to {args.out}")
    return 0


def cmd_seed(args) -> int:
    """Write the training fixture through the ORM (the app's own model definitions)."""
    db_path = Path(args.db)
    _guard(db_path, args.i_mean_it)
    import os
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    from datetime import datetime

    from app.database import SessionLocal
    from app.models import (
        AIInvocation, Case, CaseSession, CompetencyProfile, LearningEvidenceEvent, LearningRecommendation,
        Score, Student, StudentAnswer, Teacher, TeacherScoreReview, TutorTurn, User,
    )

    db = SessionLocal()
    try:
        teacher = Teacher(name="迁移验收测试教师", teacher_no="MIG-T-001", department="TEST")
        db.add(teacher)
        db.flush()
        db.add(User(username="mig_teacher", password_hash="x", role="teacher", teacher_id=teacher.id))
        student = Student(name="迁移验收测试学生", student_no="MIG-S-0001", class_name="TEST",
                          current_stage="阶段一")
        db.add(student)
        db.flush()
        db.add(User(username="mig_student", password_hash="x", role="student", student_id=student.id))
        db.add(CompetencyProfile(student_id=student.id, medical_knowledge=61, key_information=62,
                                 differential_diagnosis=63, evidence_integration=64, clinical_decision=65,
                                 evidence_based_medicine=66, learning_engagement=67))
        case = Case(title="迁移验收用例", disease_category="SLE", difficulty="基础",
                    learning_objectives="[]", chief_complaint="c", history="h", physical_exam="p",
                    lab_results="l", imaging="i", standard_diagnosis="HIDDEN-DX", differential_diagnosis="[]",
                    treatment_plan="HIDDEN-PLAN", rubric="{}")
        db.add(case)
        db.flush()
        session = CaseSession(student_id=student.id, case_id=case.id, status="completed",
                              started_at=datetime(2026, 10, 1, 8, 0, 0), completed_at=datetime(2026, 10, 1, 8, 40, 0))
        db.add(session)
        db.flush()
        db.add(StudentAnswer(session_id=session.id, step="key_information", answer_text="迁移验收作答"))
        score = Score(session_id=session.id, total_score=77.5, medical_knowledge=70, key_information=72,
                      differential_diagnosis=74, evidence_integration=76, clinical_decision=80,
                      evidence_based_medicine=82, feedback="f", strengths="s", weaknesses="w",
                      evaluation_mode="rule_fallback", degraded=True)
        db.add(score)
        db.add(TutorTurn(session_id=session.id, step="key_information", turn_index=0, role="tutor",
                         message="追问", tutor_state_json="{}"))
        db.add(AIInvocation(task_type="case_evaluation", session_id=session.id, student_id=student.id,
                            calls=1, success=True, fallback_used=True, latency_ms=1234))
        db.add(LearningRecommendation(student_id=student.id, recommended_case_id=case.id,
                                      recommendation_reason="r", pathway_stage="巩固"))
        db.flush()
        evidence = LearningEvidenceEvent(student_id=student.id, module_type="case", module_id=case.id,
                                         session_id=session.id, event_type="case_scored",
                                         source_table="scores", source_id=score.id, score=77.5,
                                         competency_updates_json="{}", evidence_payload_json="{}")
        db.add(evidence)
        db.flush()
        db.add(TeacherScoreReview(evidence_event_id=evidence.id, reviewer_user_id=1, ai_score=77.5,
                                  baseline_score=77.5, baseline_source="rule_fallback", teacher_score=78.0,
                                  comment="迁移验收复核", agreement_delta=0.5,
                                  confirmed_dimensions_json="{}"))
        db.commit()
        print("seeded the training fixture rows")
    finally:
        db.close()
    return 0


def _connect(db_path: Path):
    import sqlite3
    return sqlite3.connect(str(db_path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--i-mean-it", action="store_true", help="allow the repository's production database path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("tables", help="list tables with row counts (read-only)")
    p.add_argument("--db", required=True)
    p.add_argument("--columns", action="store_true", help="also print every column name")
    p.set_defaults(func=cmd_tables)

    p = sub.add_parser("dump", help="dump every table to JSON (read-only)")
    p.add_argument("--db", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_dump)

    p = sub.add_parser("seed", help="write the training fixture through the ORM")
    p.add_argument("--db", required=True)
    p.set_defaults(func=cmd_seed)

    p = sub.add_parser("schema", help="write every CREATE statement to JSON (read-only)")
    p.add_argument("--db", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_schema)

    p = sub.add_parser("compare", help="compare two dumps; exit 1 on any difference")
    p.add_argument("--before", required=True)
    p.add_argument("--after", required=True)
    p.set_defaults(func=cmd_compare)

    args = parser.parse_args()
    return args.func(args)


def _plain(value):
    if value is None or isinstance(value, (int, float, str)):
        return value
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
