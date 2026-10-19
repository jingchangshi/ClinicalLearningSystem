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

# The demo teaching dataset comes FIRST, and deliberately so: the operator tool
# behind the plan refuses to touch a database holding students it cannot classify
# as demo data, and the 7x7 fixture is exactly 49 of those. It is offline and
# keyless -- every score is the rule engine's, and demo_dataset.json records that
# provenance rather than calling it AI.
step "demo dataset: synthetic, rule-fallback, keyless" demo_dataset.log \
  "${PY[@]}" "$HERE/build_demo_dataset.py" \
  --database-url "sqlite:///$RUN_DIR/accept.db" \
  --api "http://127.0.0.1:$BACKEND_PORT" \
  --manifest "$RUN_DIR/demo_dataset.json"

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

# This stack is keyless by construction (stack.build_env blanks every provider
# key), so the honest expectation for a scored case IS the rule fallback. The
# spec that asserts that badge is opt-in precisely because it describes this
# deployment shape, not a general one.
export E2E_EXPECT_FALLBACK=1

# This stack is disposable (throwaway /tmp database, torn down by stack.py), which
# is exactly the condition the mutating suite asks for. Leaving it off used to
# skip eleven tests that this environment can run, including the only browser
# coverage of the five-stage independent exam and the keyless fallback badge.
export E2E_RUN_MUTATING=1

# The independent exam is sat by a *demo* student: an exam sitting is not a
# ClinPath formative intervention, so a study student is the wrong account for it
# -- and under the study access policy most batches cannot train anyway.
export E2E_EXAM_STUDENT_USERNAME="${E2E_EXAM_STUDENT_USERNAME:-student2}"
export E2E_EXAM_STUDENT_PASSWORD="${E2E_EXAM_STUDENT_PASSWORD:-test-student-pw}"

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

# Screenshots are captured into the run dir, not straight into the tracked
# evidence directory: a routine verification run must not churn committed
# evidence. Publishing is opt-in (E2E_PUBLISH_SHOTS=1).
export E2E_SHOTS_DIR="$RUN_DIR/screenshots"
mkdir -p "$E2E_SHOTS_DIR"
step "playwright: E2 evidence screenshots" screenshots.log \
  npx playwright test tests/e2e/evidence-screenshots.spec.ts --reporter=list

if [[ "${E2E_PUBLISH_SHOTS:-0}" == "1" ]]; then
  mkdir -p "$SHOTS"
  cp "$E2E_SHOTS_DIR"/*.png "$SHOTS"/
  echo "published $(ls "$E2E_SHOTS_DIR"/*.png | wc -l) screenshots to $SHOTS"
fi

echo
if [[ "$failures" -eq 0 ]]; then
  echo "ALL STEPS PASSED ($LABEL)"
else
  echo "$failures STEP(S) FAILED ($LABEL)"
fi
exit "$failures"
