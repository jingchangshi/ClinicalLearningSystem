#!/usr/bin/env bash
set -euo pipefail

cd /home/jcshi/workspace/clinical_learning_system/frontend

export PATH="/home/jcshi/.local/bin:/home/jcshi/Software/node/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
export INTERNAL_API_BASE_URL="${INTERNAL_API_BASE_URL:-http://127.0.0.1:8100/api}"

# The pilot entry is HTTPS (Cloudflare tunnel -> 127.0.0.1:8101); the plain-HTTP
# public port is retired, so the listener is bound to loopback. Set
# CLINPATH_FRONTEND_HOST=0.0.0.0 only for a temporary HTTP-only deployment.
export CLINPATH_FRONTEND_HOST="${CLINPATH_FRONTEND_HOST:-127.0.0.1}"

# Route protection verifies cookie signatures, so a deployment without the shared
# secret must fail fast instead of serving a proxy that cannot authorize.
if [ -z "${JWT_SECRET:-}" ]; then
  echo "start_frontend: JWT_SECRET is required (see ~/.config/clinpath/frontend.env)" >&2
  exit 1
fi
# Build-time stamp so the running frontend can be compared with git HEAD.
_repo=/home/jcshi/workspace/clinical_learning_system
_sha="$(git -C "$_repo" rev-parse --short HEAD 2>/dev/null || echo unknown)"
if [ -n "$(git -C "$_repo" status --porcelain 2>/dev/null)" ]; then
  _sha="${_sha}-dirty"
fi
export NEXT_PUBLIC_BUILD_SHA="${NEXT_PUBLIC_BUILD_SHA:-$_sha}"

npm run build

exec npm run start -- --hostname "$CLINPATH_FRONTEND_HOST" --port 8101
