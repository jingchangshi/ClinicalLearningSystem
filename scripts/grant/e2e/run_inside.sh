#!/usr/bin/env bash
# Runs *inside* the stack: build the synthetic fixture, then Playwright.
# Invoked by run_acceptance.sh; expects E2E_* env from stack.py's serve action.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
RUN_DIR="${E2E_RUN_DIR:-/tmp/clinpath-e2e}"
BACKEND_PORT="${E2E_BACKEND_PORT:-8400}"
JWT_SECRET="test-only-jwt-secret-8f3a1c"

uv run --python 3.11 --with-requirements "$REPO/backend/requirements.txt" \
  python "$HERE/build_fixture.py" \
  --api "http://127.0.0.1:$BACKEND_PORT" \
  --database-url "sqlite:///$RUN_DIR/accept.db" \
  --jwt-secret "$JWT_SECRET" \
  --manifest "$RUN_DIR/fixture.json"

cd "$REPO/frontend"
# Credentials for the disposable stack. student1..3 come from app.seed_data with
# SEED_DEMO_STUDENT_PASSWORD; the staff accounts were provisioned by the fixture.
export E2E_STUDENT_USERNAME="${E2E_STUDENT_USERNAME:-student1}"
export E2E_STUDENT_PASSWORD="${E2E_STUDENT_PASSWORD:-test-student-pw}"
export E2E_TEACHER_USERNAME="${E2E_TEACHER_USERNAME:-test_teacher_a}"
export E2E_TEACHER_PASSWORD="${E2E_TEACHER_PASSWORD:-test-teacher-pw}"
export E2E_ADMIN_USERNAME="${E2E_ADMIN_USERNAME:-test_admin}"
export E2E_ADMIN_PASSWORD="${E2E_ADMIN_PASSWORD:-test-admin-pw}"
export E2E_RATER_USERNAME="${E2E_RATER_USERNAME:-test_teacher_a}"
export E2E_RATER_PASSWORD="${E2E_RATER_PASSWORD:-test-teacher-pw}"
exec npx playwright test "$@"
