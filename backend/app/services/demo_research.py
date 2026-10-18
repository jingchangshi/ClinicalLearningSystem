"""Read-only synthetic teaching-research demo dataset (work package D).

Everything in this module is deliberately *outside* the application database.
The work package D dataset describes 60 virtual students in two virtual teaching
cohorts; it exists to demonstrate that ClinPath can collect, export and analyse a
study-shaped dataset. It is not evidence that ClinPath improves learning.

Three rules hold here and are enforced by tests:

1. **No database session is ever opened.** Nothing in this module imports
   ``app.models`` or ``get_db``. The synthetic rows cannot reach
   ``students`` / ``case_sessions`` / ``learning_evidence_events`` /
   ``teacher_score_reviews``.
2. **Every row carries its provenance.** ``data_origin`` is read from the CSV and
   never rewritten; simulated raters stay ``SIMULATED_NOT_HUMAN``.
3. **The statistics are computed from the rows that are served.** No page and no
   CSV download has a second, hand-written copy of a number. The offline
   generator's ``metrics_SYNTHETIC.json`` is checked against these results by
   ``tests/test_demo_research.py``, which is what makes "reproducible" testable.

The dataset directory is versioned: ``demo_research/synthetic_v1``. A future
dataset version gets its own directory and its own id rather than mutating this
one.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import threading
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

DATASET_ID = "synthetic_v1"
DATA_ORIGIN = "SYNTHETIC_DEMO_NOT_REAL_STUDENTS"
RATER_ORIGIN = "SIMULATED_NOT_HUMAN"
BANNER = "合成教学研究演示｜虚拟学生、虚拟评分者｜不代表真实教学成效"
ANALYSIS_NOTE = (
    "全部数值均为模拟结果。组间提升差异是在生成数据时预先设定的情景，"
    "统计程序只是如实计算了这种模拟差异；这些 P 值不能作为真实教学效果的证据。"
)

SIX_DIMENSIONS = [
    ("medical_knowledge", "医学知识运用", 0.10),
    ("key_information", "关键信息提取", 0.20),
    ("differential_diagnosis", "鉴别诊断与论证", 0.25),
    ("evidence_integration", "临床证据整合", 0.15),
    ("clinical_decision", "检查与临床决策", 0.20),
    ("evidence_based_medicine", "循证依据与安全意识", 0.10),
]

REASONING_STEPS = [
    ("S1", "关键信息提取"),
    ("S2", "初步诊断与问题表征"),
    ("S3", "鉴别诊断与论证"),
    ("S4", "辅助检查决策"),
    ("S5", "治疗决策与安全意识"),
]

FILE_NAMES = {
    "participants": "data/participants_SYNTHETIC.csv",
    "assessments": "data/assessments_SYNTHETIC.csv",
    "sessions": "data/learning_sessions_SYNTHETIC.csv",
    "reasoning_steps": "data/reasoning_steps_SYNTHETIC.csv",
    "analysis": "data/analysis_ready_SYNTHETIC.csv",
    "dictionary": "data_dictionary.csv",
    "expert_review": "templates/expert_review_BLANK.csv",
    "metrics": "metrics_SYNTHETIC.json",
}

_CACHE: dict[str, "DemoDataset"] = {}


def repo_root() -> Path:
    # <repo>/backend/app/services/demo_research.py -> <repo>
    return Path(__file__).resolve().parents[3]


def dataset_dir() -> Path:
    override = os.getenv("CLINPATH_DEMO_RESEARCH_DIR")
    if override:
        return Path(override)
    return repo_root() / "demo_research" / DATASET_ID


def _read_csv(path: Path) -> list[dict[str, str]]:
    # The generator writes a UTF-8 BOM so Excel opens the Chinese headers; strip it.
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: str | None) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    return float(text)


def _mean(values: Iterable[float]) -> float:
    """Exact-decimal mean of the served values.

    Python's float ``sum`` is order-dependent: ``sum`` over the same 30 gains in
    a different order can land a ULP either side of ``x.xx5`` and flip a reported
    hundredth. The numbers here are decimals that were generated as decimals, so
    they are summed as ``Decimal`` and the mean is rounded half-up — the same
    convention the offline generator's ``round`` produced.
    """

    items = list(values)
    if not items:
        return 0.0
    total = sum(Decimal(repr(value)) for value in items)
    return float(total / Decimal(len(items)))


def _round_half_up(value: float, places: int = 2) -> float:
    quantum = Decimal(1).scaleb(-places)
    return float(Decimal(repr(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _var(values: list[float]) -> float:
    """Sample variance (ddof=1), matching the generator's numpy default."""

    if len(values) < 2:
        return 0.0
    mu = _mean(values)
    return sum((value - mu) ** 2 for value in values) / (len(values) - 1)


# --- Student t distribution, pure Python -------------------------------------
# scipy is not a backend dependency, and adding it for a demo page would be a
# poor trade. The tail probabilities below use the regularized incomplete beta
# function, which stays accurate for the very large t values this seeded
# scenario produces.


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""

    max_iterations, epsilon, tiny = 300, 3.0e-16, 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    result = d
    for m in range(1, max_iterations + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        result *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) < epsilon:
            break
    return result


def _betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b)."""

    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_beta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(log_beta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(statistic: float, degrees_of_freedom: float) -> float:
    """Two-sided p-value for a Student t statistic."""

    if degrees_of_freedom <= 0:
        return 1.0
    x = degrees_of_freedom / (degrees_of_freedom + statistic * statistic)
    return max(0.0, min(1.0, _betai(degrees_of_freedom / 2.0, 0.5, x)))


def t_cdf(statistic: float, degrees_of_freedom: float) -> float:
    if degrees_of_freedom <= 0:
        return 0.5
    tail = 0.5 * t_two_sided_p(abs(statistic), degrees_of_freedom)
    return 1.0 - tail if statistic >= 0 else tail


def normal_two_sided_p(statistic: float) -> float:
    """Two-sided p-value under the standard normal distribution."""

    return math.erfc(abs(statistic) / math.sqrt(2.0))


NORMAL_975 = 1.959963984540054


def t_quantile(probability: float, degrees_of_freedom: float) -> float:
    """Inverse t CDF by bisection; only used for a 95% interval."""

    low, high = -1.0e3, 1.0e3
    for _ in range(200):
        middle = (low + high) / 2.0
        if t_cdf(middle, degrees_of_freedom) < probability:
            low = middle
        else:
            high = middle
    return (low + high) / 2.0


def welch_test(treatment: list[float], control: list[float]) -> dict[str, Any]:
    """Welch's unequal-variance t test plus the 95% CI of the mean difference."""

    nx, ny = len(control), len(treatment)
    vx = _var(control) / nx
    vy = _var(treatment) / ny
    standard_error = math.sqrt(vx + vy)
    delta = _mean(treatment) - _mean(control)
    if standard_error == 0:
        return {
            "difference": delta,
            "standard_error": 0.0,
            "t_statistic": 0.0,
            "degrees_of_freedom": float(nx + ny - 2),
            "p_value": 1.0,
            "ci95": [delta, delta],
        }
    statistic = delta / standard_error
    df = (vx + vy) ** 2 / (
        (vx**2) / (nx - 1) + (vy**2) / (ny - 1)
    )
    margin = t_quantile(0.975, df) * standard_error
    return {
        "difference": delta,
        "standard_error": standard_error,
        "t_statistic": statistic,
        "degrees_of_freedom": df,
        "p_value": t_two_sided_p(statistic, df),
        "ci95": [delta - margin, delta + margin],
    }


def _invert(matrix: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan inverse for the small (3x3) design matrix."""

    size = len(matrix)
    work = [
        list(matrix[row]) + [1.0 if row == column else 0.0 for column in range(size)]
        for row in range(size)
    ]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(work[row][column]))
        if abs(work[pivot][column]) < 1.0e-12:
            raise ValueError("singular design matrix")
        work[column], work[pivot] = work[pivot], work[column]
        divisor = work[column][column]
        work[column] = [value / divisor for value in work[column]]
        for row in range(size):
            if row == column:
                continue
            factor = work[row][column]
            if factor:
                work[row] = [
                    value - factor * pivot_value
                    for value, pivot_value in zip(work[row], work[column])
                ]
    return [row[size:] for row in work]


def _matmul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [
            sum(left[row][k] * right[k][column] for k in range(len(right)))
            for column in range(len(right[0]))
        ]
        for row in range(len(left))
    ]


def _transpose(matrix: list[list[float]]) -> list[list[float]]:
    return [list(column) for column in zip(*matrix)]


def ancova_hc3(
    post: list[float], pre: list[float], treatment: list[int]
) -> dict[str, Any]:
    """OLS ``post ~ 1 + treatment + pre`` with HC3 robust standard errors.

    HC3 is implemented as ``(e_i / (1 - h_i))^2`` on *whitened* residuals — the
    residuals statsmodels calls ``wresid`` — and not as ``e_i^2 / (1 - h_i)^2``.
    Those two differ by a constant factor of ``1 / (1 - h_i)`` for a design with
    a unit constant column, because whitening turns ``e_i`` into
    ``e_i / sqrt(1 - h_i)``. Using the unwhitened form inflates the robust
    variance and changes the p-value by ~20 orders of magnitude on this dataset,
    which is exactly the kind of "close enough" that would make the page and the
    offline workbook disagree. ``tests/test_demo_research.py`` pins the result
    against the generator's statsmodels output.

    The reference distribution is the normal, matching
    ``OLS(...).fit(cov_type="HC3")`` (statsmodels sets ``use_t=False`` for robust
    covariance). Reporting a t-based p-value here would silently disagree with
    the Excel workbook a reviewer is checking against.
    """

    design = [[1.0, float(group), float(base)] for group, base in zip(treatment, pre)]
    xt = _transpose(design)
    xtx_inverse = _invert(_matmul(xt, design))
    xty = [
        sum(row[column] * value for column, value in enumerate(post))
        for row in xt
    ]
    beta = [
        sum(xtx_inverse[row][column] * xty[column] for column in range(3))
        for row in range(3)
    ]

    residuals = [
        target - sum(coefficient * value for coefficient, value in zip(beta, row))
        for target, row in zip(post, design)
    ]
    leverage = [
        sum(
            row[i] * xtx_inverse[i][j] * row[j]
            for i in range(3)
            for j in range(3)
        )
        for row in design
    ]

    # HC3: squared residuals, each already divided by sqrt(1 - h_ii) by the
    # whitening step, then divided by one more sqrt(1 - h_ii).
    meat = [[0.0] * 3 for _ in range(3)]
    for row, residual, h in zip(design, residuals, leverage):
        if 1.0 - h <= 0:
            raise ValueError("non-positive leverage in ANCOVA design")
        weight = (residual / math.sqrt(1.0 - h)) ** 2 / (1.0 - h)
        for i in range(3):
            for j in range(3):
                meat[i][j] += row[i] * row[j] * weight

    sandwich = _matmul(_matmul(xtx_inverse, meat), xtx_inverse)
    standard_error = math.sqrt(sandwich[1][1])
    effect = beta[1]
    df = len(post) - 3
    statistic = effect / standard_error if standard_error else 0.0
    margin = NORMAL_975 * standard_error
    return {
        "effect": effect,
        "standard_error": standard_error,
        "z_statistic": statistic,
        "degrees_of_freedom": float(df),
        "p_value": normal_two_sided_p(statistic),
        "ci95": [effect - margin, effect + margin],
    }


@dataclass(frozen=True)
class DemoDataset:
    participants: list[dict[str, str]]
    assessments: list[dict[str, str]]
    sessions: list[dict[str, str]]
    reasoning_steps: list[dict[str, str]]
    dictionary: list[dict[str, str]]
    expert_review: list[dict[str, str]]
    offline_metrics: dict[str, Any]
    file_hashes: dict[str, str]
    directory: Path

    # --- lookups ---------------------------------------------------------

    def participant(self, study_id: str) -> dict[str, str] | None:
        return self._participants_by_id.get(study_id)

    @property
    def _participants_by_id(self) -> dict[str, dict[str, str]]:
        cached = getattr(self, "_participant_index", None)
        if cached is not None:
            return cached
        index = {row["study_id"]: row for row in self.participants}
        object.__setattr__(self, "_participant_index", index)
        return index

    def assessments_for(self, study_id: str) -> list[dict[str, str]]:
        return [row for row in self.assessments if row["study_id"] == study_id]

    def sessions_for(self, study_id: str) -> list[dict[str, str]]:
        return sorted(
            (row for row in self.sessions if row["study_id"] == study_id),
            key=lambda row: int(row["week"]),
        )

    def steps_for(self, study_id: str) -> list[dict[str, str]]:
        order = {key: index for index, (key, _) in enumerate(REASONING_STEPS)}
        return sorted(
            (row for row in self.reasoning_steps if row["study_id"] == study_id),
            key=lambda row: (row["session_id"], order.get(row["step_id"], 99)),
        )

    # --- derived facts ---------------------------------------------------

    def paired_scores(self) -> list[dict[str, Any]]:
        """One row per student: T0, T1 and the gain, from the assessments."""

        by_key = {(row["study_id"], row["timepoint"]): row for row in self.assessments}
        scores: list[dict[str, Any]] = []
        for person in self.participants:
            study_id = person["study_id"]
            pre_row = by_key.get((study_id, "T0"))
            post_row = by_key.get((study_id, "T1"))
            if pre_row is None or post_row is None:
                continue
            pre = float(pre_row["independent_total"])
            post = float(post_row["independent_total"])
            scores.append(
                {
                    "study_id": study_id,
                    "group": person["group"],
                    "cohort": person["cohort"],
                    "pre_score": pre,
                    "post_score": post,
                    "gain_score": round(post - pre, 2),
                }
            )
        return scores

    def group_label(self, group: str) -> str:
        return "常规CBL" if group == "CBL" else "ClinPath辅助教学"


_lock = threading.Lock()


def load_dataset(directory: Path | None = None) -> DemoDataset:
    """Load the dataset once per process; ``directory`` enables tests."""

    base = directory or dataset_dir()
    key = str(base)
    dataset = _CACHE.get(key)
    if dataset is not None:
        return dataset
    with _lock:
        dataset = _CACHE.get(key)
        if dataset is not None:
            return dataset
        if not base.is_dir():
            raise FileNotFoundError(f"synthetic research dataset not found: {base}")

        paths = {name: base / relative for name, relative in FILE_NAMES.items()}
        absent = [str(path) for path in paths.values() if not path.is_file()]
        if absent:
            raise FileNotFoundError(
                "synthetic research dataset is incomplete: " + ", ".join(absent)
            )

        hashes = {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in paths.items()
        }
        dataset = DemoDataset(
            participants=_read_csv(paths["participants"]),
            assessments=_read_csv(paths["assessments"]),
            sessions=_read_csv(paths["sessions"]),
            reasoning_steps=_read_csv(paths["reasoning_steps"]),
            dictionary=_read_csv(paths["dictionary"]),
            expert_review=_read_csv(paths["expert_review"]),
            offline_metrics=json.loads(paths["metrics"].read_text(encoding="utf-8")),
            file_hashes=hashes,
            directory=base,
        )
        _CACHE[key] = dataset
        return dataset


def reset_cache() -> None:
    with _lock:
        _CACHE.clear()


def _round(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def compute_summary(dataset: DemoDataset) -> dict[str, Any]:
    """Descriptive and inferential statistics, computed from the served rows."""

    paired = dataset.paired_scores()
    groups: dict[str, Any] = {}
    for group in ("CBL", "CLINPATH"):
        rows = [row for row in paired if row["group"] == group]
        pre = [row["pre_score"] for row in rows]
        post = [row["post_score"] for row in rows]
        gains = [row["gain_score"] for row in rows]
        groups[group] = {
            "label": dataset.group_label(group),
            "n": len(rows),
            "pre_mean": _round_half_up(_mean(pre)),
            "post_mean": _round_half_up(_mean(post)),
            "gain_mean": _round_half_up(_mean(gains)),
            "gain_sd": _round_half_up(math.sqrt(_var(gains))),
        }

    control = [row["gain_score"] for row in paired if row["group"] == "CBL"]
    treatment = [row["gain_score"] for row in paired if row["group"] == "CLINPATH"]
    welch = welch_test(treatment, control)

    ordered = sorted(paired, key=lambda row: row["study_id"])
    post = [row["post_score"] for row in ordered]
    pre = [row["pre_score"] for row in ordered]
    treatment_flag = [1 if row["group"] == "CLINPATH" else 0 for row in ordered]
    ancova = ancova_hc3(post, pre, treatment_flag)

    return {
        "data_origin": DATA_ORIGIN,
        "rater_origin": RATER_ORIGIN,
        "banner": BANNER,
        "groups": groups,
        "difference": {
            "label": "模拟两组提升差（ClinPath − 常规CBL）",
            "value": _round(welch["difference"]),
            "ci95": [_round(value) for value in welch["ci95"]],
            "welch_t": _round(welch["t_statistic"], 3),
            "welch_df": _round(welch["degrees_of_freedom"], 2),
            "welch_p": welch["p_value"],
        },
        "ancova": {
            "label": "校正T0基线后的模拟组别效应（HC3稳健标准误）",
            "value": _round(ancova["effect"]),
            "ci95": [_round(value) for value in ancova["ci95"]],
            "p_value": ancova["p_value"],
        },
        "analysis_note": ANALYSIS_NOTE,
        "scenario": {
            "nominal_CBL_gain": 6,
            "nominal_CLINPATH_gain": 18,
            "measurement": "两名计算机模拟评分者，不是真实教师",
            "scale": "0-100",
            "explanation": "数据生成时预先注入了两组不同的提升期望，因此模拟显著性不代表教学效果。",
        },
    }


def _student_row(dataset: DemoDataset, person: dict[str, str]) -> dict[str, Any]:
    rows = {row["timepoint"]: row for row in dataset.assessments_for(person["study_id"])}
    pre = rows.get("T0")
    post = rows.get("T1")
    return {
        "study_id": person["study_id"],
        "group": person["group"],
        "group_label": dataset.group_label(person["group"]),
        "cohort": person["cohort"],
        "pre_score": _float(pre["independent_total"]) if pre else None,
        "post_score": _float(post["independent_total"]) if post else None,
        "gain_score": _round(
            float(post["independent_total"]) - float(pre["independent_total"])
        )
        if pre and post
        else None,
        "training_session_count": len(dataset.sessions_for(person["study_id"])),
        "reasoning_step_count": len(dataset.steps_for(person["study_id"])),
        "data_origin": DATA_ORIGIN,
        "rater_origin": RATER_ORIGIN,
    }


def list_students(
    dataset: DemoDataset, group: str | None = None, query: str | None = None
) -> list[dict[str, Any]]:
    people = dataset.participants
    if group:
        people = [person for person in people if person["group"] == group]
    if query:
        needle = query.strip().upper()
        people = [person for person in people if needle in person["study_id"].upper()]
    return [_student_row(dataset, person) for person in sorted(people, key=lambda p: p["study_id"])]


def _assessment_payload(row: dict[str, str]) -> dict[str, Any]:
    return {
        "timepoint": row["timepoint"],
        "assessment_case_id": row["assessment_case_id"],
        "assessment_type": row["assessment_type"],
        "independent_total": float(row["independent_total"]),
        "rater_A": {"id": row["rater_A_id"], "total": float(row["rater_A_total"])},
        "rater_B": {"id": row["rater_B_id"], "total": float(row["rater_B_total"])},
        "rater_origin": row["rater_origin"],
        "ai_scoring_used_for_primary_outcome": row["ai_scoring_used_for_primary_outcome"],
        "dimensions": [
            {"key": key, "label": label, "weight": weight, "score": float(row[key])}
            for key, label, weight in SIX_DIMENSIONS
        ],
        "data_origin": row["data_origin"],
    }


def student_detail(dataset: DemoDataset, study_id: str) -> dict[str, Any] | None:
    person = dataset.participant(study_id)
    if person is None:
        return None

    sessions = []
    for session in dataset.sessions_for(study_id):
        steps = [
            {
                "step_id": step["step_id"],
                "step_label": step["step_label"],
                "initial_answer": step["initial_student_answer_synthetic"],
                "tutor_question": step["ai_tutor_question_synthetic"],
                "revised_answer": step["revised_student_answer_synthetic"],
                "answer_text_generation": step["answer_text_generation"],
                "is_real_student": step["is_real_student"],
            }
            for step in dataset.steps_for(study_id)
            if step["session_id"] == session["session_id"]
        ]
        sessions.append(
            {
                "session_id": session["session_id"],
                "week": int(session["week"]),
                "case_code": session["case_code"],
                "teaching_mode": session["teaching_mode"],
                "training_score_internal": _float(session["training_score_internal"]),
                "evaluation_mode": session["evaluation_mode"],
                "model_id": session["model_id"],
                "simulated_teacher_intervention": session["synthetic_teacher_intervention"],
                "date_relative": session["date_relative"],
                "reasoning_steps": steps,
            }
        )

    summary = _student_row(dataset, person)
    return {
        **summary,
        "cohort_program": person["program"],
        "study_status": person["study_status"],
        "ethics_or_consent": person["ethics_or_consent"],
        "assessments": [_assessment_payload(row) for row in dataset.assessments_for(study_id)],
        "sessions": sessions,
        "notes": [
            "该学生的全部作答、评分与教师干预均为合成内容。",
            "评分者 SYN_RATER_A / SYN_RATER_B 是计算机模拟评分者，不是真实教师。",
            "训练分与独立前后测是不同来源，训练分不得替代主结局。",
        ],
    }


def export_rows(dataset: DemoDataset) -> list[dict[str, Any]]:
    """One flat row per student, for the downloadable CSV."""

    rows = []
    for row in dataset.paired_scores():
        person = dataset.participant(row["study_id"]) or {}
        rows.append(
            {
                "study_id": row["study_id"],
                "data_origin": DATA_ORIGIN,
                "group": row["group"],
                "cohort": row["cohort"],
                "pre_score_T0": row["pre_score"],
                "post_score_T1": row["post_score"],
                "gain_score": row["gain_score"],
                "rater_origin": RATER_ORIGIN,
                "training_sessions": len(dataset.sessions_for(row["study_id"])),
                "reasoning_steps": len(dataset.steps_for(row["study_id"])),
                "simulation_seed": person.get("simulation_seed", ""),
            }
        )
    return sorted(rows, key=lambda item: item["study_id"])


def meta_payload(dataset: DemoDataset) -> dict[str, Any]:
    pending = sum(1 for row in dataset.expert_review if row["final_approval"].startswith("PENDING"))
    metrics = dataset.offline_metrics
    return {
        "dataset_id": DATASET_ID,
        "data_origin": DATA_ORIGIN,
        "rater_origin": RATER_ORIGIN,
        "banner": BANNER,
        "title": "合成教学研究演示",
        "description": (
            "60 名虚拟学生、两组虚拟教学批次的前后测演示数据集。"
            "用于展示研究数据的采集字段、导出与统计处理是否可复现，"
            "不代表任何真实学生的教学效果。"
        ),
        "seed": metrics.get("seed", 20261018),
        "generator": {
            "script": "demo_research/synthetic_v1/generate_demo.py",
            "version": "synthetic_v1",
            "ai_text_generation": "MODEL_AUTHORED_TEMPLATE_PLUS_DETERMINISTIC_VARIATION",
            "note": "推理步骤文本为模板＋固定随机变化，不是逐条线上模型调用。",
        },
        "design": {
            "groups": [
                {"key": "CBL", "label": "常规CBL病例讨论", "n": 30},
                {"key": "CLINPATH", "label": "ClinPath辅助病例教学", "n": 30},
            ],
            "timepoints": ["T0", "T1"],
            "assessment": "独立标准化病例（训练库不复用），每例两名模拟评分者",
            "primary_outcome": "独立前后测总分（0-100）",
            "cohorts": sorted({row["cohort"] for row in dataset.participants}),
        },
        "counts": {
            "students": len(dataset.participants),
            "assessments": len(dataset.assessments),
            "learning_sessions": len(dataset.sessions),
            "reasoning_steps": len(dataset.reasoning_steps),
        },
        "scenario_assumptions": metrics.get("scenario_assumptions", {}),
        "dimensions": [
            {"key": key, "label": label, "weight": weight}
            for key, label, weight in SIX_DIMENSIONS
        ],
        "methods": {
            "descriptive": "组内均值与提升均来自 analysis_ready 同源记录，由后端按 CSV 实时计算",
            "gain_test": "Welch 不等方差 t 检验（模仿生成器的 scipy 实现，双尾）",
            "baseline_adjusted": "OLS post ~ 1 + group + pre，HC3 稳健标准误",
            "source": "数值由服务端从 demo_research/synthetic_v1/data/*.csv 计算，页面与下载共用同一结果",
        },
        "files": [
            {
                "name": name,
                "path": str(FILE_NAMES[name]),
                "sha256": digest,
            }
            for name, digest in sorted(dataset.file_hashes.items())
        ],
        "expert_review": {
            "status": "PENDING_REAL_REVIEW",
            "pending_rows": pending,
            "total_rows": len(dataset.expert_review),
            "template": str(FILE_NAMES["expert_review"]),
            "note": "真实教师审核尚未进行；在收到带有日期与签名的原始记录前，不得标记为已审核。",
        },
    }


def dictionary_payload(dataset: DemoDataset) -> list[dict[str, str]]:
    return dataset.dictionary


def expert_review_payload(dataset: DemoDataset) -> list[dict[str, str]]:
    return dataset.expert_review


@lru_cache(maxsize=1)
def default_dataset() -> DemoDataset:
    return load_dataset()
