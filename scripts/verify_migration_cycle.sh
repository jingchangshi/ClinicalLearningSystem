#!/usr/bin/env bash
# R8.3 migration acceptance: upgrade -> downgrade -> upgrade on an ISOLATED database.
#
# It never touches a real database: DATABASE_URL is pointed at a fresh temporary
# SQLite file for every step, so the acceptance can be re-run at any time. The
# output is the evidence record (see
# docs/teaching_grant_2026/evidence/E2_platform/MIGRATION_ACCEPTANCE.md).
#
#   scripts/verify_migration_cycle.sh
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/clinpath-migration-acceptance.XXXXXX")"
DB="$WORK/acceptance.db"
LOG="$WORK/migration_cycle.log"
export DATABASE_URL="sqlite:///$DB"
export CLINPATH_ENV=development
UV=(uv run --python 3.11 --with-requirements requirements.txt)
cd "$BACKEND"

run() {
  printf '\n$ %s\n' "$*" | tee -a "$LOG"
  "$@" 2>&1 | tee -a "$LOG"
}
step() { printf '\n=== %s ===\n' "$*" | tee -a "$LOG"; }

step "isolated database: $DB (temporary; no other database is read or written)"

step "1. upgrade to 20261018_07 (before the assessment revisions)"
run "${UV[@]}" alembic upgrade 20261018_07
run "${UV[@]}" alembic current

step "2. seed the pre-existing training rows"
run "${UV[@]}" python tools/migration_acceptance.py seed --db "$DB"

step "3. dump the training data BEFORE the assessment migrations"
run "${UV[@]}" python tools/migration_acceptance.py dump --db "$DB" --out "$WORK/dump_pre_assessment.json"

step "4. upgrade head"
run "${UV[@]}" alembic upgrade head
run "${UV[@]}" alembic current
run "${UV[@]}" python tools/migration_acceptance.py schema --db "$DB" --out "$WORK/schema_after_upgrade.json"
run "${UV[@]}" python tools/migration_acceptance.py dump --db "$DB" --out "$WORK/dump_after_upgrade.json"
run "${UV[@]}" python tools/migration_acceptance.py compare --before "$WORK/dump_pre_assessment.json" --after "$WORK/dump_after_upgrade.json"

step "5. downgrade to 20261018_07"
run "${UV[@]}" alembic downgrade 20261018_07
run "${UV[@]}" alembic current
run "${UV[@]}" python tools/migration_acceptance.py tables --db "$DB"
run "${UV[@]}" python tools/migration_acceptance.py dump --db "$DB" --out "$WORK/dump_after_downgrade.json"
run "${UV[@]}" python tools/migration_acceptance.py compare --before "$WORK/dump_pre_assessment.json" --after "$WORK/dump_after_downgrade.json"

step "6. upgrade head again"
run "${UV[@]}" alembic upgrade head
run "${UV[@]}" alembic current
run "${UV[@]}" python tools/migration_acceptance.py schema --db "$DB" --out "$WORK/schema_after_reupgrade.json"
run "${UV[@]}" python tools/migration_acceptance.py dump --db "$DB" --out "$WORK/dump_after_reupgrade.json"
run "${UV[@]}" python tools/migration_acceptance.py compare --before "$WORK/dump_pre_assessment.json" --after "$WORK/dump_after_reupgrade.json"
run "${UV[@]}" python tools/migration_acceptance.py compare --before "$WORK/dump_after_upgrade.json" --after "$WORK/dump_after_reupgrade.json"

step "7. migrated schema vs a fresh create_all install of the same models"
run env DATABASE_URL="sqlite:///$WORK/fresh_create_all.db" "${UV[@]}" python -c \
  "from app.database import Base, engine; import app.models, app.assessment_models; Base.metadata.create_all(engine)"
run "${UV[@]}" python tools/migration_acceptance.py schema --db "$WORK/fresh_create_all.db" --out "$WORK/schema_fresh_install.json"
run python3 "$REPO_ROOT/scripts/compare_schema_json.py" "$WORK/schema_after_reupgrade.json" "$WORK/schema_fresh_install.json"

step "acceptance complete: artifacts kept in $WORK"
run echo "log: $LOG"
