#!/usr/bin/env bash
# Read-only production triage: does the running deployment match this checkout?
#
#   ./scripts/verify_deploy.sh
#
# Answers the question "which code is the browser actually running?" without
# touching data, restarting services, or printing any secret.
set -uo pipefail

REPO_ROOT="/home/jcshi/workspace/clinical_learning_system"
PUBLIC_BASE="${CLINPATH_PUBLIC_BASE:-http://129.153.118.58:8101}"
INTERNAL="${CLINPATH_INTERNAL_API:-http://127.0.0.1:8100}"
status=0

echo "== git =="
local_sha="$(git -C "$REPO_ROOT" rev-parse HEAD)"
dirty="$(git -C "$REPO_ROOT" status --porcelain | wc -l | tr -d ' ')"
echo "HEAD           : $local_sha"
echo "uncommitted    : $dirty file(s)"

echo
echo "== local source fingerprint =="
local_fingerprint="$(
  cd "$REPO_ROOT/backend" && python3 -c \
    "from app.core.source_fingerprint import compute_source_fingerprint as f; print(f())" 2>/dev/null
)"
echo "expected       : ${local_fingerprint:-unavailable}"

echo
echo "== services =="
for unit in clinical-backend.service clinical-frontend.service; do
  printf '%-26s: %s\n' "$unit" "$(systemctl --user is-active "$unit")"
done

echo
echo "== running backend =="
version_json="$(curl -fsS "$INTERNAL/api/system/version" 2>/dev/null)"
if [ -z "$version_json" ]; then
  echo "FAIL: $INTERNAL/api/system/version unreachable"
  exit 1
fi
running_sha="$(printf '%s' "$version_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['git_sha'])")"
running_dirty="$(printf '%s' "$version_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['git_dirty'])")"
running_fingerprint="$(printf '%s' "$version_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['backend_source_fingerprint'])")"
running_schema="$(printf '%s' "$version_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['schema_revision'])")"
running_env="$(printf '%s' "$version_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['environment'])")"
echo "git_sha        : $running_sha"
echo "git_dirty      : $running_dirty"
echo "fingerprint    : $running_fingerprint"
echo "schema         : $running_schema"
echo "environment    : $running_env"

echo
echo "== verdict =="
if [ "$running_sha" != "$local_sha" ]; then
  echo "FAIL: running commit differs from this checkout"
  status=1
elif [ -n "$local_fingerprint" ] && [ "$running_fingerprint" != "$local_fingerprint" ]; then
  echo "FAIL: running source differs from this checkout (restart/redeploy the backend)"
  status=1
else
  echo "OK: running backend matches this checkout (commit + source fingerprint)"
fi
# Migration head is derived by scanning the versions directory, so this check
# needs no alembic install and no database connection.
local_head="$(
  cd "$REPO_ROOT/backend" && python3 -c "
import os, re
directory = 'alembic/versions'
revisions, referenced = set(), set()
for name in os.listdir(directory):
    if not name.endswith('.py'):
        continue
    text = open(os.path.join(directory, name)).read()
    revision = re.search(r'^revision\s*=\s*[\'\"]([^\'\"]+)', text, re.M)
    if not revision:
        continue
    revisions.add(revision.group(1))
    down = re.search(r'^down_revision\s*=\s*([^\n]+)', text, re.M)
    if down:
        referenced.update(re.findall(r'[\'\"]([^\'\"]+)[\'\"]', down.group(1)))
heads = sorted(revisions - referenced)
print(heads[0] if len(heads) == 1 else ','.join(heads))
" 2>/dev/null
)"
echo "expected head  : ${local_head:-unavailable}"
if [ -z "$local_head" ] || [ "$running_schema" != "$local_head" ]; then
  echo "FAIL: running schema revision is not the migration head"
  status=1
else
  echo "OK: schema revision is at migration head"
fi

echo
echo "== public entry =="
printf 'home           : %s\n' "$(curl -fsS -o /dev/null -w '%{http_code}' "$PUBLIC_BASE/" || echo unreachable)"
printf 'login          : %s\n' "$(curl -fsS -o /dev/null -w '%{http_code}' "$PUBLIC_BASE/login" || echo unreachable)"
printf 'api proxy      : %s\n' "$(curl -fsS "$PUBLIC_BASE/api/health" || echo unreachable)"

exit "$status"
