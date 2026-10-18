"""Build, start and stop the disposable acceptance stack on isolated ports.

The stack is four things that must not leak into each other or into production:

    backend   uvicorn on 127.0.0.1:8400   (throwaway SQLite under /tmp)
    frontend  Next.js on 127.0.0.1:8401   (dedicated NEXT_DIST_DIR build)
    database  /tmp/<run>/accept.db        (alembic upgrade head)
    env       process-local only          (never ~/.config/clinpath/*)

The Next.js `rewrites()` target is baked in at BUILD time, so the build step
always passes INTERNAL_API_BASE_URL=http://127.0.0.1:8400/api and a private
NEXT_DIST_DIR. Setting the variable only at `next start` does not change the
built proxy target -- that was the production incident.

The orchestrator runs the whole cycle in one process so its `finally` always
stops both servers, even when the command it runs fails.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend"
FRONTEND = REPO / "frontend"
UV = shutil.which("uv") or "uv"
UV_ARGS = ["run", "--python", "3.11", "--with-requirements", "requirements.txt"]

DEFAULT_BACKEND_PORT = 8400
DEFAULT_FRONTEND_PORT = 8401
DEFAULT_DIST = ".next-accept"
DEFAULT_RUN_DIR = "/tmp/clinpath-e2e"
# Throwaway values; they never leave this process and are not operator secrets.
DEV_JWT_SECRET = "e2e-disposable-jwt-secret-not-production"


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str], log: Path, check: bool = True) -> subprocess.CompletedProcess:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as handle:
        handle.write(f"\n$ {' '.join(shlex.quote(c) for c in cmd)}\n".encode())
        handle.flush()
        completed = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=handle, stderr=subprocess.STDOUT)
    if check and completed.returncode != 0:
        tail = log.read_text(errors="replace").splitlines()[-40:]
        raise SystemExit(f"command failed ({completed.returncode}): {' '.join(cmd)}\n--- {log} tail ---\n" + "\n".join(tail))
    return completed


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(REPO), text=True).strip()
    except Exception:  # noqa: BLE001 - a build stamp must never fail the stack
        return "unknown"


def build_env(backend_port: int, database_url: str) -> dict[str, str]:
    """A process-local environment: no inherited production secrets, no model key."""
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/home/jcshi"),
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        "DATABASE_URL": database_url,
        "JWT_SECRET": DEV_JWT_SECRET,
        "CLINPATH_ENV": "development",
        # Deliberately keyless: acceptance must not spend model calls or depend on
        # an external provider. AI is unavailable -> the product must say so.
        "LLM_API_KEY": "",
        "DEEPSEEK_API_KEY": "",
        "OPENAI_API_KEY": "",
        "COOKIE_SECURE": "false",
        "SEED_DEMO_STUDENT_ACCOUNTS": "true",
        "SEED_DEMO_STUDENT_PASSWORD": "test-student-pw",
        "INTERNAL_API_BASE_URL": f"http://127.0.0.1:{backend_port}/api",
        # Browser-side calls must stay relative so they go through the Next proxy
        # (which the build already points at the isolated backend). An absolute
        # value here would make the browser call the backend cross-origin and be
        # blocked by CORS -- and, worse, would bypass the proxy path we are testing.
        "NEXT_PUBLIC_API_BASE_URL": "/api",
        "NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS": "true",
        "NEXT_PUBLIC_ALLOW_PUBLIC_REGISTRATION": "false",
        "NEXT_PUBLIC_BUILD_SHA": _git_sha(),
        "PYTHONUNBUFFERED": "1",
    }


def wait_http(url: str, *, timeout: float, label: str) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status < 500:
                    return
                last = f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            if exc.code < 500:  # a 401/403/404 still proves the server is up
                return
            last = f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001 - connection refused while booting
            last = str(exc)
        time.sleep(0.5)
    raise SystemExit(f"{label} did not become ready at {url} within {timeout}s ({last})")


class Stack:
    def __init__(self, *, backend_port: int, frontend_port: int, run_dir: Path, dist_dir: str,
                 database_url: str):
        self.backend_port = guard.check_port(backend_port, "backend port")
        self.frontend_port = guard.check_port(frontend_port, "frontend port")
        if self.backend_port == self.frontend_port:
            raise guard.IsolationError("backend and frontend need different ports")
        self.run_dir = run_dir
        self.dist_dir = dist_dir
        self.database_url = guard.check_database_url(database_url)
        self.env = build_env(self.backend_port, self.database_url)
        self.procs: list[subprocess.Popen] = []
        self.run_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.frontend_port}"

    @property
    def api_url(self) -> str:
        return f"http://127.0.0.1:{self.backend_port}"

    # --- lifecycle ---------------------------------------------------------
    def prepare_database(self, *, reset: bool = False) -> None:
        """Create the throwaway database.

        `reset` must remove the -wal/-shm sidecars too: SQLite keeps committed
        pages in the WAL, so deleting only `accept.db` can leave the previous run's
        rows attached to the "new" file. That silently reuses old sitting windows
        and makes a supposedly fresh run fail in confusing ways.
        """
        base = self.run_dir / "accept.db"
        if reset:
            removed = []
            for suffix in ("", "-wal", "-shm"):
                path = Path(str(base) + suffix)
                if path.exists():
                    path.unlink()
                    removed.append(path.name)
            if removed:
                print(f"reset: removed {', '.join(removed)}")
        elif base.exists():
            raise SystemExit(
                f"{base} already exists. Pass --reset for a fresh acceptance run, "
                "or use a different --run-dir."
            )
        self._run([UV, *UV_ARGS, "alembic", "upgrade", "head"], log="alembic.log")
        self._run([UV, *UV_ARGS, "python", "-m", "app.seed_data"], log="seed.log")

    def build_frontend(self) -> None:
        """Build into a private dist dir with the isolated API target baked in.

        A non-default NEXT_DIST_DIR makes Next.js rewrite two tracked files
        (`next-env.d.ts` and `tsconfig.json`) to point at that directory. The
        acceptance build must not leave that in the working tree, so both files
        are snapshotted and restored in a `finally`.
        """
        guard.check_api_base(self.env["INTERNAL_API_BASE_URL"])
        touched = [FRONTEND / "next-env.d.ts", FRONTEND / "tsconfig.json"]
        snapshots = {path: path.read_bytes() for path in touched if path.exists()}
        try:
            self._run(["npm", "run", "build"], log="frontend-build.log", cwd=FRONTEND,
                      env=dict(self.env, NEXT_DIST_DIR=self.dist_dir))
        finally:
            for path, content in snapshots.items():
                if path.read_bytes() != content:
                    path.write_bytes(content)
                    print(f"restored {path.relative_to(REPO)} after the isolated build")
        if not (FRONTEND / self.dist_dir / "BUILD_ID").exists():
            raise SystemExit(f"build did not produce {self.dist_dir}/BUILD_ID; refusing to start")

    def _run(self, cmd, *, log, env=None, cwd=BACKEND):
        _run(cmd, cwd=cwd, env=env or self.env, log=self.run_dir / log)

    def _spawn(self, cmd: list[str], *, log_name: str, env: dict[str, str], cwd: Path) -> None:
        """Start a child in its own process group.

        `npm run start` forks `next-server`; signalling npm alone leaves the real
        server listening on the port. A dedicated session lets `stop()` kill the
        whole group, so a failed run never leaves a stray acceptance server.
        """
        handle = (self.run_dir / log_name).open("ab")
        handle.write(f"\n$ {' '.join(shlex.quote(c) for c in cmd)}\n".encode())
        handle.flush()
        proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=handle,
                                stderr=subprocess.STDOUT, start_new_session=True)
        self.procs.append(proc)

    def start_backend(self) -> None:
        guard.check_free(self.backend_port)
        self._spawn([UV, *UV_ARGS, "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(self.backend_port)],
                    log_name="backend.log", env=self.env, cwd=BACKEND)
        wait_http(f"{self.api_url}/api/health", timeout=90, label="backend")

    def start_frontend(self) -> None:
        guard.check_free(self.frontend_port)
        self._spawn(["npm", "run", "start", "--", "--hostname", "127.0.0.1", "--port", str(self.frontend_port)],
                    log_name="frontend.log", env=dict(self.env, NEXT_DIST_DIR=self.dist_dir), cwd=FRONTEND)
        wait_http(f"{self.base_url}/login", timeout=120, label="frontend")

    def stop(self) -> None:
        for proc in reversed(self.procs):
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for proc in reversed(self.procs):
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)
        self.procs.clear()

    def write_manifest(self, extra: dict) -> Path:
        path = self.run_dir / "stack.json"
        payload = {
            "git_sha": _git_sha(),
            "backend_port": self.backend_port,
            "frontend_port": self.frontend_port,
            "e2e_base_url": self.base_url,
            "api_url": self.api_url,
            "database_url": self.database_url,
            "dist_dir": self.dist_dir,
            "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **extra,
        }
        path.write_text(json.dumps(payload, indent=2) + "\n")
        return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated ClinPath acceptance stack")
    parser.add_argument("action", choices=["prepare", "build", "serve"])
    parser.add_argument("--backend-port", type=int, default=DEFAULT_BACKEND_PORT)
    parser.add_argument("--frontend-port", type=int, default=DEFAULT_FRONTEND_PORT)
    parser.add_argument("--run-dir", default=DEFAULT_RUN_DIR)
    parser.add_argument("--dist-dir", default=DEFAULT_DIST)
    parser.add_argument("--reset", action="store_true", help="delete the throwaway DB first (prepare only)")
    args, extra = parser.parse_known_args()
    args.command = [a for a in extra if a != "--"]

    run_dir = Path(args.run_dir)
    stack = Stack(
        backend_port=args.backend_port, frontend_port=args.frontend_port, run_dir=run_dir,
        dist_dir=args.dist_dir, database_url=f"sqlite:///{run_dir}/accept.db",
    )
    if args.action == "prepare":
        stack.prepare_database(reset=args.reset)
        print(f"prepared {stack.database_url}")
        return 0
    if args.action == "build":
        stack.build_frontend()
        print(f"built {FRONTEND / args.dist_dir}")
        return 0

    # serve: start, run the command (if any), always stop.
    if not args.command:
        raise SystemExit("serve needs a command, e.g. `-- npx playwright test`")
    stack.write_manifest({"command": args.command})
    try:
        stack.start_backend()
        stack.start_frontend()
        env = dict(os.environ, E2E_BASE_URL=stack.base_url, E2E_API_BASE_URL=stack.api_url,
                   E2E_DATABASE_URL=stack.database_url, E2E_RUN_DIR=str(run_dir))
        return subprocess.run(args.command, cwd=str(REPO), env=env).returncode
    finally:
        stack.stop()


if __name__ == "__main__":
    raise SystemExit(main())
