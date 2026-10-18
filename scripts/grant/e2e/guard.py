"""Refuse to run anything that could reach the production stack.

Production on this machine is:

    clinical-backend.service   -> 0.0.0.0:8100   (backend, real DB)
    clinical-frontend.service  -> 127.0.0.1:8101 (Next.js, proxy -> 8100)
    clinical-https.service     -> HTTPS tunnel

The disposable stack must use other ports and its own database. A previous
incident (docs/teaching_grant_2026/evidence/E2_platform/
INCIDENT_2026-10-18_production_touch.md) happened because a frontend build baked
the default INTERNAL_API_BASE_URL (8100) into the rewrites and only the *listen*
port had been changed. So the port check alone is not enough: callers must also
pass the isolated API base URL at build time, which `stack.py` enforces.

Nothing here imports app code, so it is safe to run from any checkout.
"""
from __future__ import annotations

import socket

FORBIDDEN_PORTS = {8100, 8101}
PRODUCTION_DB = "/home/jcshi/workspace/clinical_learning_system/backend/clinical_learning.db"
PRODUCTION_CONFIG_DIR = "/home/jcshi/.config/clinpath"


class IsolationError(RuntimeError):
    """A requested value would touch production."""


def check_port(port: int, what: str = "port") -> int:
    if not isinstance(port, int) or not (1024 <= port <= 65535):
        raise IsolationError(f"{what} {port!r} is not an unprivileged port in 1024..65535")
    if port in FORBIDDEN_PORTS:
        raise IsolationError(f"{what} {port} is the production port; refusing to use it")
    return port


def check_free(port: int) -> None:
    """Fail if something already listens on the port (never adopt an unknown server)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise IsolationError(f"port {port} is already in use ({exc}); pick another") from None


def check_database_url(url: str) -> str:
    if not url.startswith("sqlite:///"):
        raise IsolationError(f"DATABASE_URL must be a throwaway SQLite file, got {url!r}")
    path = url[len("sqlite:///"):]
    if not path.startswith("/tmp/"):
        raise IsolationError(f"the disposable database must live under /tmp, got {path!r}")
    if PRODUCTION_DB in path or path.rstrip("/") == PRODUCTION_DB.rsplit("/", 1)[0]:
        raise IsolationError("that path is the production database")
    return url


def check_api_base(url: str) -> str:
    """The build-time API target must be a loopback port that is not production."""
    if not url.startswith("http://127.0.0.1:") and not url.startswith("http://localhost:"):
        raise IsolationError(f"INTERNAL_API_BASE_URL must be a loopback URL, got {url!r}")
    rest = url.split("://", 1)[1]
    authority = rest.split("/", 1)[0]
    port_text = authority.rsplit(":", 1)[1] if ":" in authority else "80"
    try:
        port = int(port_text)
    except ValueError:
        raise IsolationError(f"cannot read a port from {url!r}") from None
    check_port(port, "INTERNAL_API_BASE_URL port")
    return url
