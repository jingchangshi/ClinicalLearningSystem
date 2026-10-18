#!/usr/bin/env bash
# The complete acceptance run, in one stack lifetime, with logs kept as evidence.
#
#   ./run_full_acceptance.sh [run-label]
#
# Produces, under $RUN_DIR (default /tmp/clinpath-e2e):
#   fixture.json          the synthetic study the run was built on
#   invariants.json       7/7 study invariants
#   logs/                 alembic, seed, backend, frontend, build, each suite
# and writes screenshots into docs/teaching_grant_2026/evidence/E2_platform/screenshots/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
LABEL="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="${E2E_RUN_DIR:-/tmp/clinpath-e2e}"
BACKEND_PORT="${E2E_BACKEND_PORT:-8400}"
FRONTEND_PORT="${E2E_FRONTEND_PORT:-8401}"
DIST_DIR="${E2E_DIST_DIR:-.next-accept}"
LOGS="$RUN_DIR/logs"
JWT_SECRET="test-only-jwt-secret-8f3a1c"
SHOTS="$REPO/docs/teaching_grant_2026/evidence/E2_platform/screenshots"

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  [[ "$port" == "8100" || "$port" == "8101" ]] && { echo "REFUSING production port $port" >&2; exit 2; }
done

mkdir -p "$RUN_DIR" "$LOGS" "$SHOTS"
SHA="$(git -C "$REPO" rev-parse HEAD)"
SHORT="$(git -C "$REPO" rev-parse --short HEAD)"
STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[$STARTED] label=$LABEL sha=$SHORT backend=$BACKEND_PORT frontend=$FRONTEND_PORT"

python3 "$HERE/stack.py" prepare --reset \
  --backend-port "$BACKEND_PORT" --frontend-port "$FRONTEND_PORT" --run-dir "$RUN_DIR"

python3 "$HERE/stack.py" build \
  --backend-port "$BACKEND_PORT" --frontend-port "$FRONTEND_PORT" --run-dir "$RUN_DIR" --dist-dir "$DIST_DIR"

cat > "$LOGS/run_env.json" <<JSON
{
  "label": "$LABEL",
  "git_sha": "$SHA",
  "git_sha_short": "$SHORT",
  "started_at_utc": "$STARTED",
  "backend_port": $BACKEND_PORT,
  "frontend_port": $FRONTEND_PORT,
  "dist_dir": "$DIST_DIR",
  "database": "sqlite:///$RUN_DIR/accept.db",
  "llm_api_key": "deliberately empty (keyless: rule fallback)",
  "data_origin": "pilot_test",
  "label_of_data": "SYNTHETIC / SIMULATED_NOT_HUMAN"
}
JSON

python3 "$HERE/stack.py" serve --backend-port "$BACKEND_PORT" --frontend-port "$FRONTEND_PORT" --run-dir "$RUN_DIR" --dist-dir "$DIST_DIR" \
  -- bash "$HERE/run_all_inside.sh" "$LOGS" "$RUN_DIR" "$BACKEND_PORT" "$FRONTEND_PORT" "$SHOTS" "$JWT_SECRET" "$LABEL" \
  | tee "$LOGS/suite_output.log"
