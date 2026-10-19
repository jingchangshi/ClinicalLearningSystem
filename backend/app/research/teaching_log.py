"""The minimal structured register of real CBL teaching (Research layer, read-only).

The CBL arm is taught conventionally in the ward; ClinPath deliberately has no
simulated AI-training structure for it. What the study still needs is a *record*
that the teaching happened, so the Research export can separate "not logged" from
"no teaching" — two different facts, and only one of them is evidence.

The register is a versioned JSON file kept in the same controlled, mode-600
location as the operator secrets (``~/.config/clinpath/``): it names real
teachers and real case topics, so it must never enter the public repository.
Set ``CLINPATH_CBL_TEACHING_LOG`` to its path. Absent file ⇒ ``not_registered``,
never an empty teaching record.

Format (``teaching_log_version: cbl-teaching-log-v1``)::

    {
      "teaching_log_version": "cbl-teaching-log-v1",
      "data_origin": "real_study",
      "entries": [
        {"cohort_code": "C1", "date": "2026-11-03", "case_topic": "...",
         "duration_minutes": 90, "supervising_teacher": "...",
         "completed": true, "overlaps_assessment_case_topic": false,
         "notes": "..."}
      ]
    }

``overlaps_assessment_case_topic`` is the supervising teacher's recorded judgement
that the taught topic resembles an independent-assessment case. It is never
inferred here: inferring it would have to read the confidential assessment forms.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.research import DATA_ORIGINS

LOG_VERSION = "cbl-teaching-log-v1"
DEFAULT_PATH = "~/.config/clinpath/cbl_teaching_log.json"
ENTRY_FIELDS = ("cohort_code", "date", "case_topic", "duration_minutes", "supervising_teacher",
                "completed", "overlaps_assessment_case_topic", "notes")
REQUIRED_FIELDS = ENTRY_FIELDS[:-1]  # notes is optional
NOT_REGISTERED = "not_registered"
INVALID = "invalid"
REGISTERED = "registered"


@dataclass(frozen=True)
class TeachingLogEntry:
    cohort_code: str
    date: date
    case_topic: str
    duration_minutes: int
    supervising_teacher: str
    completed: bool
    overlaps_assessment_case_topic: bool
    notes: str | None = None


@dataclass(frozen=True)
class TeachingLog:
    version: str
    data_origin: str
    path: str
    sha256: str
    entries: tuple[TeachingLogEntry, ...]

    def for_cohort(self, cohort_code: str) -> list[TeachingLogEntry]:
        return [e for e in self.entries if e.cohort_code == cohort_code]


@dataclass(frozen=True)
class TeachingLogStatus:
    status: str  # registered | not_registered | invalid
    path: str | None
    version: str | None = None
    sha256: str | None = None
    entry_count: int = 0
    problems: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {"status": self.status, "path": self.path, "version": self.version,
                "sha256": self.sha256, "entry_count": self.entry_count,
                "problems": list(self.problems)}

    def provenance(self) -> dict:
        """The part safe to freeze into a research artifact: no local filesystem path."""
        record = self.as_dict()
        record.pop("path", None)
        return record


def configured_path(path: str | os.PathLike | None = None) -> Path:
    return Path(path or os.getenv("CLINPATH_CBL_TEACHING_LOG") or DEFAULT_PATH).expanduser()


def _entry_problem(index: int, raw) -> str | None:
    if not isinstance(raw, dict):
        return f"entry[{index}]: not an object"
    unknown = sorted(set(raw) - set(ENTRY_FIELDS))
    if unknown:
        return f"entry[{index}]: unknown field(s) {unknown}"
    missing = [k for k in REQUIRED_FIELDS if raw.get(k) in (None, "")]
    if missing:
        return f"entry[{index}]: missing required field(s) {missing}"
    try:
        date.fromisoformat(str(raw["date"]))
    except ValueError:
        return f"entry[{index}]: date must be ISO-8601 (YYYY-MM-DD)"
    if not isinstance(raw["duration_minutes"], int) or isinstance(raw["duration_minutes"], bool) \
            or raw["duration_minutes"] <= 0:
        return f"entry[{index}]: duration_minutes must be a positive integer"
    for key in ("completed", "overlaps_assessment_case_topic"):
        if not isinstance(raw[key], bool):
            return f"entry[{index}]: {key} must be true/false"
    if raw.get("notes") is not None and not isinstance(raw["notes"], str):
        return f"entry[{index}]: notes must be text"
    return None


def load(path: str | os.PathLike | None = None) -> tuple[TeachingLog | None, TeachingLogStatus]:
    """Read and validate the register. Never writes, never invents an empty log."""
    target = configured_path(path)
    if not target.is_file():
        return None, TeachingLogStatus(NOT_REGISTERED, str(target),
                                       problems=("teaching_log_file_not_found",))
    raw_bytes = target.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, TeachingLogStatus(INVALID, str(target), sha256=digest,
                                       problems=("teaching_log_is_not_valid_json",))
    problems: list[str] = []
    if not isinstance(payload, dict):
        return None, TeachingLogStatus(INVALID, str(target), sha256=digest,
                                       problems=("teaching_log_root_must_be_an_object",))
    version = payload.get("teaching_log_version")
    if version != LOG_VERSION:
        problems.append(f"teaching_log_version must be {LOG_VERSION!r}")
    origin = payload.get("data_origin")
    if origin not in DATA_ORIGINS:
        problems.append(f"data_origin must be one of {list(DATA_ORIGINS)}")
    entries_raw = payload.get("entries")
    if not isinstance(entries_raw, list):
        problems.append("entries must be a list")
        entries_raw = []
    entries: list[TeachingLogEntry] = []
    for index, raw in enumerate(entries_raw):
        problem = _entry_problem(index, raw)
        if problem:
            problems.append(problem)
            continue
        entries.append(TeachingLogEntry(
            cohort_code=str(raw["cohort_code"]).strip(), date=date.fromisoformat(str(raw["date"])),
            case_topic=str(raw["case_topic"]).strip(), duration_minutes=int(raw["duration_minutes"]),
            supervising_teacher=str(raw["supervising_teacher"]).strip(),
            completed=raw["completed"], overlaps_assessment_case_topic=raw["overlaps_assessment_case_topic"],
            notes=raw.get("notes")))
    status = TeachingLogStatus(INVALID if problems else REGISTERED, str(target), str(version), digest,
                               len(entries), tuple(problems))
    if problems:
        # A malformed register is not partially usable: a dropped entry would look
        # like teaching that never happened.
        return None, status
    return TeachingLog(LOG_VERSION, str(origin), str(target), digest, tuple(entries)), status
