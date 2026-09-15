"""A transient SQLite write lock must delay an audit event, not drop it."""

from app.core import ai_audit
from app.core.ai_audit import ai_invocation
from app.models import AIInvocation


class _FlakySession:
    """A session that fails its first ``fail_commits`` commit(s) with a lock error."""

    def __init__(self, real_session, fail_commits: int = 0):
        self._real = real_session
        self._remaining_failures = fail_commits
        self.attempts = 0

    def execute(self, *args, **kwargs):
        return self._real.execute(*args, **kwargs)

    def add(self, instance):
        self._real.add(instance)

    def commit(self):
        self.attempts += 1
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("database is locked")
        self._real.commit()

    def close(self):
        self._real.close()


def test_locked_write_is_retried(db_factory):
    from sqlalchemy.orm import sessionmaker

    db = db_factory()
    engine = db.get_bind()
    db.close()
    testing_session = sessionmaker(bind=engine, autoflush=False)
    # The lock lives on the database, so only the first attempt hits it.
    state = {"lock_held": True}
    sessions: list[_FlakySession] = []

    def factory():
        wrapper = _FlakySession(testing_session(), fail_commits=1 if state["lock_held"] else 0)
        state["lock_held"] = False
        sessions.append(wrapper)
        return wrapper

    previous = ai_audit._session_factory
    ai_audit.set_session_factory(factory)
    try:
        with ai_invocation("tutor_question", session_id=5):
            ai_audit.report_call(success=True, fallback_used=False, latency_ms=10)
        assert ai_audit.flush() is True
        # The first attempt hit the lock; a later attempt committed the row.
        assert len(sessions) >= 2
        assert sessions[0].attempts == 1
    finally:
        ai_audit.set_session_factory(previous)

    verify = db_factory()
    row = verify.query(AIInvocation).one()
    assert row.task_type == "tutor_question" and row.session_id == 5
    verify.close()


def test_persistent_failure_keeps_the_event_queued(monkeypatch):
    class _AlwaysFailing:
        def execute(self, *args, **kwargs):
            return None

        def add(self, instance):
            pass

        def commit(self):
            raise RuntimeError("database is locked")

        def close(self):
            pass

    previous = ai_audit._session_factory
    ai_audit.set_session_factory(lambda: _AlwaysFailing())
    try:
        with ai_invocation("case_evaluation") as invocation:
            ai_audit.report_call(success=True, fallback_used=False, latency_ms=5)
        assert invocation.recorded is True  # accepted for delivery
        assert ai_audit.flush(timeout=1.0) is False
        # The event is retained rather than lost, and nothing raised.
        assert ai_audit.queue_depth() >= 1
        ai_audit.flush(timeout=0.1)
    finally:
        # Do not leave the poisoned record behind for other tests.
        from app.core import ai_audit as module

        with module._queue_lock:
            module._queue.clear()
        ai_audit.set_session_factory(previous)
