#!/usr/bin/env bash
# Disposable staging backend for capacity testing.
#
#   scripts/start_staging_8200.sh
#
# It never touches the production database or the running services: the schema
# and data come from a timestamped sqlite backup copy, the process listens on
# 127.0.0.1:8200, and the provider can be pointed at loadtest/mock_provider.py.
#
# Staging-only overrides (all optional, all read from the caller's environment):
#   CLINPATH_STAGING_DB            copy of the production database
#   CLINPATH_STAGING_PORT          default 8200
#   CLINPATH_STAGING_REFRESH_DB    re-copy from production when "1" (default)
#   CLINPATH_STAGING_LLM_BASE_URL  e.g. http://127.0.0.1:8300
#   CLINPATH_STAGING_LLM_MODEL     e.g. mock-model
#   CLINPATH_STAGING_LLM_PROVIDER  e.g. openai-compatible
#   CLINPATH_STAGING_LOGIN_LIMIT   login attempts/hour/IP (default 1000)
#   CLINPATH_STAGING_LOG_FILE      default <staging dir>/staging.log
#   CLINPATH_STAGING_WORKERS       uvicorn worker processes (default 1)
#   CLINPATH_STAGING_ABUSE_LIMITS  "1" lifts the per-identity abuse limits so a
#                                  capacity run is not cut short by them
set -euo pipefail

REPO_ROOT="${CLINPATH_REPO_ROOT:-/home/jcshi/workspace/clinical_learning_system}"
OPERATOR_ENV="${CLINPATH_BACKEND_ENV:-$HOME/.config/clinpath/backend.env}"
STAGING_DB="${CLINPATH_STAGING_DB:-$HOME/.local/state/clinpath-staging/staging.db}"
STAGING_PORT="${CLINPATH_STAGING_PORT:-8200}"
PRODUCTION_DB="${CLINPATH_PRODUCTION_DB:-$REPO_ROOT/backend/clinical_learning.db}"

if [ ! -f "$OPERATOR_ENV" ]; then
  echo "operator environment not found: $OPERATOR_ENV" >&2
  exit 1
fi

mkdir -p "$(dirname "$STAGING_DB")"
# A load test must never write its logs into a terminal: a full PTY buffer blocks
# the event loop on write and turns a capacity measurement into a measurement of
# the terminal. Redirect to a file before the server starts.
STAGING_LOG="${CLINPATH_STAGING_LOG_FILE:-$(dirname "$STAGING_DB")/staging.log}"
exec 3>&1
exec >>"$STAGING_LOG" 2>&1
echo "=== staging start $(date -Is) ==="

if [ "${CLINPATH_STAGING_REFRESH_DB:-1}" = "1" ] && [ -f "$PRODUCTION_DB" ]; then
  # Offline copy: the running deployment keeps serving its own file.
  rm -f "$STAGING_DB" "$STAGING_DB-wal" "$STAGING_DB-shm"
  sqlite3 "$PRODUCTION_DB" ".backup '$STAGING_DB'"
  echo "staging database refreshed from production (copy only)"
fi

set -a
# shellcheck disable=SC1090
. "$OPERATOR_ENV"
set +a

export DATABASE_URL="sqlite:///$STAGING_DB"
export CLINPATH_ENV=production
export LLM_BASE_URL="${CLINPATH_STAGING_LLM_BASE_URL:-${LLM_BASE_URL:-}}"
export LLM_MODEL="${CLINPATH_STAGING_LLM_MODEL:-${LLM_MODEL:-}}"
export LLM_PROVIDER="${CLINPATH_STAGING_LLM_PROVIDER:-${LLM_PROVIDER:-}}"
export LLM_MAX_RETRIES="${CLINPATH_STAGING_LLM_MAX_RETRIES:-1}"
export RATE_LIMIT_LOGIN_PER_HOUR="${CLINPATH_STAGING_LOGIN_LIMIT:-1000}"
if [ "${CLINPATH_STAGING_ABUSE_LIMITS:-0}" = "1" ]; then
  # Load-test-only: the limits themselves are reported as their own finding.
  export RATE_LIMIT_COACH_PER_HOUR=100000
  export RATE_LIMIT_SUBMIT_PER_HOUR=100000
  export RATE_LIMIT_SP_MESSAGE_PER_HOUR=100000
fi
export FRONTEND_ORIGINS="${FRONTEND_ORIGINS:-http://127.0.0.1:8101}"

cd "$REPO_ROOT/backend"
echo "staging schema -> head"
uv run --python 3.11 --with-requirements requirements.txt alembic upgrade head

echo "staging backend on http://127.0.0.1:$STAGING_PORT (db=$STAGING_DB)"
echo "staging backend on http://127.0.0.1:$STAGING_PORT (db=$STAGING_DB, log $STAGING_LOG)" >&3
exec uv run --python 3.11 --with-requirements requirements.txt \
  uvicorn app.main:app --host 127.0.0.1 --port "$STAGING_PORT" --timeout-keep-alive 75 \
  --workers "${CLINPATH_STAGING_WORKERS:-1}"
