"""SQLite must run in WAL mode so readers never block the writer."""

from sqlalchemy import text

from app.database import DATABASE_URL, engine


def test_sqlite_engine_uses_wal_and_busy_timeout():
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.connect() as connection:
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar()
        busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar()
    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) >= 5000
