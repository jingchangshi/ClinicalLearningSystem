from collections.abc import Generator
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clinical_learning.db")

# The default QueuePool is 5 connections plus 10 of overflow, i.e. 15 in-flight
# sessions for the whole process. Measured under 100 concurrent readers, that
# ceiling — not SQLite and not the CPU — was what produced
# "QueuePool limit of size 5 overflow 10 reached, connection timed out".
# The size is explicit here so the limit is a decision with evidence behind it.
# ``pool_timeout`` stays short: waiting 30 s for a connection only converts a
# capacity problem into a pile of slow 500s.
_engine_kwargs: dict = {"connect_args": {"check_same_thread": False}}
if DATABASE_URL.startswith("sqlite") and ":memory:" not in DATABASE_URL:
    _engine_kwargs.update(
        pool_size=int(os.getenv("CLINPATH_SQLITE_POOL_SIZE", "20")),
        max_overflow=int(os.getenv("CLINPATH_SQLITE_MAX_OVERFLOW", "40")),
        pool_timeout=float(os.getenv("CLINPATH_SQLITE_POOL_TIMEOUT", "5")),
        pool_recycle=1800,
    )

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _apply_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        """WAL so a reader cannot block the writer, plus a bounded busy wait.

        Default rollback-journal SQLite holds a shared lock for the whole life of a
        read transaction, which made concurrent requests (and the AI audit writer)
        fail with "database is locked". WAL removes reader/writer blocking and is
        safe for the sqlite3 backup API used by scripts/backup_db.sh.
        """

        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
