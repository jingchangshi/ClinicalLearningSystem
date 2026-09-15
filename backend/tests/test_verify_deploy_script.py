"""The deploy verifier is a production gate: every required check must exit non-zero.

These tests run the real ``scripts/verify_deploy.sh`` against a fake deployment:
the host commands it calls (``git``, ``systemctl``, ``curl``) are stubbed on
PATH, so each failure mode is exercised without touching the live stack.
"""

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from app.core.source_fingerprint import compute_source_fingerprint

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SCRIPT = REPO_ROOT / "scripts" / "verify_deploy.sh"
MIGRATION_REVISION = "20260101_01"
PUBLIC_BASE = "http://stub.test"
INTERNAL_API = "http://internal.test:8100"
SHA = "a" * 40

FAKE_GIT = """#!/usr/bin/env python3
import json, os, sys

config = json.load(open(os.environ["VERIFY_TEST_CONFIG"]))
args = sys.argv[1:]
if "rev-parse" in args:
    print(config["sha"])
elif "status" in args:
    print(config.get("dirty", ""))
sys.exit(0)
"""

FAKE_SYSTEMCTL = """#!/usr/bin/env python3
import json, os, sys

config = json.load(open(os.environ["VERIFY_TEST_CONFIG"]))
unit = sys.argv[-1]
print(config["services"].get(unit, "inactive"))
sys.exit(0)
"""

FAKE_CURL = """#!/usr/bin/env python3
import json, os, sys

config = json.load(open(os.environ["VERIFY_TEST_CONFIG"]))
args = sys.argv[1:]
skip = False
positional = []
for arg in args:
    if skip:
        skip = False
        continue
    if arg in ("-o", "-m", "--max-time", "-w", "-H", "-X"):
        skip = True
        continue
    if arg.startswith("-"):
        continue
    positional.append(arg)
url = positional[-1]

def emit(body):
    if body is None:
        sys.exit(7)
    sys.stdout.write(body)
    sys.exit(0)

if url.endswith("/api/system/version"):
    emit(config["version_json"])
if url.endswith("/api/health"):
    emit(config["health"])
if "-o" in args:
    code = config["pages"].get(url)
    emit(("000" if code is None else str(code)) + "\\n")
# Plain body request for a known page.
emit(config["health"])
"""


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


@pytest.fixture
def deployment(tmp_path):
    """Build a fake checkout the verifier can be pointed at."""

    repo = tmp_path / "repo"
    (repo / "backend" / "app" / "core").mkdir(parents=True)
    (repo / "backend" / "alembic" / "versions").mkdir(parents=True)
    for relative in ("app/__init__.py", "app/core/__init__.py", "app/core/source_fingerprint.py"):
        (repo / "backend" / relative).write_bytes((BACKEND_ROOT / relative).read_bytes())
    (repo / "backend" / "alembic" / "versions" / "20260101_01_init.py").write_text(
        f"revision = '{MIGRATION_REVISION}'\ndown_revision = None\n"
    )
    fingerprint = compute_source_fingerprint(str(repo / "backend"))

    bins = tmp_path / "bin"
    bins.mkdir()
    _write_executable(bins / "git", FAKE_GIT)
    _write_executable(bins / "systemctl", FAKE_SYSTEMCTL)
    _write_executable(bins / "curl", FAKE_CURL)

    backend_env = tmp_path / "backend.env"
    frontend_env = tmp_path / "frontend.env"
    backend_env.write_text("JWT_SECRET=shared-secret\n")
    frontend_env.write_text("JWT_SECRET=shared-secret\n")
    config_path = tmp_path / "config.json"

    def run(**overrides):
        services = {
            "clinical-backend.service": "active",
            "clinical-frontend.service": "active",
        }
        services.update(overrides.pop("services", {}))
        pages = {
            f"{PUBLIC_BASE}/": 200,
            f"{PUBLIC_BASE}/login": 200,
        }
        pages.update(overrides.pop("pages", {}))
        config = {
            "sha": SHA,
            "dirty": "",
            "services": services,
            "pages": pages,
            "health": '{"status": "ok"}',
            "version_json": json.dumps(
                {
                    "git_sha": SHA,
                    "git_dirty": False,
                    "backend_source_fingerprint": fingerprint,
                    "schema_revision": MIGRATION_REVISION,
                    "environment": "production",
                }
            ),
        }
        config.update(overrides)
        config_path.write_text(json.dumps(config))
        environment = {
            **os.environ,
            "PATH": f"{bins}:{os.environ['PATH']}",
            "VERIFY_TEST_CONFIG": str(config_path),
            "CLINPATH_REPO_ROOT": str(repo),
            "CLINPATH_PUBLIC_BASE": PUBLIC_BASE,
            "CLINPATH_INTERNAL_API": INTERNAL_API,
            "CLINPATH_BACKEND_ENV": str(backend_env),
            "CLINPATH_FRONTEND_ENV": str(frontend_env),
        }
        return subprocess.run(
            ["bash", str(SCRIPT)], capture_output=True, text=True, env=environment, cwd=REPO_ROOT
        )

    run.backend_env = backend_env  # type: ignore[attr-defined]
    run.frontend_env = frontend_env  # type: ignore[attr-defined]
    run.fingerprint = fingerprint  # type: ignore[attr-defined]
    return run


def test_everything_healthy_passes(deployment):
    result = deployment()

    assert result.returncode == 0, result.stdout + result.stderr
    assert "DEPLOY VERIFICATION PASSED" in result.stdout


def test_inactive_frontend_fails(deployment):
    result = deployment(services={"clinical-frontend.service": "inactive"})

    assert result.returncode == 1, result.stdout
    assert "clinical-frontend.service is inactive" in result.stdout


def test_inactive_backend_fails(deployment):
    result = deployment(services={"clinical-backend.service": "failed"})

    assert result.returncode == 1, result.stdout
    assert "clinical-backend.service is failed" in result.stdout


@pytest.mark.parametrize("path", ["/", "/login"])
def test_unreachable_public_entry_fails(deployment, path):
    result = deployment(pages={f"{PUBLIC_BASE}{path}": None})

    assert result.returncode == 1, result.stdout
    assert "expected 200" in result.stdout


def test_unhealthy_public_api_health_fails(deployment):
    result = deployment(health="")

    assert result.returncode == 1, result.stdout
    assert "/api/health did not report a healthy backend" in result.stdout


def test_jwt_secret_mismatch_fails(deployment):
    deployment.frontend_env.write_text("JWT_SECRET=a-different-secret\n")

    result = deployment()

    assert result.returncode == 1, result.stdout
    assert "MISMATCH" in result.stdout


def test_missing_jwt_secret_fails(deployment):
    deployment.frontend_env.write_text("OTHER=value\n")

    result = deployment()

    assert result.returncode == 1, result.stdout
    assert "JWT_SECRET parity is not MATCH" in result.stdout


def test_running_sha_mismatch_fails(deployment):
    result = deployment(version_json=json.dumps({
        "git_sha": "b" * 40,
        "git_dirty": False,
        "backend_source_fingerprint": "v1:000000000000",
        "schema_revision": MIGRATION_REVISION,
        "environment": "production",
    }))

    assert result.returncode == 1, result.stdout
    assert "differs from this checkout" in result.stdout


def test_source_fingerprint_mismatch_fails(deployment):
    result = deployment(version_json=json.dumps({
        "git_sha": SHA,
        "git_dirty": True,
        "backend_source_fingerprint": "v1:ffffffffffff",
        "schema_revision": MIGRATION_REVISION,
        "environment": "production",
    }))

    assert result.returncode == 1, result.stdout
    assert "running source differs from this checkout" in result.stdout


def test_schema_revision_mismatch_fails(deployment):
    result = deployment(version_json=json.dumps({
        "git_sha": SHA,
        "git_dirty": False,
        "backend_source_fingerprint": deployment.fingerprint,
        "schema_revision": "20250101_99",
        "environment": "production",
    }))

    assert result.returncode == 1, result.stdout
    assert "is not the migration head" in result.stdout


def test_unreachable_backend_version_endpoint_fails(deployment):
    result = deployment(version_json=None)

    assert result.returncode == 1, result.stdout
    assert "unreachable" in result.stdout
