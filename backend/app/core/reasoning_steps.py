"""Canonical clinical reasoning steps.

Single source of truth for both the API contract and the frontend: the student
training page renders exactly these steps and submission validates against the
same list, so the two can no longer drift apart.
"""

REQUIRED_REASONING_STEPS = [
    {
        "key": "key_information",
        "title": "关键信息提取",
        "prompt": "提取关键阳性表现、关键阴性表现和异常检查结果。",
    },
    {
        "key": "initial_diagnosis",
        "title": "初步诊断及依据",
        "prompt": "提出首要诊断，并从症状、实验室检查和器官受累说明依据。",
    },
    {
        "key": "differential_diagnosis",
        "title": "鉴别诊断",
        "prompt": "列出需要排除的感染、肿瘤、HLH、其他结缔组织病等。",
    },
    {
        "key": "examination",
        "title": "进一步检查",
        "prompt": "说明还需要哪些检查，以及每项检查解决什么临床问题。",
    },
    {
        "key": "treatment",
        "title": "治疗方案",
        "prompt": "给出治疗方案、依据、风险评估和监测计划。",
    },
]

REQUIRED_STEP_KEYS = [step["key"] for step in REQUIRED_REASONING_STEPS]


def missing_reasoning_steps(answers: list[dict]) -> list[str]:
    """Return required steps that are absent or blank, in canonical order."""

    latest = {answer["step"]: (answer.get("answer_text") or "").strip() for answer in answers}
    return [key for key in REQUIRED_STEP_KEYS if not latest.get(key)]
