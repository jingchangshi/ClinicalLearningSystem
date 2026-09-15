#!/usr/bin/env bash
# Read-only production triage: does the running deployment match this checkout?
#
#   ./scripts/verify_deploy.sh
#
# Answers the question "which code is the browser actually running?" without
# touching data, restarting services, or printing any secret.
#
# Every required check below feeds the final exit status: a green-looking report
# with a dead frontend or an unreachable public entry must not exit 0.
set -uo pipefail

REPO_ROOT="${CLINPATH_REPO_ROOT:-/home/jcshi/workspace/clinical_learning_system}"
# The pilot entry is HTTPS (Cloudflare tunnel -> 127.0.0.1:8101). Override with
# CLINPATH_PUBLIC_BASE for a deployment that still serves plain HTTP on 8101.
PUBLIC_BASE="${CLINPATH_PUBLIC_BASE:-https://clinpath.1031989.xyz}"
INTERNAL="${CLINPATH_INTERNAL_API:-http://127.0.0.1:8100}"
failures=0

pass() { echo "OK: $*"; }
fail() { echo "FAIL: $*"; failures=$((failures + 1)); }

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
  unit_state="$(systemctl --user is-active "$unit" 2>/dev/null || true)"
  printf '%-26s: %s\n' "$unit" "${unit_state:-unknown}"
  if [ "$unit_state" != "active" ]; then
    fail "$unit is ${unit_state:-unknown}, not active"
  fi
done

echo
echo "== running backend =="
version_json="$(curl -fsS "$INTERNAL/api/system/version" 2>/dev/null)"
if [ -z "$version_json" ]; then
  fail "$INTERNAL/api/system/version unreachable"
  running_sha=""
  running_dirty=""
  running_fingerprint=""
  running_schema=""
  running_env=""
else
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
fi

echo
echo "== verdict =="
if [ "$running_sha" != "$local_sha" ]; then
  fail "running commit ($running_sha) differs from this checkout ($local_sha)"
elif [ -n "$local_fingerprint" ] && [ "$running_fingerprint" != "$local_fingerprint" ]; then
  fail "running source differs from this checkout (restart/redeploy the backend)"
else
  pass "running backend matches this checkout (commit + source fingerprint)"
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
  fail "running schema revision (${running_schema:-unknown}) is not the migration head (${local_head:-unavailable})"
else
  pass "schema revision is at migration head"
fi

echo
echo "== public entry =="
check_public_page() {
  local label="$1" url="$2"
  local code
  code="$(curl -fsS -o /dev/null -m 15 -w '%{http_code}' "$url" 2>/dev/null || true)"
  printf '%-15s: %s\n' "$label" "${code:-unreachable}"
  if [ "$code" != "200" ]; then
    fail "$label $url returned ${code:-unreachable}, expected 200"
  fi
}
check_public_page home "$PUBLIC_BASE/"
check_public_page login "$PUBLIC_BASE/login"

public_health="$(curl -fsS -m 15 "$PUBLIC_BASE/api/health" 2>/dev/null || true)"
printf '%-15s: %s\n' "api proxy" "${public_health:-unreachable}"
if ! printf '%s' "$public_health" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  fail "$PUBLIC_BASE/api/health did not report a healthy backend through the proxy"
fi

echo
echo "== shared secret parity (values are never printed) =="
if ! python3 - "${CLINPATH_BACKEND_ENV:-$HOME/.config/clinpath/backend.env}" \
              "${CLINPATH_FRONTEND_ENV:-$HOME/.config/clinpath/frontend.env}" <<'PY'
import hashlib
import os
import sys

def secret_digest(path: str) -> str:
    if not os.path.exists(path):
        return "missing-file"
    for line in open(path):
        name, _, value = line.strip().partition("=")
        if name == "JWT_SECRET":
            if not value:
                return "empty"
            return hashlib.sha256(value.encode()).hexdigest()[:12]
    return "absent"

backend, frontend = sys.argv[1], sys.argv[2]
left, right = secret_digest(backend), secret_digest(frontend)
print(f"backend.env    : {left}")
print(f"frontend.env   : {right}")
if left == right and left not in {"missing-file", "empty", "absent"}:
    print("verdict        : MATCH (backend and frontend sign with the same secret)")
else:
    print("verdict        : MISMATCH - the proxy cannot verify backend cookies")
    sys.exit(1)
PY
then
  fail "JWT_SECRET parity is not MATCH"
fi

echo
echo "== summary =="
if [ "$failures" -gt 0 ]; then
  echo "DEPLOY VERIFICATION FAILED: $failures check(s) failed"
  exit 1
fi
echo "DEPLOY VERIFICATION PASSED: running $(git -C "$REPO_ROOT" rev-parse HEAD) is serving the public entry"
exit 0
