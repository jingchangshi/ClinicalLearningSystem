#!/usr/bin/env bash
# End-to-end acceptance driver for the isolated ClinPath stack.
#
#   ./run_acceptance.sh                     # prepare DB, build, start, fixture, Playwright, stop
#   ./run_acceptance.sh --reuse-build       # skip the Next.js build (reuse frontend/.next-accept)
#   ./run_acceptance.sh --no-tests          # stack + fixture only
#   ./run_acceptance.sh -- <playwright args>  # e.g. -- assessment.spec.ts
#
# Ports are fixed and checked: 8400 (backend) and 8401 (frontend). The script
# refuses the production ports 8100/8101, and stack.py refuses to start on a
# port something already listens on.
#
# All state lives in /tmp/clinpath-e2e and frontend/.next-accept. It never reads
# or writes ~/.config/clinpath/*.env and never touches the production database.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
RUN_DIR="${E2E_RUN_DIR:-/tmp/clinpath-e2e}"
BACKEND_PORT="${E2E_BACKEND_PORT:-8400}"
FRONTEND_PORT="${E2E_FRONTEND_PORT:-8401}"
DIST_DIR="${E2E_DIST_DIR:-.next-accept}"
JWT_SECRET="test-only-jwt-secret-8f3a1c"

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if [[ "$port" == "8100" || "$port" == "8101" ]]; then
    echo "REFUSING: $port is the production port" >&2
    exit 2
  fi
done

BUILD=1
TESTS=1
PLAYWRIGHT_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reuse-build|--only-tests) BUILD=0 ;;
    --no-tests) TESTS=0 ;;
    --) shift; PLAYWRIGHT_ARGS=("$@"); break ;;
    *) PLAYWRIGHT_ARGS+=("$1") ;;
  esac
  shift
done

mkdir -p "$RUN_DIR"
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] run=$RUN_DIR backend=$BACKEND_PORT frontend=$FRONTEND_PORT sha=$(git -C "$REPO" rev-parse --short HEAD)"

python3 "$HERE/stack.py" prepare --reset \
  --backend-port "$BACKEND_PORT" --frontend-port "$FRONTEND_PORT" --run-dir "$RUN_DIR"

if [[ "$BUILD" == "1" ]]; then
  python3 "$HERE/stack.py" build \
    --backend-port "$BACKEND_PORT" --frontend-port "$FRONTEND_PORT" --run-dir "$RUN_DIR" --dist-dir "$DIST_DIR"
fi

FIXTURE_CMD=(
  uv run --python 3.11 --with-requirements "$REPO/backend/requirements.txt"
  python "$HERE/build_fixture.py"
  --api "http://127.0.0.1:$BACKEND_PORT"
  --database-url "sqlite:///$RUN_DIR/accept.db"
  --jwt-secret "$JWT_SECRET"
  --manifest "$RUN_DIR/fixture.json"
)

if [[ "$TESTS" == "1" ]]; then
  cd "$REPO/frontend"
  E2E_BASE_URL="http://127.0.0.1:$FRONTEND_PORT" \
  E2E_API_BASE_URL="http://127.0.0.1:$BACKEND_PORT" \
  E2E_FIXTURE_MANIFEST="$RUN_DIR/fixture.json" \
  python3 "$HERE/stack.py" serve \
    --backend-port "$BACKEND_PORT" --frontend-port "$FRONTEND_PORT" --run-dir "$RUN_DIR" --dist-dir "$DIST_DIR" \
    -- bash "$HERE/run_inside.sh" "${PLAYWRIGHT_ARGS[@]}"
else
  python3 "$HERE/stack.py" serve \
    --backend-port "$BACKEND_PORT" --frontend-port "$FRONTEND_PORT" --run-dir "$RUN_DIR" --dist-dir "$DIST_DIR" \
    -- "${FIXTURE_CMD[@]}"
fi
