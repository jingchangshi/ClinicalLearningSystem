"""Cluster randomization of 7 whole cohorts: 3 ClinPath + 4 CBL.

Design (docs/goal/teaching-1018-final.md R4.2, R4.5):

* the unit is the whole cohort; C(7,3) = 35 allocations, each equiprobable;
* the draw is seeded and reproducible, and its record is immutable. There is no
  redraw API: the only way to get another record is a new call with a new seed, and
  the caller (persistence layer) must refuse to store a second one;
* form order (X/Y) is a SEPARATE random process that must be frozen BEFORE the
  group draw. ``draw_cluster_allocation`` therefore requires a verified
  ``FormOrderRecord`` frozen strictly earlier than the draw time.

The random stream is SHA-256 based with rejection sampling, so it does not depend on
the Python version's ``random`` implementation.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Mapping, Sequence

from . import (
    FORM_ORDERS,
    MODE_QUASI,
    MODE_RANDOMIZED,
    RandomizationOrderError,
    ResearchError,
)

ALGORITHM = "sha256-rejection-stream"
ALGORITHM_VERSION = "1"
N_COHORTS = 7
N_CLINPATH = 3
N_ALLOCATIONS = 35  # C(7, 3)

_PURPOSE_FORM_ORDER = "form_order"
_PURPOSE_CLUSTER = "cluster_allocation"


def _digest(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class _Stream:
    """Deterministic uniform integers from SHA-256(seed:purpose:counter)."""

    def __init__(self, seed: str, purpose: str):
        self._seed, self._purpose, self._counter = str(seed), purpose, 0

    def below(self, bound: int) -> int:
        if bound < 1:
            raise ResearchError("bound must be >= 1")
        limit = (1 << 64) // bound * bound
        while True:
            h = hashlib.sha256(f"{self._seed}:{self._purpose}:{self._counter}".encode()).digest()
            self._counter += 1
            value = int.from_bytes(h[:8], "big")
            if value < limit:
                return value % bound


def _parse_ts(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ResearchError(f"timestamp must be ISO-8601: {value!r}") from exc


def all_allocations(cohort_ids: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    """The 35 legal ClinPath cohort sets, in a fixed (lexicographic) order."""
    ids = tuple(sorted(cohort_ids))
    _check_cohorts(ids)
    return tuple(itertools.combinations(ids, N_CLINPATH))


def _check_cohorts(ids: Sequence[str]) -> None:
    if len(ids) != N_COHORTS or len(set(ids)) != N_COHORTS:
        raise ResearchError(f"exactly {N_COHORTS} distinct cohorts required, got {len(ids)}")


# ---------------------------------------------------------------- form order

@dataclass(frozen=True)
class FormOrderRecord:
    algorithm: str
    algorithm_version: str
    seed: str
    protocol_version: str
    executor: str
    frozen_at: str
    # ((student_code, cohort_id, form_order), ...) sorted by student code
    assignments: tuple[tuple[str, str, str], ...]
    content_hash: str

    def cohort_ids(self) -> tuple[str, ...]:
        return tuple(sorted({c for _, c, _ in self.assignments}))

    def to_dict(self) -> dict:
        return asdict(self)


def _form_order_payload(rec_fields: Mapping) -> dict:
    return {k: (list(map(list, v)) if k == "assignments" else v)
            for k, v in rec_fields.items() if k != "content_hash"}


def assign_form_orders(
    cohorts: Mapping[str, Sequence[str]],
    *,
    seed: str,
    protocol_version: str,
    executor: str,
    frozen_at: str,
) -> FormOrderRecord:
    """Assign X/Y inside each cohort (about 4/3 for 7 students), seeded and frozen.

    Which form gets the extra student is itself randomized per cohort. Dropouts are
    never reassigned: the record is the single source of truth.
    """
    _check_cohorts(tuple(cohorts))
    _parse_ts(frozen_at)
    stream = _Stream(seed, _PURPOSE_FORM_ORDER)
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for cohort_id in sorted(cohorts):
        codes = sorted(cohorts[cohort_id])
        if len(set(codes)) != len(codes) or seen & set(codes):
            raise ResearchError("student codes must be unique across cohorts")
        seen.update(codes)
        n = len(codes)
        n_x = n // 2 + (stream.below(2) if n % 2 else 0)  # 7 -> 3 or 4
        pool = list(codes)
        for i in range(n - 1, 0, -1):  # Fisher-Yates
            j = stream.below(i + 1)
            pool[i], pool[j] = pool[j], pool[i]
        x_set = set(pool[:n_x])
        rows.extend((c, cohort_id, "X" if c in x_set else "Y") for c in codes)
    rows.sort()
    fields = dict(
        algorithm=ALGORITHM, algorithm_version=ALGORITHM_VERSION, seed=str(seed),
        protocol_version=protocol_version, executor=executor, frozen_at=frozen_at,
        assignments=tuple(rows),
    )
    return FormOrderRecord(**fields, content_hash=_digest(_form_order_payload(fields)))


def verify_form_order_record(record: FormOrderRecord | Mapping) -> FormOrderRecord:
    """Re-derive the assignment from the seed and compare. Raises on any mismatch."""
    rec = _coerce_form_order(record)
    fields = {k: v for k, v in rec.to_dict().items()}
    if _digest(_form_order_payload(fields)) != rec.content_hash:
        raise RandomizationOrderError("form order record content hash mismatch")
    cohorts: dict[str, list[str]] = {}
    for code, cohort_id, _ in rec.assignments:
        cohorts.setdefault(cohort_id, []).append(code)
    again = assign_form_orders(cohorts, seed=rec.seed, protocol_version=rec.protocol_version,
                               executor=rec.executor, frozen_at=rec.frozen_at)
    if again.assignments != rec.assignments:
        raise RandomizationOrderError("form order assignment does not follow from the stored seed")
    return rec


def _coerce_form_order(record) -> FormOrderRecord:
    if isinstance(record, FormOrderRecord):
        return record
    d = dict(record)
    d["assignments"] = tuple(tuple(a) for a in d["assignments"])
    return FormOrderRecord(**d)


def form_order_balance(record: FormOrderRecord) -> dict[str, dict[str, int]]:
    """Per-cohort X/Y counts; every count must stay within 1 of the other."""
    out: dict[str, dict[str, int]] = {}
    for _, cohort_id, order in record.assignments:
        if order not in FORM_ORDERS:
            raise ResearchError(f"unknown form order {order!r}")
        out.setdefault(cohort_id, {"X": 0, "Y": 0})[order] += 1
    return out


# ------------------------------------------------------------ group allocation

@dataclass(frozen=True)
class AllocationRecord:
    mode: str
    algorithm: str
    algorithm_version: str
    seed: str | None
    protocol_version: str
    executor: str
    drawn_at: str
    cohort_ids: tuple[str, ...]
    clinpath_cohorts: tuple[str, ...]
    cbl_cohorts: tuple[str, ...]
    n_allocations: int
    allocation_index: int | None
    form_order_hash: str
    content_hash: str

    def to_dict(self) -> dict:
        return asdict(self)


def _alloc_payload(fields: Mapping) -> dict:
    return {k: v for k, v in fields.items() if k != "content_hash"}


def _require_frozen_form_order(form_order: FormOrderRecord, drawn_at: str, cohort_ids) -> None:
    if not isinstance(form_order, FormOrderRecord):
        raise RandomizationOrderError("a frozen FormOrderRecord is required before the group draw")
    verify_form_order_record(form_order)
    if form_order.cohort_ids() != tuple(sorted(cohort_ids)):
        raise RandomizationOrderError("form order record covers different cohorts")
    if not _parse_ts(form_order.frozen_at) < _parse_ts(drawn_at):
        raise RandomizationOrderError("form order must be frozen strictly before the group draw")


def draw_cluster_allocation(
    form_order: FormOrderRecord,
    *,
    cohort_ids: Sequence[str],
    seed: str,
    protocol_version: str,
    executor: str,
    drawn_at: str,
) -> AllocationRecord:
    """Draw one of the 35 equiprobable allocations. The record is the only result.

    ``form_order`` comes first on purpose: ordering is enforced by signature and by
    the timestamp check. The seed must differ from the form-order seed so the two
    random processes are separate and auditable.
    """
    ids = tuple(sorted(cohort_ids))
    _check_cohorts(ids)
    _require_frozen_form_order(form_order, drawn_at, ids)
    if str(seed) == form_order.seed:
        raise RandomizationOrderError("group draw and form order must use different seeds")
    index = _Stream(seed, _PURPOSE_CLUSTER).below(N_ALLOCATIONS)
    clinpath = all_allocations(ids)[index]
    return _build_allocation(MODE_RANDOMIZED, str(seed), index, ids, clinpath, protocol_version,
                             executor, drawn_at, form_order.content_hash)


def record_quasi_experimental_allocation(
    form_order: FormOrderRecord,
    *,
    clinpath_cohorts: Sequence[str],
    cohort_ids: Sequence[str],
    protocol_version: str,
    executor: str,
    assigned_at: str,
) -> AllocationRecord:
    """Record a non-random assignment honestly. It can never feed a randomization test."""
    ids = tuple(sorted(cohort_ids))
    _check_cohorts(ids)
    _require_frozen_form_order(form_order, assigned_at, ids)
    clinpath = tuple(sorted(clinpath_cohorts))
    if len(clinpath) != N_CLINPATH or not set(clinpath) <= set(ids):
        raise ResearchError("exactly 3 ClinPath cohorts drawn from the 7 are required")
    return _build_allocation(MODE_QUASI, None, None, ids, clinpath, protocol_version,
                             executor, assigned_at, form_order.content_hash)


def _build_allocation(mode, seed, index, ids, clinpath, protocol_version, executor, drawn_at,
                      form_hash) -> AllocationRecord:
    fields = dict(
        mode=mode, algorithm=ALGORITHM if mode == MODE_RANDOMIZED else "manual",
        algorithm_version=ALGORITHM_VERSION, seed=seed, protocol_version=protocol_version,
        executor=executor, drawn_at=drawn_at, cohort_ids=ids, clinpath_cohorts=tuple(clinpath),
        cbl_cohorts=tuple(c for c in ids if c not in clinpath), n_allocations=N_ALLOCATIONS,
        allocation_index=index, form_order_hash=form_hash,
    )
    payload = {k: (list(v) if isinstance(v, tuple) else v) for k, v in fields.items()}
    return AllocationRecord(**fields, content_hash=_digest(payload))


def verify_allocation_record(record: AllocationRecord | Mapping,
                             form_order: FormOrderRecord | Mapping | None = None) -> AllocationRecord:
    """Check a stored record: hash intact and, if randomized, reproducible from its seed.

    Pass ``form_order`` to also check the record is bound to that frozen form order
    and that it was frozen first. Raises ``ResearchError`` on any inconsistency.
    """
    if not isinstance(record, AllocationRecord):
        d = dict(record)
        for key in ("cohort_ids", "clinpath_cohorts", "cbl_cohorts"):
            d[key] = tuple(d[key])
        record = AllocationRecord(**d)
    fields = record.to_dict()
    payload = {k: (list(v) if isinstance(v, tuple) else v) for k, v in _alloc_payload(fields).items()}
    if _digest(payload) != record.content_hash:
        raise ResearchError("allocation record content hash mismatch")
    if set(record.clinpath_cohorts) | set(record.cbl_cohorts) != set(record.cohort_ids) \
            or len(record.clinpath_cohorts) != N_CLINPATH \
            or set(record.clinpath_cohorts) & set(record.cbl_cohorts):
        raise ResearchError("allocation is not a 3 + 4 partition of the 7 cohorts")
    if record.mode == MODE_RANDOMIZED:
        index = _Stream(record.seed, _PURPOSE_CLUSTER).below(N_ALLOCATIONS)
        if index != record.allocation_index or \
                all_allocations(record.cohort_ids)[index] != record.clinpath_cohorts:
            raise ResearchError("randomized allocation does not follow from the stored seed")
    elif record.mode != MODE_QUASI:
        raise ResearchError(f"unknown mode {record.mode!r}")
    if form_order is not None:
        fo = verify_form_order_record(form_order)
        if fo.content_hash != record.form_order_hash:
            raise RandomizationOrderError("allocation is not bound to this form order record")
        if not _parse_ts(fo.frozen_at) < _parse_ts(record.drawn_at):
            raise RandomizationOrderError("form order was not frozen before the group draw")
    return record
