"""Stamping must never pretend an existing database is current.

These run the real entrypoint in a subprocess against a temporary database, so
the behaviour under test is exactly the deployed path (`python -m app.seed_data`
with DATABASE_URL pointing at the file).
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

HEAD_REVISION = "20260915_05"


def _run_seed(database: Path) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database}",
        "SEED_DEMO_STUDENT_ACCOUNTS": "true",
        "SEED_DEMO_STUDENT_PASSWORD": "local-test-password",
    }
    return subprocess.run(
        [sys.executable, "-m", "app.seed_data"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _revision(database: Path) -> str | None:
    con = sqlite3.connect(database)
    try:
        rows = con.execute("select version_num from alembic_version").fetchall()
        return rows[0][0] if rows else None
    finally:
        con.close()


def _columns(database: Path, table: str) -> set[str]:
    con = sqlite3.connect(database)
    try:
        return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()


def _counts(database: Path, tables: list[str]) -> dict[str, int]:
    con = sqlite3.connect(database)
    try:
        return {table: con.execute(f"select count(*) from {table}").fetchone()[0] for table in tables}
    finally:
        con.close()


def test_fresh_database_is_created_and_stamped(tmp_path):
    database = tmp_path / "fresh.db"
    result = _run_seed(database)
    assert result.returncode == 0, result.stderr[-2000:]

    assert _revision(database) == HEAD_REVISION
    assert {"evaluation_mode", "ai_score", "degraded"} <= _columns(database, "scores")
    assert "updated_at" in _columns(database, "student_answers")
    assert {"tutor_turns", "ai_invocations"} <= {
        row[0] for row in sqlite3.connect(database).execute("select name from sqlite_master where type='table'")
    }
    # A fresh install seeds teaching data but no privileged account.
    con = sqlite3.connect(database)
    roles = {row[0] for row in con.execute("select distinct role from users")}
    con.close()
    assert "teacher" not in roles and "admin" not in roles


def test_existing_old_database_is_migrated_not_stamped(tmp_path):
    """A database missing a column must be upgraded; a stamp would hide that."""

    database = tmp_path / "legacy.db"
    assert _run_seed(database).returncode == 0

    # Simulate a legacy install: current tables, a provenance column removed, and
    # no migration version recorded.
    con = sqlite3.connect(database)
    con.execute("ALTER TABLE scores DROP COLUMN evaluation_mode")
    con.execute("DROP TABLE alembic_version")
    con.commit()
    con.close()
    assert "evaluation_mode" not in _columns(database, "scores")

    result = _run_seed(database)
    assert result.returncode == 0, result.stderr[-2000:]

    # The column is back only because migrations actually ran.
    assert "evaluation_mode" in _columns(database, "scores")
    assert _revision(database) == HEAD_REVISION


def test_already_current_database_is_idempotent(tmp_path):
    database = tmp_path / "current.db"
    assert _run_seed(database).returncode == 0
    tables = ["users", "students", "teachers", "cases", "knowledge_units", "scores"]
    before = _counts(database, tables)
    revision_before = _revision(database)

    result = _run_seed(database)
    assert result.returncode == 0, result.stderr[-2000:]

    assert _revision(database) == revision_before == HEAD_REVISION
    # Re-running seeds nothing new and destroys nothing.
    after = _counts(database, tables)
    assert after["users"] == before["users"]
    assert after["cases"] == before["cases"]
    for table in ("students", "teachers", "knowledge_units", "scores"):
        assert after[table] >= 0
        assert after[table] == before[table]


def test_seed_refuses_to_produce_staff_credentials(tmp_path):
    database = tmp_path / "no-staff.db"
    assert _run_seed(database).returncode == 0

    con = sqlite3.connect(database)
    rows = con.execute("select username, role from users order by username").fetchall()
    con.close()
    assert rows, "the restricted student demo logins should still be seeded"
    assert all(role == "student" for _, role in rows), rows
