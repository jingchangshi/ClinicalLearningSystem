"""The production frontend entrypoint must refuse to start without JWT_SECRET.

Route protection verifies cookie signatures, so a deployment without the shared
secret cannot authorize anything. Failing at boot is much clearer than serving a
proxy that answers 503 (or worse, trusts an unverified claim) later.
"""

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "start_frontend_8101.sh"


def _run_without_secret() -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items() if key != "JWT_SECRET"}
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_start_script_requires_jwt_secret():
    result = _run_without_secret()
    assert result.returncode != 0
    assert "JWT_SECRET is required" in (result.stderr + result.stdout)
    # It must refuse before doing any work (no build output).
    assert "next build" not in result.stdout


def test_start_script_guard_is_documented_in_the_unit():
    unit = (REPO_ROOT / "deploy" / "systemd-user" / "clinical-frontend.service").read_text()
    assert "frontend.env" in unit
    example = (REPO_ROOT / "deploy" / "env" / "frontend.env.example").read_text()
    assert "JWT_SECRET=" in example
