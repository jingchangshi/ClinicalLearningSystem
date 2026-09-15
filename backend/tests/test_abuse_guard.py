"""Public endpoints must not be an open tap on paid model quota."""

from app.core import rate_limit
from app.core.rate_limit import SlidingWindowLimiter
from app.routes import auth as auth_routes

from tests.factories import make_case


def test_sliding_window_blocks_after_the_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REGISTER_PER_HOUR", "2")
    limiter = SlidingWindowLimiter()

    assert limiter.hit("register", "1.2.3.4") == (True, 0)
    assert limiter.hit("register", "1.2.3.4") == (True, 0)
    allowed, retry_after = limiter.hit("register", "1.2.3.4")
    assert allowed is False
    assert retry_after > 0
    # A different identity is unaffected.
    assert limiter.hit("register", "5.6.7.8") == (True, 0)


def test_register_returns_429_after_repeated_attempts(client, db_factory, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REGISTER_PER_HOUR", "2")
    db = db_factory()
    make_case(db)
    db.commit()
    db.close()

    payload = {"username": "flood1", "password": "secret1", "role": "student"}
    assert client.post("/api/auth/register", json=payload).status_code == 200
    assert client.post(
        "/api/auth/register", json={"username": "flood2", "password": "secret1", "role": "student"}
    ).status_code == 200
    blocked = client.post(
        "/api/auth/register", json={"username": "flood3", "password": "secret1", "role": "student"}
    )
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"]


def test_public_registration_can_be_closed(client, monkeypatch):
    monkeypatch.setattr(auth_routes, "ALLOW_PUBLIC_REGISTRATION", False)
    response = client.post(
        "/api/auth/register", json={"username": "closed", "password": "secret1", "role": "student"}
    )
    assert response.status_code == 403


def test_teacher_only_accounts_cannot_be_self_provisioned(client, monkeypatch):
    monkeypatch.setattr(auth_routes, "ALLOW_PUBLIC_REGISTRATION", True)
    response = client.post(
        "/api/auth/register", json={"username": "fake", "password": "secret1", "role": "teacher"}
    )
    assert response.status_code == 422
