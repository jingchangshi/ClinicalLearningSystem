"""Pure transforms for the frozen research dataset (R4.6) and its content hash.

One row = one student x timepoint. Columns and order are fixed by ``COLUMNS`` and
documented in docs/teaching_grant_2026/workpackages/DATA_DICTIONARY.md. The frozen
hash is SHA-256 over the canonical CSV, so the same dataset_version always
reproduces the same bytes (and therefore the same statistics).
"""
from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from . import (
    DATA_ORIGINS,
    FORM_BY_ORDER,
    FORM_ORDERS,
    MixedDataOriginError,
    ResearchError,
    STUDY_GROUPS,
)

COLUMNS = (
    "study_student_code", "cohort_id", "study_group", "randomization_version", "timepoint",
    "assessment_form_id", "assessment_form_version", "form_order",
    "blinded_rater_1_score", "blinded_rater_2_score", "adjudicated_score", "final_score",
    "assessment_completed_at", "training_exposure", "intervention_count", "missingness",
    "scoring_provenance", "dataset_version", "data_origin",
)
_SCORES = ("blinded_rater_1_score", "blinded_rater_2_score", "adjudicated_score", "final_score")
TIMEPOINTS = ("T0", "T1")
MISSINGNESS_OBSERVED = "observed"


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return format(v, ".6g") if v != int(v) else str(int(v))
    return str(v)


def build_rows(records: Iterable[Mapping], *, dataset_version: str, data_origin: str) -> list[dict]:
    """Validate and canonicalise rows. Refuses mixed or unknown data_origin."""
    if data_origin not in DATA_ORIGINS:
        raise MixedDataOriginError(f"unknown data_origin {data_origin!r}")
    out, seen = [], set()
    for rec in records:
        origin = rec.get("data_origin", data_origin)
        if origin != data_origin:
            raise MixedDataOriginError(f"row origin {origin!r} != dataset origin {data_origin!r}")
        row = {c: rec.get(c) for c in COLUMNS}
        row["dataset_version"], row["data_origin"] = dataset_version, data_origin
        if row["timepoint"] not in TIMEPOINTS:
            raise ResearchError(f"timepoint must be T0 or T1: {row['timepoint']!r}")
        if row["form_order"] not in FORM_ORDERS:
            raise ResearchError(f"form_order must be X or Y: {row['form_order']!r}")
        if row["study_group"] not in STUDY_GROUPS:
            raise ResearchError(f"study_group invalid: {row['study_group']!r}")
        expected_form = FORM_BY_ORDER[row["form_order"]][row["timepoint"]]
        if row["assessment_form_id"] != expected_form:
            raise ResearchError(
                f"{row['study_student_code']} {row['timepoint']}: form order {row['form_order']} "
                f"requires {expected_form}, got {row['assessment_form_id']!r}")
        if row["final_score"] is None and not row["missingness"]:
            raise ResearchError("a missing final_score needs a missingness reason")
        if row["final_score"] is not None and not row["missingness"]:
            row["missingness"] = MISSINGNESS_OBSERVED
        key = (row["study_student_code"], row["timepoint"])
        if key in seen:
            raise ResearchError(f"duplicate row for {key}")
        seen.add(key)
        out.append(row)
    out.sort(key=lambda r: (r["study_student_code"], r["timepoint"]))
    return out


def to_csv(rows: Sequence[Mapping]) -> str:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUMNS)
    for r in rows:
        w.writerow([_fmt(r.get(c)) for c in COLUMNS])
    return buf.getvalue()


@dataclass(frozen=True)
class DatasetManifest:
    dataset_version: str
    data_origin: str
    row_count: int
    columns: tuple[str, ...]
    content_sha256: str


def freeze(rows: Sequence[Mapping], *, dataset_version: str, data_origin: str) -> tuple[str, DatasetManifest]:
    """Return (canonical_csv, manifest). Store both; never regenerate under the same version."""
    checked = build_rows(rows, dataset_version=dataset_version, data_origin=data_origin)
    text = to_csv(checked)
    return text, DatasetManifest(dataset_version, data_origin, len(checked), COLUMNS,
                                 hashlib.sha256(text.encode("utf-8")).hexdigest())


def verify_frozen(csv_text: str, manifest: DatasetManifest) -> bool:
    return hashlib.sha256(csv_text.encode("utf-8")).hexdigest() == manifest.content_sha256
