"""Content fingerprint of the running backend source.

A git SHA alone cannot describe a deployment that carries local edits — and this
workspace deploys an uncommitted working tree. The fingerprint is a SHA-256 over
(relative path, file bytes) for the backend application and migration sources, so
"is the running server the code I am looking at?" is answerable in one compare.
"""

import hashlib
import os

FINGERPRINT_VERSION = "v1"
SOURCE_ROOTS = ("app", "alembic/versions")

_cached: str | None = None


def backend_root() -> str:
    # <backend>/app/core/source_fingerprint.py -> <backend>
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def compute_source_fingerprint(base_dir: str | None = None) -> str:
    """Return ``"<version>:<12 hex chars>"`` for the given backend checkout."""

    base = base_dir or backend_root()
    paths: list[str] = []
    for root in SOURCE_ROOTS:
        for dirpath, dirnames, filenames in os.walk(os.path.join(base, root)):
            dirnames[:] = sorted(name for name in dirnames if name != "__pycache__")
            for name in filenames:
                if name.endswith(".py"):
                    paths.append(os.path.join(dirpath, name))

    if not paths:
        raise RuntimeError(
            f"source fingerprint found no python files under {base} for roots {SOURCE_ROOTS}"
        )

    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(os.path.relpath(path, base).replace(os.sep, "/").encode("utf-8"))
        digest.update(b"\0")
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    return f"{FINGERPRINT_VERSION}:{digest.hexdigest()[:12]}"


def source_fingerprint() -> str:
    global _cached
    if _cached is None:
        _cached = compute_source_fingerprint()
    return _cached
