#!/usr/bin/env bash
set -euo pipefail

cd /home/jcshi/workspace/clinical_learning_system/backend

export PATH="/home/jcshi/.local/bin:/home/jcshi/Software/node/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
export FRONTEND_ORIGINS="${FRONTEND_ORIGINS:-http://129.153.118.58:8101,http://localhost:8101,http://127.0.0.1:8101}"

exec uv run --with-requirements requirements.txt \
  uvicorn app.main:app --host 0.0.0.0 --port 8100
