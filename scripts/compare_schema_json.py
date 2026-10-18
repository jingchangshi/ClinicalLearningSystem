#!/usr/bin/env python3
"""Compare two schema JSONs produced by ``tools/migration_acceptance.py schema``.

SQLite's batch-mode table rebuilds reorder FK/UNIQUE clauses, quote the table name
and spell out a server default for columns a migration had to add with one. None of
that changes what the database enforces, so it is normalised away; a lost NOT NULL,
UNIQUE, index or column is reported and the exit code is 1.

    scripts/compare_schema_json.py BEFORE.json AFTER.json
"""
import json
import re
import sys


def normalise(ddl: str) -> str:
    text = ddl.replace('"', "")
    text = re.sub(r"CONSTRAINT fk_\w+ ", "", text)
    text = re.sub(r" DEFAULT '[^']*'", "", text)
    head, _, body = text.partition("(")
    if not body:
        return " ".join(text.split())
    clauses = sorted(re.split(r",(?![^()]*\))", body.rsplit(")", 1)[0]))
    return head.strip() + " (" + ", ".join(c.strip() for c in clauses) + ")"


def main() -> int:
    before = json.load(open(sys.argv[1], encoding="utf-8"))
    after = json.load(open(sys.argv[2], encoding="utf-8"))
    problems = []
    for key in sorted(set(before) | set(after)):
        if key not in before:
            print(f"ADDED   {key}")
        elif key not in after:
            problems.append(key)
            print(f"MISSING {key}")
        elif normalise(before[key]) == normalise(after[key]):
            print(f"same    {key}")
        else:
            problems.append(key)
            print(f"CHANGED {key}\n  before: {normalise(before[key])}\n  after : {normalise(after[key])}")
    print(f"\nobjects: {len(before)} -> {len(after)}; differing: {len(problems)}")
    if problems:
        print("SCHEMA MISMATCH: " + ", ".join(problems))
        return 1
    print("schema equivalent (modulo clause order, quoting and server defaults)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
