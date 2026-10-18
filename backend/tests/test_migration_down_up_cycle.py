"""R8.3: an upgrade -> downgrade -> upgrade cycle converges on the fresh-install schema.

The cycle runs in a subprocess against a throwaway SQLite file, exactly as an operator
would. It is deliberately *not* run in-process: ``app.database`` binds its engine to
``DATABASE_URL`` at import time, and a mistake there would migrate the developer's real
database. The test seeds plain training rows before the assessment revisions and checks
that they survive byte-for-byte, that the assessment tables come and go with the
migrations, and that the re-upgraded schema equals a fresh ``create_all`` install.
"""
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
BEFORE_ASSESSMENT = "20261018_07"
HEAD = "20261018_09"
ASSESSMENT_TABLES = ("assessment_forms", "assessment_form_reviews", "assessment_form_reviewers",
                     "assessment_sittings", "assessment_answers", "assessment_reviews", "assessment_events",
                     "assessment_adjudications", "assessment_final_scores", "assessment_dataset_locks",
                     "assessment_audit_log", "research_codes", "study_cohorts", "study_enrollments",
                     "study_allocations")
TRAINING_ROWS = {
    "students": "(1, '迁移验收学生', 'MIG-S-0001', 'TEST', '阶段一')",
    "competency_profiles": ("(1, 1, 61, 75, 62, 63, 64, 65, 66, 75, 75, 67, '2026-10-01 00:00:00')"),
    "cases": ("(1, '迁移验收用例', 'SLE', '基础', '[]', 'c', 'h', 'p', 'l', 'i', 'HIDDEN-DX', '[]', "
              "'HIDDEN-PLAN', '{}')"),
    "case_sessions": "(1, 1, 1, 'completed', '2026-10-01 08:00:00', '2026-10-01 08:40:00')",
    "scores": ("(1, 1, 77.5, 70, 72, 74, 76, 80, 82, 'f', 's', 'w', 'rule_fallback', NULL, NULL, "
               "'case-evaluation-v1', 'case-rubric-v1', 'hybrid-v1', 77.5, NULL, 0, '{}', NULL, NULL, "
               "'2026-10-01 08:41:00')"),
}
COLUMNS = {
    "students": "id, name, student_no, class_name, current_stage",
    "competency_profiles": ("id, student_id, medical_knowledge, skill_operation, key_information, "
                            "differential_diagnosis, evidence_integration, clinical_decision, "
                            "evidence_based_medicine, communication, humanistic_care, learning_engagement, updated_at"),
    "cases": ("id, title, disease_category, difficulty, learning_objectives, chief_complaint, history, "
              "physical_exam, lab_results, imaging, standard_diagnosis, differential_diagnosis, treatment_plan, rubric"),
    "case_sessions": "id, student_id, case_id, status, started_at, completed_at",
    "scores": ("id, session_id, total_score, medical_knowledge, key_information, differential_diagnosis, "
               "evidence_integration, clinical_decision, evidence_based_medicine, feedback, strengths, weaknesses, "
               "evaluation_mode, provider, model, prompt_version, rubric_version, evaluator_version, rule_score, "
               "ai_score, degraded, evaluation_detail_json, teacher_confirmed_score, teacher_override_reason, created_at"),
}


def alembic(db, *args):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}", "CLINPATH_ENV": "development"}
    done = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env,
                          capture_output=True, text=True, timeout=180)
    assert done.returncode == 0, f"alembic {' '.join(args)} failed:\n{done.stdout[-2000:]}\n{done.stderr[-2000:]}"
    return done


def connect(db):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def tables(conn):
    return {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}


def schema(conn, names):
    out = {}
    for (name, sql) in conn.execute("select name, sql from sqlite_master where sql is not null"):
        if name in names:
            out[name] = " ".join(sql.split())
    return out


def training_dump(conn):
    return {t: [tuple(r) for r in conn.execute(f'select {COLUMNS[t]} from "{t}" order by rowid')]
            for t in TRAINING_ROWS}


def seed_training_rows(conn):
    for table, values in TRAINING_ROWS.items():
        conn.execute(f'insert into "{table}" ({COLUMNS[table]}) values {values}')
    conn.commit()


def test_upgrade_downgrade_upgrade_keeps_training_rows_and_rebuilds_the_same_schema(tmp_path):
    db = tmp_path / "cycle.db"
    alembic(db, "upgrade", BEFORE_ASSESSMENT)
    conn = connect(db)
    # The chain's root revision builds every table the ORM knows about (``checkfirst``), so the
    # assessment tables already exist at the revision numbered before them, in their final
    # shape. 20261018_08/09 are no-ops on such a database and only do real work after a
    # downgrade — that is the convention the two migrations document.
    assert {"assessment_sittings", "assessment_forms", "study_cohorts"} <= tables(conn)
    assert "data_origin" in _columns(conn, "assessment_sittings")
    seed_training_rows(conn)
    before = training_dump(conn)

    # --- upgrade to head: training rows untouched
    alembic(db, "upgrade", "head")
    conn.close()
    conn = connect(db)
    assert conn.execute("select version_num from alembic_version").fetchone()[0] == HEAD
    assert not (ASSESSMENT_TABLES_GONE - tables(conn))
    assert training_dump(conn) == before
    head_schema = schema(conn, tables(conn))

    # --- downgrade below the assessment revisions: those tables disappear, training rows stay
    alembic(db, "downgrade", BEFORE_ASSESSMENT)
    conn.close()
    conn = connect(db)
    assert not (tables(conn) & set(ASSESSMENT_TABLES))
    assert training_dump(conn) == before

    # --- upgrade again: the tables come back through 08 and 09's own definitions
    alembic(db, "upgrade", "head")
    conn.close()
    conn = connect(db)
    assert not (ASSESSMENT_TABLES_GONE - tables(conn))
    assert training_dump(conn) == before
    # created_at regressed to nullable on this path before; the ORM declares it required.
    assert "created_at DATETIME NOT NULL" in schema(conn, ["assessment_sittings"])["assessment_sittings"]
    again = schema(conn, tables(conn))
    for name, ddl in sorted(again.items()):
        if name in head_schema:
            assert _equivalent(head_schema[name]) == _equivalent(ddl), f"{name} differs after down/up:\n" \
                                                                       f"{head_schema[name]}\n{ddl}"

    # --- and the result matches what a fresh install of the current models creates
    fresh = tmp_path / "fresh.db"
    from sqlalchemy import create_engine
    from app.database import Base
    import app.assessment_models  # noqa: F401  (registers the assessment tables)
    engine = create_engine(f"sqlite:///{fresh}")
    Base.metadata.create_all(engine)
    engine.dispose()
    fresh_conn = connect(fresh)
    for name in ("assessment_sittings", "assessment_forms", "assessment_reviews", "study_cohorts"):
        assert _equivalent(schema(conn, [name])[name]) == _equivalent(schema(fresh_conn, [name])[name]), name
    fresh_conn.close()
    conn.close()


ASSESSMENT_TABLES_GONE = {"assessment_sittings", "assessment_forms", "assessment_reviews", "study_cohorts",
                          "study_allocations", "research_codes"}


def _columns(conn, table):
    return {r[1] for r in conn.execute(f'pragma table_info("{table}")')}


def _equivalent(ddl):
    """SQLite DDL, with the parts that carry no meaning normalised away.

    Batch-mode rebuilds reorder FK/UNIQUE clauses, quote the table name and spell out a
    server default for the columns the migration had to add with one. None of that
    changes what the database enforces; a lost NOT NULL, UNIQUE or index does.
    """
    text = ddl.replace('"', "")
    text = re.sub(r"CONSTRAINT fk_\w+ ", "", text)
    text = re.sub(r" DEFAULT '[^']*'", "", text)
    head, _, body = text.partition("(")
    body = body.rsplit(")", 1)[0]
    clauses = sorted(re.split(r",(?![^()]*\))", body))
    return head.strip() + " (" + ", ".join(c.strip() for c in clauses) + ")"
