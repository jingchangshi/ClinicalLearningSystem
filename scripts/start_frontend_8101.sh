#!/usr/bin/env bash
set -euo pipefail

cd /home/jcshi/workspace/clinical_learning_system/frontend

export PATH="/home/jcshi/.local/bin:/home/jcshi/Software/node/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
export INTERNAL_API_BASE_URL="${INTERNAL_API_BASE_URL:-http://127.0.0.1:8100}"

npm run build

exec npm run start -- --hostname 0.0.0.0 --port 8101
