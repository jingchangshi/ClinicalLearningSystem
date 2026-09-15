import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Test runs hit the same endpoints repeatedly from one process; the production
# limits themselves are unit-tested in test_abuse_guard.py.
os.environ.setdefault("CLINPATH_ENV", "development")
os.environ.setdefault("ALLOW_PUBLIC_REGISTRATION", "true")
for bucket in ("REGISTER", "LOGIN", "COACH", "SP_MESSAGE", "SUBMIT", "CASE_GENERATE", "AI_PROBE"):
    os.environ.setdefault(f"RATE_LIMIT_{bucket}_PER_HOUR", "1000")

# Unit tests must never spend real model quota or depend on ambient credentials,
# so the suite runs with AI configuration removed. The live path is verified
# against the deployed service (and by LLM_LIVE_AI=1 opt-in runs).
if os.getenv("LLM_LIVE_AI") != "1":
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_PROVIDER",
                 "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
                 "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
        os.environ.pop(name, None)
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.core import ai_audit  # noqa: E402
from app.models import AIInvocation  # noqa: E402

# The AI audit writer opens its own session. Without this, audited code paths
# reached from tests would write audit rows into the real database.
_audit_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(_audit_engine, tables=[AIInvocation.__table__])
ai_audit.set_session_factory(sessionmaker(bind=_audit_engine, autoflush=False))


@pytest.fixture(autouse=True)
def _isolate_audit_queue():
    """The audit queue is module-global; clear it around every test."""

    ai_audit.reset_for_tests()
    yield
    ai_audit.reset_for_tests()


@pytest.fixture
def db_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    Base.metadata.create_all(engine)

    def override_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestingSession
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
