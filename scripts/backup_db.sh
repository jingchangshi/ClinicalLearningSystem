#!/usr/bin/env bash
# Snapshot the production SQLite database before any schema or data change.
# Uses the sqlite3 backup API so a concurrent writer (systemd service) cannot
# produce a torn copy of a WAL database.
set -euo pipefail

REPO_ROOT="/home/jcshi/workspace/clinical_learning_system"
DB_PATH="${CLINPATH_DB_PATH:-$REPO_ROOT/backend/clinical_learning.db}"
BACKUP_DIR="${CLINPATH_BACKUP_DIR:-$REPO_ROOT/backend/backups}"

if [ ! -f "$DB_PATH" ]; then
  echo "backup_db: no database at $DB_PATH, nothing to do" >&2
  exit 0
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="$BACKUP_DIR/clinical_learning-$STAMP.db"

python3 - "$DB_PATH" "$TARGET" <<'PY'
import sqlite3
import sys

source, target = sys.argv[1], sys.argv[2]
source_connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
try:
    target_connection = sqlite3.connect(target)
    try:
        source_connection.backup(target_connection)
    finally:
        target_connection.close()
finally:
    source_connection.close()
print(f"backup_db: wrote {target}")
PY
