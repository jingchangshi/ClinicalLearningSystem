#!/usr/bin/env bash
set -euo pipefail

cd /home/jcshi/workspace/clinical_learning_system/backend

export PATH="/home/jcshi/.local/bin:/home/jcshi/Software/node/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
export FRONTEND_ORIGINS="${FRONTEND_ORIGINS:-https://clinpath.1031989.xyz,http://127.0.0.1:8101,http://localhost:8101}"
# Read endpoints are synchronous, so one process runs Python-level work one
# request at a time (measured: p95 6-10s for 100 concurrent readers). Four
# workers brought the same load to p95 ~0.19s at 2.3/4 cores of CPU.
# Consequence to keep in mind: the in-memory rate limiter and the ai_runtime
# counters are per process now (docs/ARCH.md §12).
export CLINPATH_BACKEND_WORKERS="${CLINPATH_BACKEND_WORKERS:-4}"

# A pending migration must never touch the live database without a snapshot first.
current_revision="$(uv run --python 3.11 --with-requirements requirements.txt alembic current 2>/dev/null | tail -n 1 | awk '{print $1}')"
head_revision="$(uv run --python 3.11 --with-requirements requirements.txt alembic heads 2>/dev/null | tail -n 1 | awk '{print $1}')"
if [ -n "$head_revision" ] && [ "$current_revision" != "$head_revision" ]; then
  echo "start_backend: migrating $current_revision -> $head_revision, taking a backup first"
  /home/jcshi/workspace/clinical_learning_system/scripts/backup_db.sh
fi
uv run --python 3.11 --with-requirements requirements.txt alembic upgrade head

# The Next.js proxy pools keep-alive sockets to this port and drops idle ones on
# its own shorter timer. With uvicorn's 5s default the server can close a socket
# first, and the next proxied request (a submit, after a slow model call) dies as
# "socket hang up / ECONNRESET" and surfaces as an unexpected 500. Keeping the
# server-side timeout comfortably longer makes the server never be the one that
# closes an idle connection.
exec uv run --python 3.11 --with-requirements requirements.txt \
  uvicorn app.main:app --host 0.0.0.0 --port 8100 --timeout-keep-alive 75 \
  --workers "$CLINPATH_BACKEND_WORKERS"
