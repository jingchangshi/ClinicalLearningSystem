#!/usr/bin/env bash
# Runs inside `stack.py serve`: fixture → invariants → Playwright suites → screenshots.
# Every step writes its own log; a failing step does not stop the later evidence
# steps, but the script exits non-zero so the caller sees the failure.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
LOGS="$1"; RUN_DIR="$2"; BACKEND_PORT="$3"; FRONTEND_PORT="$4"; SHOTS="$5"; JWT_SECRET="$6"; LABEL="$7"
mkdir -p "$LOGS" "$SHOTS"
PY=(uv run --python 3.11 --with-requirements "$REPO/backend/requirements.txt" python)

failures=0
step() {  # step <name> <logfile> <command...>
  local name="$1" log="$2"; shift 2
  echo "=== $name ==="
  if "$@" > "$LOGS/$log" 2>&1; then
    echo "PASS $name  (log: $LOGS/$log)"
  else
    echo "FAIL $name  (log: $LOGS/$log)"
    tail -25 "$LOGS/$log"
    failures=$((failures + 1))
  fi
}

step "fixture: synthetic 7x7 study" fixture.log \
  "${PY[@]}" "$HERE/build_fixture.py" \
  --api "http://127.0.0.1:$BACKEND_PORT" \
  --database-url "sqlite:///$RUN_DIR/accept.db" \
  --jwt-secret "$JWT_SECRET" --manifest "$RUN_DIR/fixture.json"

step "invariants: 7 cohorts / 49 students / 98 sittings" invariants.log \
  "${PY[@]}" "$HERE/verify_study_invariants.py" \
  --api "http://127.0.0.1:$BACKEND_PORT" --database "$RUN_DIR/accept.db" \
  --json-out "$RUN_DIR/invariants.json"

cd "$REPO/frontend"
export E2E_BASE_URL="http://127.0.0.1:$FRONTEND_PORT"
export E2E_FIXTURE_MANIFEST="$RUN_DIR/fixture.json"
export E2E_STUDENT_USERNAME=student1 E2E_STUDENT_PASSWORD=test-student-pw
export E2E_TEACHER_USERNAME=test_teacher_a E2E_TEACHER_PASSWORD=test-teacher-pw
export E2E_ADMIN_USERNAME=test_admin E2E_ADMIN_PASSWORD=test-admin-pw
export E2E_RATER_USERNAME=test_teacher_a E2E_RATER_PASSWORD=test-teacher-pw

# The R8.2 flow runs FIRST and alone: it produces the training evidence that the
# AI-audit assertion in teacher.spec.ts reads. Playwright interleaves files when
# it has several workers, and the audit writer is asynchronous, so running them
# together made teacher.spec.ts race the audit flush (an intermittently empty
# audit table, not a product bug).
step "playwright: R8.2 research flow" playwright_research.log \
  npx playwright test tests/e2e/research-flow.spec.ts --reporter=list --workers=1

# The pre-existing suite, unchanged. Excludes the screenshot spec: that runs
# after the functional suites so it captures their end state.
step "playwright: existing suite" playwright.log \
  npx playwright test --reporter=list --grep-invert "E2 evidence screenshots|R8.2 research flow"

export E2E_SHOTS_DIR="$SHOTS"
step "playwright: E2 evidence screenshots" screenshots.log \
  npx playwright test tests/e2e/evidence-screenshots.spec.ts --reporter=list

echo
if [[ "$failures" -eq 0 ]]; then
  echo "ALL STEPS PASSED ($LABEL)"
else
  echo "$failures STEP(S) FAILED ($LABEL)"
fi
exit "$failures"
