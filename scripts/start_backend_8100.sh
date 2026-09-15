#!/usr/bin/env bash
set -euo pipefail

cd /home/jcshi/workspace/clinical_learning_system/backend

export PATH="/home/jcshi/.local/bin:/home/jcshi/Software/node/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
export FRONTEND_ORIGINS="${FRONTEND_ORIGINS:-http://129.153.118.58:8101,http://localhost:8101,http://127.0.0.1:8101}"

# A pending migration must never touch the live database without a snapshot first.
current_revision="$(uv run --python 3.11 --with-requirements requirements.txt alembic current 2>/dev/null | tail -n 1 | awk '{print $1}')"
head_revision="$(uv run --python 3.11 --with-requirements requirements.txt alembic heads 2>/dev/null | tail -n 1 | awk '{print $1}')"
if [ -n "$head_revision" ] && [ "$current_revision" != "$head_revision" ]; then
  echo "start_backend: migrating $current_revision -> $head_revision, taking a backup first"
  /home/jcshi/workspace/clinical_learning_system/scripts/backup_db.sh
fi
uv run --python 3.11 --with-requirements requirements.txt alembic upgrade head
exec uv run --python 3.11 --with-requirements requirements.txt \
  uvicorn app.main:app --host 0.0.0.0 --port 8100
