#!/usr/bin/env python3
"""Compare AI task policies on latency and quality. Spends real provider quota.

Run it deliberately, never from pytest:

    cd backend
    uv run --python 3.11 --with-requirements requirements.txt \\
        python tools/ai_benchmark.py --runs 3 --tasks tutor_question,case_evaluation

What it answers: is the *default* policy in ``app.core.ai_policy`` the right
trade-off for this task, on this provider, today? Each task is run under several
policy variants (the default, the pre-policy global configuration, and a cheaper
option) with fixed, synthetic, non-sensitive inputs.

What it writes: task, policy, provider, model, thinking, effort, max_tokens,
latency, success, fallback, schema validity and quality-gate results. Never the
prompt, the response body, a reasoning trace or a credential.
"""

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.ai_policy import AI_TASK_POLICIES, AITaskPolicy, with_overrides  # noqa: E402
from app.core.llm_config import (  # noqa: E402
    LLM_CONFIGURED,
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_REASONING_EFFORT,
    LLM_TIMEOUT_SECONDS,
)
from app.llm.prompts.case_generation import CASE_GENERATION_SYSTEM_PROMPT  # noqa: E402
from app.llm.prompts.evaluation import (  # noqa: E402
    CASE_EVALUATION_SYSTEM_PROMPT,
    CASE_EVALUATION_USER_TEMPLATE,
    GUIDELINE_RATIONALE_SYSTEM_PROMPT,
    GUIDELINE_RATIONALE_USER_TEMPLATE,
    SP_FEEDBACK_SYSTEM_TEMPLATE,
    SP_PATIENT_SYSTEM_TEMPLATE,
    SKILL_FEEDBACK_SYSTEM_PROMPT,
    SKILL_FEEDBACK_USER_TEMPLATE,
)
from app.llm.prompts.insight import TEACHER_INSIGHT_SYSTEM_PROMPT, TEACHER_INSIGHT_USER_TEMPLATE  # noqa: E402
from app.llm.prompts.pathway import (  # noqa: E402
    RECOMMENDATION_EXPLANATION_BATCH_SYSTEM_PROMPT,
    RECOMMENDATION_EXPLANATION_SYSTEM_PROMPT,
    RECOMMENDATION_EXPLANATION_USER_TEMPLATE,
)
from app.services.case_generator import validate_case_payload  # noqa: E402
from app.services.llm_service import PROBE_PROMPT, llm_service, prompt_json  # noqa: E402
from app.services.scoring_llm import CaseEvaluation  # noqa: E402
from app.services.tutor_service import TUTOR_SYSTEM_PROMPT, TUTOR_USER_TEMPLATE  # noqa: E402
from app.services.tutor_service import leaks_hidden_answer  # noqa: E402

# --- fixed, synthetic, non-sensitive inputs ------------------------------------

SYNTHETIC_CASE = {
    "title": "发热伴皮疹（合成病例）",
    "disease_category": "SLE",
    "difficulty": "基础",
    "learning_objectives": ["关键信息提取", "鉴别诊断"],
    "chief_complaint": "反复发热伴面部皮疹两周",
    "lab_results": "ANA 阳性，补体降低，尿蛋白 1+",
    "standard_diagnosis": "系统性红斑狼疮",
    "differential_diagnosis": ["感染", "淋巴瘤"],
    "treatment_plan": "激素联合免疫抑制剂，治疗前感染筛查并随访监测。",
    "rubric": {"medical_knowledge": "诊断依据完整"},
}

SYNTHETIC_ANSWERS = [
    {"step": "key_information", "answer_text": "发热、皮疹、ANA阳性、尿蛋白，需要评估器官受累。"},
    {"step": "initial_diagnosis", "answer_text": "考虑系统性红斑狼疮，依据症状、抗体和器官受累。"},
    {"step": "differential_diagnosis", "answer_text": "需要排除感染、AOSD、HLH 与淋巴瘤。"},
    {"step": "examination", "answer_text": "补充补体、抗dsDNA、尿蛋白定量评估活动度。"},
    {"step": "treatment", "answer_text": "激素联合免疫抑制剂，治疗前感染筛查，随访监测不良反应。"},
]

WEAK_DIMENSIONS = [
    {"key": "differential_diagnosis", "label": "鉴别诊断", "score": 58.0, "level": "偏弱"},
    {"key": "evidence_integration", "label": "证据整合", "score": 61.0, "level": "偏弱"},
]
TRAINING_SUMMARY = {"training_total_count": 42, "module_counts": {"knowledge": 10, "case": 20, "sp": 12}}

RECOMMENDED_TASKS = [
    {
        "task_key": "case:1",
        "title": "发热皮疹鉴别病例",
        "type": "case",
        "priority": 92,
        "fallback_reason": "鉴别诊断链条需要拓宽，推荐继续训练该病例。",
        "target_abilities": ["鉴别诊断"],
    },
    {
        "task_key": "knowledge_unit:2",
        "title": "发热皮疹的鉴别诊断",
        "type": "knowledge_unit",
        "priority": 88,
        "fallback_reason": "医学知识得分 58，先补齐核心概念再做题。",
        "target_abilities": ["医学知识"],
    },
]


@dataclass
class QualityResult:
    schema_valid: bool
    passed: bool
    checks: dict
    fallback_used: bool


def _text_checks(text: str, *, max_chars: int) -> tuple[bool, dict]:
    stripped = (text or "").strip()
    checks = {
        "non_empty": bool(stripped),
        "concision": len(stripped) <= max_chars,
    }
    return all(checks.values()), checks


# --- task scenarios ------------------------------------------------------------


def _case_evaluation_task(run) -> QualityResult:
    fallback = {"_fallback": True}
    raw = run(
        CASE_EVALUATION_SYSTEM_PROMPT,
        CASE_EVALUATION_USER_TEMPLATE.format(
            case=prompt_json(SYNTHETIC_CASE),
            rubric=prompt_json(SYNTHETIC_CASE["rubric"]),
            answers=prompt_json(SYNTHETIC_ANSWERS),
            rule_evidence=prompt_json({"total_score": 72.0}),
        ),
        fallback,
        json_mode=True,
    )
    schema_valid, schema_error = False, "fallback"
    checks: dict = {}
    if isinstance(raw, dict) and raw != fallback:
        try:
            evaluation = CaseEvaluation.model_validate(raw)
            schema_valid = set(evaluation.dimensions) == {
                "medical_knowledge",
                "key_information",
                "differential_diagnosis",
                "evidence_integration",
                "clinical_decision",
                "evidence_based_medicine",
            }
            checks = {
                "has_dimension_scores": all(
                    isinstance(item.score, (int, float)) for item in evaluation.dimensions.values()
                ),
                "has_confidence": all(
                    isinstance(item.confidence, (int, float)) for item in evaluation.dimensions.values()
                ),
                "has_evidence": all(bool(item.evidence) for item in evaluation.dimensions.values()),
                "has_missing_points": all(
                    isinstance(item.missing_points, list) for item in evaluation.dimensions.values()
                ),
                "has_overall_feedback": bool(evaluation.overall_feedback.strip()),
                "safety_flags_present": isinstance(evaluation.safety_flags, list),
            }
            schema_error = None
        except Exception as error:  # schema failure is exactly what this gate looks for
            schema_error = type(error).__name__
    return QualityResult(schema_valid, schema_valid and all(checks.values()), checks or {"schema": False}, raw == fallback)


def _tutor_question_task(run) -> QualityResult:
    fallback = "请说明你目前判断的证据，以及还有哪些证据与它矛盾？为什么？"
    text = run(
        TUTOR_SYSTEM_PROMPT,
        TUTOR_USER_TEMPLATE.format(
            case_context=prompt_json(
                {"title": SYNTHETIC_CASE["title"], "chief_complaint": SYNTHETIC_CASE["chief_complaint"]}
            ),
            step="differential_diagnosis",
            student_answer=SYNTHETIC_ANSWERS[2]["answer_text"],
            reasoning_state=prompt_json({"dimension": "differential_diagnosis", "asked_about": []}),
        ),
        fallback,
    )
    passed, checks = _text_checks(text, max_chars=200)
    checks["no_hidden_answer_leak"] = not leaks_hidden_answer(text, SYNTHETIC_CASE)
    checks["is_a_question"] = "?" in text or "？" in text
    return QualityResult(True, passed and all(checks.values()), checks, text == fallback)


def _recommendation_explanation_task(run) -> QualityResult:
    # Same call shape the pathway enrichment uses: one JSON answer for several
    # already-decided tasks.
    raw = run(
        RECOMMENDATION_EXPLANATION_BATCH_SYSTEM_PROMPT,
        prompt_json(
            {
                "profile": {"主要能力缺口": "鉴别诊断=58.0", "differential_diagnosis": 58.0},
                "recent_evidence": {"evidence_summary": [{"module": "case", "latest_score": 58.0}]},
                "tasks": RECOMMENDED_TASKS,
            }
        ),
        {"explanations": {}},
        json_mode=True,
    )
    explanations = raw.get("explanations") if isinstance(raw, dict) else None
    if not isinstance(explanations, dict) or not explanations:
        return QualityResult(False, False, {"explanations": False}, not explanations)
    text = " ".join(str(value) for value in explanations.values())
    checks = {
        "explanations_returned": True,
        "mentions_weakness": any(key in text for key in ("鉴别", "诊断", "知识")),
        "no_fabricated_gain": "提升" not in text,
        "concision": len(text) <= 600,
    }
    return QualityResult(True, all(checks.values()), checks, False)


def _teacher_insight_task(run) -> QualityResult:
    fallback = "班级共性短板为鉴别诊断，建议安排鉴别诊断专项训练。"
    text = run(
        TEACHER_INSIGHT_SYSTEM_PROMPT,
        TEACHER_INSIGHT_USER_TEMPLATE.format(
            weak_dimensions=json.dumps(WEAK_DIMENSIONS, ensure_ascii=False),
            training_summary=json.dumps(TRAINING_SUMMARY, ensure_ascii=False),
        ),
        fallback,
    )
    passed, checks = _text_checks(text, max_chars=400)
    checks["cites_actual_weakness"] = "鉴别诊断" in text or "证据整合" in text
    return QualityResult(True, passed and all(checks.values()), checks, text == fallback)


def _guideline_rationale_task(run) -> QualityResult:
    fallback = "系统依据 PICO 完整性等五项计算，综合得分为 82。"
    text = run(
        GUIDELINE_RATIONALE_SYSTEM_PROMPT,
        GUIDELINE_RATIONALE_USER_TEMPLATE.format(
            title="EULAR SLE 推荐",
            payload={"clinical_question": "激素如何减量", "pico": "P/I/C/O"},
            detail={"score": 82, "pico_completeness": 88, "risk_individualization": 70},
        ),
        fallback,
    )
    passed, checks = _text_checks(text, max_chars=400)
    checks["ties_to_score"] = "82" in text
    return QualityResult(True, passed and all(checks.values()), checks, text == fallback)


def _sp_patient_task(run) -> QualityResult:
    text = run(
        SP_PATIENT_SYSTEM_TEMPLATE.format(sp_case_json=prompt_json(SYNTHETIC_CASE)),
        prompt_json(
            {
                "transcript": [{"role": "student", "message": "您最近发热多久了？还有其他不舒服吗？"}],
                "student_message": "您最近发热多久了？还有其他不舒服吗？",
            }
        ),
        "（患者沉默）",
    )
    passed, checks = _text_checks(text, max_chars=200)
    # An SP answer is a patient utterance; it must not narrate that it is a model.
    checks["stays_in_character"] = not any(marker in text for marker in ("AI", "模型", "assistant"))
    return QualityResult(True, passed and all(checks.values()), checks, text.strip() == "（患者沉默）")


def _sp_evaluation_task(run) -> QualityResult:
    raw = run(
        SP_FEEDBACK_SYSTEM_TEMPLATE.format(sp_case_json=prompt_json(SYNTHETIC_CASE)),
        prompt_json({"transcript": [{"role": "student", "message": "您最近发热多久了？"}], "diagnosis_summary": "SLE"}),
        {"_fallback": True},
        json_mode=True,
    )
    if not isinstance(raw, dict) or raw == {"_fallback": True}:
        return QualityResult(False, False, {"structured_feedback": False}, True)
    checks = {
        "structured_feedback": True,
        "has_required_keys": all(key in raw for key in ("communication_score", "reasoning_score", "feedback"))
        or bool(raw.get("total_score")),
    }
    return QualityResult(True, all(checks.values()), checks, False)


def _skill_feedback_task(run) -> QualityResult:
    fallback = "技能步骤基本完成，注意安全要点。"
    text = run(
        SKILL_FEEDBACK_SYSTEM_PROMPT,
        SKILL_FEEDBACK_USER_TEMPLATE.format(
            score=78, safety_score=70, missed_steps=["消毒"], errors=["未核对患者身份"]
        ),
        fallback,
    )
    passed, checks = _text_checks(text, max_chars=400)
    checks["mentions_a_gap"] = any(key in text for key in ("消毒", "核对", "安全"))
    return QualityResult(True, passed and all(checks.values()), checks, text == fallback)


def _case_generation_task(run) -> QualityResult:
    fallback = {"_fallback": True}
    raw = run(
        CASE_GENERATION_SYSTEM_PROMPT,
        prompt_json({"生成要求": {"disease_category": "SLE", "difficulty": "基础"}, "必须字段": ["title"]}),
        fallback,
        json_mode=True,
    )
    if not isinstance(raw, dict) or raw == fallback:
        return QualityResult(False, False, {"valid_case": False}, True)
    try:
        validate_case_payload(raw)
        return QualityResult(True, True, {"valid_case": True, "required_fields": True}, False)
    except ValueError:
        return QualityResult(False, False, {"valid_case": False}, False)


def _ai_probe_task(run) -> QualityResult:
    """The cheapest possible call: is the provider reachable at all?"""

    text = run(PROBE_PROMPT, PROBE_PROMPT, "fallback")
    passed, checks = _text_checks(text, max_chars=24)
    checks["answered"] = text.strip().lower().startswith("ok")
    return QualityResult(True, passed and all(checks.values()), checks, text.strip() == "fallback")


TASKS = {
    "ai_probe": _ai_probe_task,
    "case_evaluation": _case_evaluation_task,
    "tutor_question": _tutor_question_task,
    "sp_patient": _sp_patient_task,
    "recommendation_explanation": _recommendation_explanation_task,
    "teacher_insight": _teacher_insight_task,
    "guideline_rationale": _guideline_rationale_task,
    "sp_evaluation": _sp_evaluation_task,
    "skill_feedback": _skill_feedback_task,
    "case_generation": _case_generation_task,
}


# --- policy variants -----------------------------------------------------------


# Task-specific candidates worth measuring beyond the three standard ones.
EXTRA_VARIANTS: dict[str, dict[str, AITaskPolicy]] = {
    "tutor_question": {
        # A thinking trace consumes the token budget before the answer starts, so
        # a small max_tokens yields empty content and a retry. Measure it instead
        # of guessing.
        "thinking_low_4k": with_overrides(
            "tutor_question", thinking=True, reasoning_effort="low", temperature=None,
            max_tokens=4096, timeout_seconds=30,
        ),
        "no_thinking": with_overrides(
            "tutor_question", thinking=False, reasoning_effort=None, temperature=0.3,
            max_tokens=600, timeout_seconds=30,
        ),
    },
    "recommendation_explanation": {
        "thinking_low_4k": with_overrides(
            "recommendation_explanation", thinking=True, reasoning_effort="low", temperature=None,
            max_tokens=4096, timeout_seconds=30,
        ),
    },
    "sp_patient": {
        "no_thinking": with_overrides(
            "sp_patient", thinking=False, reasoning_effort=None, temperature=0.3,
            max_tokens=600, timeout_seconds=25,
        ),
    },
    "case_evaluation": {
        "no_thinking_3k": with_overrides(
            "case_evaluation", thinking=False, reasoning_effort=None, temperature=0.2,
            max_tokens=3000, timeout_seconds=45,
        ),
    },
}


def variants_for(task_type: str) -> dict[str, AITaskPolicy]:
    default = AI_TASK_POLICIES[task_type]
    baseline = replace(
        default,
        thinking=True,
        reasoning_effort=LLM_REASONING_EFFORT,
        temperature=None,
        max_tokens=LLM_MAX_TOKENS,
        timeout_seconds=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )
    cheap = with_overrides(
        task_type,
        thinking=False,
        reasoning_effort=None,
        temperature=0.2,
        max_tokens=400,
        timeout_seconds=20,
        max_retries=1,
    )
    return {
        "default": default,
        "pre_policy_baseline": baseline,
        "cheap": cheap,
        **EXTRA_VARIANTS.get(task_type, {}),
    }


def run_scenario(task_type: str, policy: AITaskPolicy):
    scenario = TASKS[task_type]

    def call(system_prompt: str, user_prompt: str, fallback, json_mode: bool = False):
        if json_mode:
            return llm_service.chat_json(system_prompt, user_prompt, fallback, task_type=task_type, policy=policy)
        return llm_service.chat_completion(system_prompt, user_prompt, fallback, task_type=task_type, policy=policy)

    return scenario(call)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", default=",".join(TASKS))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--variants", default="default,pre_policy_baseline")
    parser.add_argument("--json-out", default=os.getenv("CLINPATH_BENCHMARK_OUT"))
    parser.add_argument("--dry-run", action="store_true", help="print the matrix without calling the provider")
    args = parser.parse_args()

    if args.dry_run:
        for task_type in args.tasks.split(","):
            task_type = task_type.strip()
            if task_type not in TASKS:
                print(f"unknown task: {task_type}", file=sys.stderr)
                return 2
            for name, policy in variants_for(task_type).items():
                print(
                    f"{task_type:<26}{name:<22}thinking={policy.thinking!s:<6}"
                    f"effort={str(policy.reasoning_effort):<6}max_tokens={policy.max_tokens:<6}"
                    f"timeout={policy.timeout_seconds}s"
                )
        return 0

    if not LLM_CONFIGURED:
        print("no provider is configured (LLM_API_KEY/LLM_BASE_URL/LLM_MODEL)", file=sys.stderr)
        return 2

    selected_variants = [name.strip() for name in args.variants.split(",") if name.strip()]
    rows = []
    print(f"provider={LLM_PROVIDER} model={LLM_MODEL} runs={args.runs}")
    for task_type in [name.strip() for name in args.tasks.split(",") if name.strip()]:
        if task_type not in TASKS:
            print(f"unknown task: {task_type}", file=sys.stderr)
            return 2
        for variant_name in selected_variants:
            available = variants_for(task_type)
            if variant_name not in available:
                continue
            policy = available[variant_name]
            latencies: list[float] = []
            successes = fallbacks = schema_ok = quality_ok = 0
            failures: list[str] = []
            for _ in range(args.runs):
                started = time.monotonic()
                try:
                    result = run_scenario(task_type, policy)
                except Exception as error:
                    failures.append(type(error).__name__)
                    latencies.append((time.monotonic() - started) * 1000)
                    continue
                latencies.append((time.monotonic() - started) * 1000)
                successes += 1
                schema_ok += int(result.schema_valid)
                quality_ok += int(result.passed)
                fallbacks += int(result.fallback_used)
            row = {
                "task": task_type,
                "variant": variant_name,
                "provider": LLM_PROVIDER,
                "model": LLM_MODEL,
                "thinking": policy.thinking,
                "reasoning_effort": policy.reasoning_effort,
                "max_tokens": policy.max_tokens,
                "timeout_seconds": policy.timeout_seconds,
                "runs": args.runs,
                "success": successes,
                "fallback": fallbacks,
                "schema_valid": schema_ok,
                "quality_pass": quality_ok,
                "latency_ms_p50": round(statistics.median(latencies)) if latencies else None,
                "latency_ms_max": round(max(latencies)) if latencies else None,
                "errors": sorted(set(failures)),
            }
            rows.append(row)
            print(
                f"{task_type:<26}{variant_name:<22}ok={successes}/{args.runs} "
                f"p50={row['latency_ms_p50']}ms max={row['latency_ms_max']}ms "
                f"schema={schema_ok}/{args.runs} quality={quality_ok}/{args.runs} fallback={fallbacks}"
            )

    payload = {"provider": LLM_PROVIDER, "model": LLM_MODEL, "runs": args.runs, "results": rows}
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
