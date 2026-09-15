#!/usr/bin/env python3
"""Measure SQLite write health while the application is under load.

    python3 loadtest/sqlite_write_probe.py --db ~/.local/state/clinpath-staging/staging.db --seconds 180

The question this answers is narrow and worth measuring directly: with the
deployment's own PRAGMAs (WAL + busy_timeout=5000) and a concurrent read load,
does a *writer* still get through, and how slow does it get? "database is
locked" is the failure this probe counts.

Use it against a disposable staging copy — it creates a scratch table.
"""

import argparse
import sqlite3
import statistics
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--seconds", type=float, default=180.0)
    parser.add_argument("--interval-ms", type=int, default=100)
    parser.add_argument("--busy-timeout-ms", type=int, default=5000)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    path = Path(args.db).expanduser()
    if not path.exists():
        print(f"no such database: {path}", file=sys.stderr)
        return 2

    connection = sqlite3.connect(str(path), timeout=args.busy_timeout_ms / 1000)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(f"PRAGMA busy_timeout={args.busy_timeout_ms}")
    connection.execute("CREATE TABLE IF NOT EXISTS loadtest_write_probe (id INTEGER PRIMARY KEY, at TEXT)")
    connection.commit()

    latencies: list[float] = []
    failures: dict[str, int] = {}
    deadline = time.monotonic() + args.seconds
    while time.monotonic() < deadline:
        started = time.monotonic()
        try:
            connection.execute("INSERT INTO loadtest_write_probe (at) VALUES (datetime('now'))")
            connection.commit()
            latencies.append((time.monotonic() - started) * 1000)
        except sqlite3.Error as error:
            failures[type(error).__name__] = failures.get(type(error).__name__, 0) + 1
            if args.verbose:
                print(f"write failed: {error}", file=sys.stderr)
            try:
                connection.rollback()
            except sqlite3.Error:
                pass
        time.sleep(args.interval_ms / 1000)

    connection.execute("DELETE FROM loadtest_write_probe")
    connection.commit()
    connection.close()

    ordered = sorted(latencies)
    print(f"writes         : {len(latencies)}")
    print(f"write failures : {sum(failures.values())} {failures or ''}")
    if ordered:
        print(f"write latency  : p50={round(statistics.median(ordered))}ms "
              f"p95={round(ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))])}ms "
              f"max={round(ordered[-1])}ms")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
