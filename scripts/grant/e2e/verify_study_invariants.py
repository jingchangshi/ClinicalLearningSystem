"""Verify the 7-cohort / 49-student / 98-sitting study invariants on a live stack.

This checks the *product's own records* (allocations, sittings, exports) rather
than re-deriving them from the fixture: the point is to prove the running system
enforces the design, not that the harness can do arithmetic.

Invariants (docs/goal/teaching-1018-final.md R4.2, R4.5, R4.6):
  I1  exactly 7 cohorts, 7 enrolled students each, 49 distinct students
  I2  every batch of 7 sits in ONE arm; 3 ClinPath + 4 CBL, and the arms are a
      subset of the C(7,3)=35 legal allocations
  I3  form order was frozen strictly before the group draw, and the record
      verifies against its own content hash
  I4  98 sittings (49 students x T0/T1), one live attempt per (student, timepoint)
  I5  each student's T0/T1 use two DIFFERENT forms, chosen by their frozen X/Y
      order (X: A01 then A02; Y: A02 then A01), and the order is stable within a
      student
  I6  within each cohort, form order is split about 4/3
  I7  the export carries study codes only -- no name, no student number -- and
      `data_origin` is never `real_study` for this synthetic fixture

Exit code 0 only when every invariant holds; the output is the evidence.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from build_fixture import ADMIN_PASSWORD, ORIGIN, Api  # noqa: E402

FORM_BY_ORDER = {"X": {"T0": "A01", "T1": "A02"}, "Y": {"T0": "A02", "T1": "A01"}}
N_CLINPATH, N_COHORTS = 3, 7
LEGAL_ALLOCATIONS = {
    frozenset(combo) for combo in itertools.combinations(range(N_COHORTS), N_CLINPATH)
}


class Checker:
    def __init__(self) -> None:
        self.results: list[dict] = []

    def check(self, name: str, ok: bool, detail: object) -> None:
        self.results.append({"invariant": name, "ok": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    @property
    def ok(self) -> bool:
        return all(row["ok"] for row in self.results)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8400")
    parser.add_argument("--manifest", default=None, help="fixture.json, for the study-code set")
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--database", default=None, help="throwaway SQLite path (read-only) for the I3 record body")
    args = parser.parse_args()
    api = Api(args.api).login("test_admin", ADMIN_PASSWORD)
    c = Checker()

    cohorts = [row for row in api.ok("GET", "/api/assessments/admin/cohorts") if row["data_origin"] == ORIGIN]
    cohorts.sort(key=lambda row: row["cohort_code"])
    enrolled = {row["cohort_code"]: row["enrolled"] for row in cohorts}

    # I1 -- 7 batches of 7, 49 distinct students
    assignments = api.ok("GET", f"/api/assessments/admin/design/assignments?data_origin={ORIGIN}")
    per_cohort = Counter(row["cohort_code"] for row in assignments)
    students = {row["student_id"] for row in assignments}
    c.check("I1 seven cohorts of seven (49 distinct students)",
            len(cohorts) == 7 and all(n == 7 for n in per_cohort.values()) and len(students) == 49,
            {"cohorts": len(cohorts), "per_cohort": dict(per_cohort), "distinct_students": len(students)})

    # I2 -- whole-batch arms: 3 ClinPath + 4 CBL, a legal C(7,3) allocation
    arm_by_cohort: dict[str, set[str]] = defaultdict(set)
    for row in assignments:
        arm_by_cohort[row["cohort_code"]].add(row["study_group"])
    split = sorted(code for code, arms in arm_by_cohort.items() if len(arms) > 1)
    clinpath = sorted(code for code, arms in arm_by_cohort.items() if arms == {"CLINPATH"})
    cbl = sorted(code for code, arms in arm_by_cohort.items() if arms == {"CBL"})
    indices = frozenset(i for i, row in enumerate(cohorts) if row["cohort_code"] in clinpath)
    c.check("I2 each batch is one arm; 3 ClinPath + 4 CBL; a legal C(7,3) allocation",
            not split and len(clinpath) == 3 and len(cbl) == 4 and indices in LEGAL_ALLOCATIONS,
            {"clinpath": clinpath, "cbl": cbl, "split_batches": split,
             "legal_allocation_index": sorted(indices), "of": len(LEGAL_ALLOCATIONS)})

    # I3 -- form order frozen strictly before the group draw.
    # Compare the records' OWN timestamps: `executed_at` is the DB row time and is
    # truncated to whole seconds, while the frozen/drawn instants carry microseconds.
    allocations = api.ok("GET", "/api/assessments/admin/allocations")
    by_kind = {row["kind"]: row for row in allocations}
    cluster_record = by_kind["cluster_group"]
    order_version = by_kind["form_order"]["allocation_version"]
    # The form-order record body is not part of the list payload; the cluster record
    # binds to it by hash, and the server refuses a draw without a verified order.
    order_frozen_at = by_kind["form_order"]["executed_at"]
    drawn_at = cluster_record["record"]["drawn_at"]
    bound_hash = cluster_record["record"]["form_order_hash"]
    # The form-order record BODY (seed, frozen_at, assignments) is not returned by any
    # endpoint, so the strict microsecond comparison is read from the product's own
    # stored record. This is a read-only check of the same database the API serves.
    stored_frozen_at = None
    if args.database:
        import sqlite3

        conn = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT record_json FROM study_allocations WHERE kind = 'form_order' AND data_origin = ?",
                (ORIGIN,),
            ).fetchone()
            stored_frozen_at = json.loads(row[0])["frozen_at"] if row else None
        finally:
            conn.close()
    strict_order = stored_frozen_at is not None and stored_frozen_at < drawn_at
    c.check("I3 form order frozen strictly before the group draw",
            strict_order and bound_hash == by_kind["form_order"]["content_hash"]
            and cluster_record["mode"] == "randomized",
            {"form_order_allocation": order_version, "form_order_frozen_at": stored_frozen_at,
             "cluster_drawn_at": drawn_at, "form_order_hash_bound": bound_hash[:12],
             "mode": cluster_record["mode"],
             "api_gap": "no endpoint returns the form-order record body (seed/frozen_at/assignments)",
             "source": "study_allocations.record_json, opened read-only" if args.database else "DB not supplied"})

    # I4 -- 98 sittings, one live attempt per (student, timepoint)
    sittings = [row for row in api.ok("GET", "/api/assessments/admin/sittings")
                if row["data_origin"] == ORIGIN and row["status"] != "voided"]
    keys = Counter((row["student_id"], row["timepoint"]) for row in sittings)
    c.check("I4 98 live sittings, one per (student, timepoint)",
            len(sittings) == 98 and set(keys.values()) == {1}
            and {row["timepoint"] for row in sittings} == {"T0", "T1"},
            {"sittings": len(sittings), "duplicates": [k for k, n in keys.items() if n > 1],
             "timepoints": sorted({row["timepoint"] for row in sittings})})

    # I5 -- two different forms per student, following the frozen X/Y order
    raw_codes = {row["id"]: row["code"] for row in api.ok("GET", "/api/assessments/forms/admin/all")}

    def form_label(code: str) -> str:
        """'TEST-CASE-A01-UA-V1' -> 'A01': the study only cares which of the two forms."""
        for label in ("A01", "A02"):
            if f"-{label}-" in code or code.endswith(label):
                return label
        return code

    forms = {form_id: form_label(code) for form_id, code in raw_codes.items()}
    # The sitting list does not repeat the form order; the design assignment does.
    orders_from_assignments = {row["student_id"]: row["form_order"] for row in assignments}
    by_student_order: dict[int, str | None] = {}
    by_student: dict[int, dict[str, dict]] = defaultdict(dict)
    for row in sittings:
        by_student[row["student_id"]][row["timepoint"]] = row
    mismatches, missing = [], []
    for student_id, pair in by_student.items():
        if set(pair) != {"T0", "T1"}:
            missing.append(student_id)
            continue
        order = by_student_order.get(student_id) or pair["T0"].get("form_order")
        if order is None:
            order = orders_from_assignments.get(student_id)
        if order is None:
            missing.append(student_id)
            continue
        for timepoint in ("T0", "T1"):
            want = FORM_BY_ORDER[order][timepoint]
            got = forms.get(pair[timepoint]["form_id"])
            if got != want:
                mismatches.append({"student_id": student_id, "timepoint": timepoint,
                                   "order": order, "want": want, "got": got})
    different = all(forms[p["T0"]["form_id"]] != forms[p["T1"]["form_id"]] for p in by_student.values())
    c.check("I5 T0/T1 use two different forms following the frozen X/Y order",
            not mismatches and not missing and different,
            {"students": len(by_student), "mismatches": mismatches[:5], "missing_timepoint": missing,
             "different_forms": different})

    # I6 -- within each cohort the order split is about 4/3
    orders_per_cohort: dict[str, Counter] = defaultdict(Counter)
    for row in assignments:
        orders_per_cohort[row["cohort_code"]][row["form_order"]] += 1
    splits = {code: dict(counts) for code, counts in orders_per_cohort.items()}
    c.check("I6 form order split ~4/3 inside every cohort",
            all(sorted(counts.values()) == [3, 4] for counts in orders_per_cohort.values()),
            splits)

    # I7 -- the export is coded, and synthetic data never claims to be real
    export = api.ok("GET", f"/api/assessments/admin/export?data_origin={ORIGIN}")
    records = export["records"]
    bad_keys = sorted({key for row in records for key in row
                       if key in {"student_id", "student_name", "student_no", "name"}})
    code_pattern_ok = all(isinstance(row["study_student_code"], str) and row["study_student_code"].startswith("S")
                          for row in records)
    origins = sorted({row["data_origin"] for row in records})
    c.check("I7 export carries study codes only, data_origin never real_study",
            not bad_keys and code_pattern_ok and origins == [ORIGIN] and len(records) == 98,
            {"records": len(records), "forbidden_keys": bad_keys, "origins": origins,
             "distinct_codes": len({row["study_student_code"] for row in records})})

    payload = {"data_origin": ORIGIN, "all_ok": c.ok, "checks": c.results}
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
    print(f"\n{'ALL INVARIANTS HOLD' if c.ok else 'INVARIANT FAILURE'} ({sum(r['ok'] for r in c.results)}/{len(c.results)})")
    return 0 if c.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
