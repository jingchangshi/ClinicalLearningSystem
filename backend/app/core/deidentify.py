"""De-identification guard for anything sent to the model.

ARCH invariant: real case material must be de-identified before it reaches an
LLM. The guard runs inside ``llm_service.prompt_json``, the single choke point
every AI capability serialises through, so a future capability cannot forget it.

Clinical numbers are left alone (dose, lab values, age); only identifier-shaped
data is redacted, and the finding *types* are logged — never the values.
"""

import logging
import re
from typing import Any

logger = logging.getLogger("clinpath.deidentify")

REDACTION_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("mainland_mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[手机号]"),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[邮箱]"),
    ("national_id", re.compile(r"(?<![0-9Xx])\d{17}[\dXx](?![0-9Xx])"), "[身份证号]"),
    ("national_id_short", re.compile(r"(?<!\d)\d{15}(?!\d)"), "[身份证号]"),
    (
        "medical_record_number",
        re.compile(r"(住院号|门诊号|病历号|病案号|就诊号)\s*[:：]?\s*[A-Za-z0-9-]{4,}"),
        r"\1[编号]",
    ),
    (
        "patient_identifier",
        re.compile(r"(MRN|Patient\s*ID|patient_id)\s*[:：]?\s*[A-Za-z0-9-]{4,}", re.IGNORECASE),
        "[编号]",
    ),
    # A name label with an explicit colon is unambiguous.
    (
        "labelled_name",
        re.compile(r"(姓名|患者姓名|监护人|联系人|患者)\s*[:：]\s*[\u4e00-\u9fa5]{2,4}"),
        "[姓名]",
    ),
    # Colon-less unambiguous labels ("姓名王五").
    (
        "labelled_name_inline",
        re.compile(r"(?:姓名|患者姓名|监护人|联系人)\s*[\u4e00-\u9fa5]{2,4}"),
        "[姓名]",
    ),
    # "患者" alone is ambiguous ("患者出现发热"), so it only counts when the text
    # is name-shaped: 患者王五，男 / 患者李四女 ...
    (
        "labelled_name_demographic",
        re.compile(
            r"患者\s*[\u4e00-\u9fa5]{2,3}(?=[，,]\s*(?:男|女)|男|女|岁)"
        ),
        "[姓名]",
    ),
]


def redact_phi(text: str) -> tuple[str, list[str]]:
    """Return the redacted text plus the identifier kinds that were removed."""

    if not text:
        return text, []
    findings: list[str] = []
    redacted = text
    for kind, pattern, replacement in REDACTION_RULES:
        redacted, count = pattern.subn(replacement, redacted)
        if count:
            findings.append(kind)
    return redacted, findings


def deidentify(value: Any) -> Any:
    """Redact identifier-shaped content anywhere inside a JSON-like payload.

    Returns the original object when nothing needed to change, so callers pay no
    extra copying cost in the common case.
    """

    findings: list[str] = []
    redacted = _walk(value, findings)
    if findings:
        logger.warning("deidentify: redacted %s before provider call", sorted(set(findings)))
        return redacted
    return value


def deidentify_text(text: str) -> str:
    """Redact a single prompt string, reporting only the finding kinds."""

    redacted, findings = redact_phi(text or "")
    if findings:
        logger.warning("deidentify: redacted %s before provider call", sorted(set(findings)))
    return redacted


CASE_TEXT_FIELDS = (
    "title",
    "chief_complaint",
    "history",
    "physical_exam",
    "lab_results",
    "imaging",
    "standard_diagnosis",
    "treatment_plan",
)

CASE_LIST_FIELDS = ("learning_objectives", "differential_diagnosis")

# Teacher-facing names, so a warning can name the field without the client
# duplicating the mapping.
FIELD_LABELS = {
    "title": "病例标题",
    "chief_complaint": "主诉",
    "history": "现病史",
    "physical_exam": "体格检查",
    "lab_results": "实验室检查",
    "imaging": "影像资料",
    "standard_diagnosis": "标准诊断",
    "treatment_plan": "治疗方案",
    "learning_objectives": "学习目标",
    "differential_diagnosis": "鉴别诊断",
    "teaching_goal": "教学目标",
    "disease_category": "疾病类别",
    "required_elements": "必需要素",
}

_COLLECTION_FIELDS = ("learning_objectives", "differential_diagnosis", "required_elements")


def scan_case_payload(payload: dict, fields: tuple[str, ...] = CASE_TEXT_FIELDS) -> dict:
    """Find identifier-shaped content in teacher-authored case text.

    Reports *which fields* look like they carry identifiers and *what kind*, but
    never echoes the offending values back. Authoring stays the teacher's call;
    this exists so real patient data is caught at the door instead of quietly
    entering the case bank.
    """

    findings: list[dict] = []
    for field in fields:
        value = payload.get(field)
        if isinstance(value, str) and value:
            _, kinds = redact_phi(value)
            if kinds:
                findings.append(_finding(field, kinds))
    for field in (*CASE_LIST_FIELDS, *[f for f in _COLLECTION_FIELDS if f not in fields]):
        value = payload.get(field)
        items = value if isinstance(value, (list, tuple)) else []
        kinds: list[str] = []
        for item in items:
            if isinstance(item, str):
                _, item_kinds = redact_phi(item)
                kinds.extend(item_kinds)
        if kinds:
            findings.append(_finding(field, kinds))
    return {
        "clean": not findings,
        "findings": findings,
        "message": (
            "检测到可能的身份信息，请确认这是去标识化后的教学病例。"
            "提交给模型的内容会自动脱敏，但病例库中仍会保留你输入的内容。"
            if findings
            else ""
        ),
    }


def _finding(field: str, kinds: list[str]) -> dict:
    return {
        "field": field,
        "label": FIELD_LABELS.get(field, field),
        "kinds": sorted(set(kinds)),
    }


def _walk(value: Any, findings: list[str]) -> Any:
    if isinstance(value, str):
        redacted, found = redact_phi(value)
        findings.extend(found)
        return redacted
    if isinstance(value, dict):
        return {key: _walk(item, findings) for key, item in value.items()}
    if isinstance(value, list):
        return [_walk(item, findings) for item in value]
    if isinstance(value, tuple):
        return tuple(_walk(item, findings) for item in value)
    return value
