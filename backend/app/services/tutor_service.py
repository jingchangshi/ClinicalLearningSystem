"""Step-level Socratic clinical reasoning tutor.

The tutor is deliberately not a chatbot: it keeps an explicit reasoning state per
reasoning step, asks ONE focused question at a time, never reveals the hidden
diagnosis or treatment plan, and stops after a bounded number of turns.
"""

import json
import logging
import os
import re

from app.core.reasoning_steps import REQUIRED_STEP_KEYS
from app.services.llm_service import llm_service, prompt_json
from app.services.scoring_llm import DIMENSION_KEYWORDS, SAFETY_SIGNALS

logger = logging.getLogger("clinpath.tutor")

MAX_TUTOR_TURNS_PER_STEP = int(os.getenv("MAX_TUTOR_TURNS_PER_STEP", "6"))

STEP_DIMENSION = {
    "key_information": "key_information",
    "initial_diagnosis": "medical_knowledge",
    "differential_diagnosis": "differential_diagnosis",
    "examination": "evidence_integration",
    "treatment": "clinical_decision",
}

TUTOR_SYSTEM_PROMPT = """你是临床推理的苏格拉底式导师。

硬性约束：
1. 绝不给出标准诊断结论、标准治疗方案或评分量规内容。
2. 每次只问一个问题，问题要短（<=60字），并且优先问「为什么」。
3. 围绕学生尚未覆盖的推理要素提问：证据与反证、鉴别排序、验证策略、安全性。
4. 不评价分数，不总结标准答案，不重复学生已经答过的内容。
5. 只输出这个问题本身，不要输出 JSON、编号或解释。
"""

TUTOR_USER_TEMPLATE = """病例（已去除隐藏答案）：
{case_context}

当前推理步骤：{step}
学生当前回答：{student_answer}

导师掌握的学生推理状态：
{reasoning_state}

请提出下一个聚焦问题。"""


def build_reasoning_state(
    case: dict,
    step: str,
    student_answer: str,
    turns: list[dict],
    covered_by_tutor: list[str] | None = None,
) -> dict:
    """Deterministic reasoning state derived from the student's own words."""

    dimension = STEP_DIMENSION.get(step, "medical_knowledge")
    keywords = DIMENSION_KEYWORDS[dimension]
    answer = (student_answer or "").strip()
    lowered = answer.lower()
    hit = [keyword for keyword in keywords if keyword.lower() in lowered]
    missing = [keyword for keyword in keywords if keyword not in hit]
    safety_gap = [
        message
        for message, signals in SAFETY_SIGNALS.items()
        if not any(signal.lower() in lowered for signal in signals)
    ]
    tutor_turns = [turn for turn in turns if turn.get("role") == "tutor"]
    student_turns = [turn for turn in turns if turn.get("role") == "student"]
    tutor_text = " ".join(turn.get("message", "") for turn in tutor_turns).lower()
    asked_about = covered_by_tutor or [
        keyword for keyword in keywords if keyword.lower() in tutor_text
    ]

    if not answer:
        completion = "not_started"
    elif not missing:
        completion = "coverage_sufficient"
    elif len(tutor_turns) >= MAX_TUTOR_TURNS_PER_STEP:
        completion = "max_turns_reached"
    else:
        completion = "in_progress"

    return {
        "step": step,
        "dimension": dimension,
        "evidence_already_covered": hit,
        "missing_reasoning_elements": missing,
        "misconceptions": _misconceptions(step, answer),
        "safety_gap": safety_gap,
        "asked_about": asked_about,
        "turn_count": len(tutor_turns),
        "student_turn_count": len(student_turns),
        "max_turns": MAX_TUTOR_TURNS_PER_STEP,
        "completion_state": completion,
    }


def next_tutor_question(case: dict, step: str, student_answer: str, state: dict) -> str:
    """One focused question, with a rule fallback and a hidden-answer guard."""

    fallback = _rule_question(step, state)
    question = llm_service.chat_completion(
        TUTOR_SYSTEM_PROMPT,
        TUTOR_USER_TEMPLATE.format(
            case_context=prompt_json(_visible_case(case)),
            step=step,
            student_answer=(student_answer or "（学生尚未作答）")[:1500],
            reasoning_state=prompt_json(state),
        ),
        fallback,
    )
    question = (question or "").strip()
    if not question:
        return fallback
    if leaks_hidden_answer(question, case, student_text=student_answer):
        logger.warning("tutor question rejected: hidden answer leakage step=%s", step)
        return fallback
    return question


# A short label such as "系统性红斑狼疮" is still the answer when the tutor names
# it. Long hidden material is caught by fragment matching; the standard diagnosis
# by normalised label matching (allowed only when the student already used it).
LONG_FRAGMENT_THRESHOLD = 12
MIN_LABEL_LENGTH = 3


def normalize_for_matching(text: str) -> str:
    """Lower-case, drop punctuation/spacing so near-exact matches are comparable."""

    return re.sub(r"[\s，。、；：？！,.;:?!\"'（）()《》\-—]+", "", (text or "").lower())


def _hidden_labels(case: dict) -> list[str]:
    diagnosis = case.get("standard_diagnosis")
    labels: list[str] = []
    if isinstance(diagnosis, str):
        labels.append(diagnosis)
        # "系统性红斑狼疮（SLE）" -> also guard the bare disease name.
        labels.extend(part for part in re.split(r"[（(]/", diagnosis) if part)
    return [label.strip() for label in labels if len(label.strip()) >= MIN_LABEL_LENGTH]


def leaks_hidden_answer(text: str, case: dict, student_text: str = "") -> bool:
    """Reject a tutor question that reproduces hidden case material.

    - Long hidden values (treatment plan, rubric entries, differential items) are
      rejected as fragments.
    - Short labels (the standard diagnosis) are rejected when the question states
      them, or contains them verbatim. A question that only re-uses a disease name
      the student already wrote is allowed, because it adds no information.
    """

    hidden_values = [
        case.get("treatment_plan"),
        case.get("rubric"),
        case.get("differential_diagnosis"),
    ]
    for value in hidden_values:
        if isinstance(value, dict):
            candidates = [str(item) for item in value.values()]
        elif isinstance(value, list):
            candidates = [str(item) for item in value]
        else:
            candidates = [str(value)] if value else []
        for candidate in candidates:
            normalized = candidate.strip()
            if len(normalized) >= LONG_FRAGMENT_THRESHOLD and normalized in text:
                return True

    normalized_question = normalize_for_matching(text)
    normalized_student = normalize_for_matching(student_text)
    for label in _hidden_labels(case):
        normalized_label = normalize_for_matching(label)
        if not normalized_label or normalized_label not in normalized_question:
            continue
        if normalized_label in normalized_student:
            # The student already named it; the tutor is not revealing anything.
            continue
        return True
    return False


def _visible_case(case: dict) -> dict:
    """Case fields a student may already see; hidden answers are never sent."""

    allowed = (
        "title",
        "disease_category",
        "difficulty",
        "chief_complaint",
        "history",
        "physical_exam",
        "lab_results",
        "imaging",
        "learning_objectives",
    )
    return {key: case.get(key) for key in allowed if case.get(key) is not None}


def _misconceptions(step: str, answer: str) -> list[str]:
    lowered = answer.lower()
    found: list[str] = []
    if step == "treatment" and "激素" in lowered and "感染" not in lowered:
        found.append("提出免疫抑制治疗但未先排除活动性感染")
    if step == "differential_diagnosis" and "排除" not in lowered and "鉴别" not in lowered:
        found.append("列出了鉴别诊断但没有给出排除逻辑")
    if step == "initial_diagnosis" and "因为" not in lowered and "依据" not in lowered:
        found.append("给出了诊断但缺少支持依据")
    if step == "key_information" and len(answer.strip()) < 30:
        found.append("关键信息提取过于简略")
    return found


def _rule_question(step: str, state: dict) -> str:
    missing = state.get("missing_reasoning_elements") or []
    asked = set(state.get("asked_about") or [])
    not_yet_asked = [item for item in missing if item not in asked]
    first_missing = (not_yet_asked or missing or [None])[0]
    if state.get("misconceptions"):
        return f"关于「{state['misconceptions'][0]}」，你的推理依据是什么？"
    if first_missing:
        return f"你的回答还没有涉及「{first_missing}」，它如何影响你的判断？"
    if step == "treatment":
        return "如果患者合并活动性感染，你的方案需要怎样调整？为什么？"
    if step == "examination":
        return "这些检查里哪一项最能改变你的处理决策？为什么？"
    if step == "differential_diagnosis":
        return "请按危险程度排列你的鉴别诊断，并说明最先排除哪一个。"
    if step == "initial_diagnosis":
        return "哪些证据支持你的首要诊断，又有哪些证据与它矛盾？"
    return "这些关键信息中，哪一条最能改变你的诊断排序？为什么？"


def normalise_step(step: str) -> str:
    if step not in REQUIRED_STEP_KEYS:
        raise ValueError("Unknown reasoning step")
    return step


def load_state(raw: str) -> dict:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
