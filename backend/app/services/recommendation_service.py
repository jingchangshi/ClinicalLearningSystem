from app.core.ai_audit import ai_invocation
from app.services.catalog_tags import MODULE_LABELS, item_tags
from app.services.llm_service import llm_service
from app.services.serializers import ALL_COMPETENCIES, ABILITY_LABELS, CORE_ABILITIES

PATHWAY_STAGES = [
    {
        "key": "stage_1_basic_recognition",
        "title": "基础疾病识别",
        "description": "识别风湿免疫疾病的核心症状、体征和实验室线索。",
    },
    {
        "key": "stage_2_differential_reasoning",
        "title": "复杂症状鉴别",
        "description": "围绕发热、皮疹、血细胞减少等症状群建立鉴别诊断。",
    },
    {
        "key": "stage_3_clinical_decision",
        "title": "治疗决策训练",
        "description": "结合器官受累和风险评估制定治疗与监测方案。",
    },
    {
        "key": "stage_4_evidence_based_learning",
        "title": "循证医学与文献训练",
        "description": "将指南、证据等级和研究结论纳入临床决策。",
    },
]


MODULE_ACTIVITY_KEYS = {
    "case": "cases",
    "knowledge_unit": "knowledge_units",
    "clinical_skill": "clinical_skills",
    "guideline": "guidelines",
    "sp_case": "sp_cases",
}

REASON_TEMPLATES = {
    "knowledge_unit": "医学知识得分 {score}，先补齐核心概念再做题。",
    "clinical_skill": "技能操作得分 {score}，通过步骤训练补足操作与安全要点。",
    "case": "该病例的推理目标直接命中当前能力缺口（{score}），用于迁移应用。",
    "guideline": "循证医学得分 {score}，通过指南 PICO 训练证据等级与推荐表达。",
    "sp_case": "信息采集与沟通得分 {score}，通过标准化病人问诊训练。",
}


def determine_pathway_stage(profile: dict) -> str:
    if profile["medical_knowledge"] < 65 or profile["key_information"] < 65:
        return "stage_1_basic_recognition"
    if profile["differential_diagnosis"] < 70 or profile["evidence_integration"] < 70:
        return "stage_2_differential_reasoning"
    if profile["clinical_decision"] < 70:
        return "stage_3_clinical_decision"
    return "stage_4_evidence_based_learning"


def weakest_abilities(profile: dict, limit: int = 2, use_expanded: bool = False) -> list[str]:
    abilities = ALL_COMPETENCIES if use_expanded else CORE_ABILITIES
    return sorted(abilities, key=lambda key: profile.get(key, 100))[:limit]


def choose_recommendation(profile: dict, recent_scores: list[dict], cases: list[dict]) -> dict:
    stage = determine_pathway_stage(profile)
    latest = recent_scores[-1] if recent_scores else profile
    case = _pick_case(latest, cases)
    fallback_reason = _recommendation_reason(latest, case)
    return {
        "case": case,
        "pathway_stage": stage,
        "reason": explain_recommendation_with_llm(profile, latest, case, fallback_reason),
    }


def explain_recommendation_with_llm(profile: dict, latest_scores: dict, task: dict, fallback: str) -> str:
    weak_keys = weakest_abilities(profile, limit=3, use_expanded=True) if profile else []
    weak_text = "、".join(f"{ABILITY_LABELS.get(key, key)}={profile.get(key)}" for key in weak_keys) or "由当前任务优先级和训练类型判断"
    with ai_invocation("recommendation_explanation", evidence_ref=f"case:{task.get('id')}"):
        return llm_service.explain_recommendation(
            {"主要能力缺口": weak_text, **profile},
            latest_scores,
            task,
            fallback,
        )


def build_learning_pathway(student_profile: dict, recent_activity: dict) -> dict:
    current_stage = determine_pathway_stage(student_profile)
    weak_keys = weakest_abilities(student_profile, limit=5, use_expanded=True)
    # Learner gap -> candidate generator -> constraint filter -> ranker.
    candidates = generate_candidates(weak_keys, recent_activity)
    admissible = apply_constraints(candidates, student_profile)
    unique_tasks = rank_candidates(admissible, student_profile, weak_keys)[:3]
    with ai_invocation("recommendation_explanation", evidence_ref="learning_pathway"):
        explanations = llm_service.explain_recommendation_batch(
            student_profile,
            recent_activity.get("recent_evidence", {}),
            [
                {"task_key": _task_key(task), "title": task["title"], "type": task["type"], "priority": task["priority"], "fallback_reason": task["reason"]}
                for task in unique_tasks
            ],
        )
    for task in unique_tasks:
        task["reason"] = explanations.get(_task_key(task), task["reason"])
    return {
        "current_stage": current_stage,
        "weak_abilities": weak_keys,
        "recommended_tasks": unique_tasks,
    }


def generate_candidates(weak_abilities_order: list[str], recent_activity: dict) -> list[dict]:
    """Every catalog item whose own tags target one of the learner's weak abilities."""

    candidates: list[dict] = []
    for module_type, activity_key in MODULE_ACTIVITY_KEYS.items():
        for item in recent_activity.get(activity_key) or []:
            tags = item_tags(module_type, item)
            for ability in weak_abilities_order:
                if ability in tags["abilities"]:
                    candidates.append(
                        {
                            "type": module_type,
                            "id": item["id"],
                            "title": item["title"],
                            "matched_ability": ability,
                            "tags": tags,
                        }
                    )
                    break
    return candidates


def apply_constraints(candidates: list[dict], profile: dict) -> list[dict]:
    """Drop candidates whose difficulty the learner is not ready for.

    A weak learner is not handed advanced material it cannot act on yet; a strong
    learner is not handed material that no longer produces information.
    """

    admissible: list[dict] = []
    for candidate in candidates:
        tags = candidate["tags"]
        score = profile.get(candidate["matched_ability"], 100)
        rank = tags["difficulty_rank"]
        if score < 70 and rank >= 3:
            continue
        if score >= 80 and rank < 2:
            continue
        if any(profile.get(key, 0) < required for key, required in tags["prerequisites"].items()):
            continue
        admissible.append(candidate)
    return admissible or candidates


def rank_candidates(candidates: list[dict], profile: dict, weak_keys: list[str]) -> list[dict]:
    """Score by gap match, difficulty fit and module diversity; deterministic ties."""

    scored: list[tuple[float, str, int, dict]] = []
    for candidate in candidates:
        ability = candidate["matched_ability"]
        score = profile.get(ability, 100)
        rank = candidate["tags"]["difficulty_rank"]
        value = 0.0
        value += 3 if weak_keys and ability == weak_keys[0] else 0
        value += 2 if ability in weak_keys[:3] else 0
        # Difficulty fit: a weak learner gets foundational material, a stronger one
        # gets material that still produces information.
        value += _difficulty_fit(score, rank)
        value += min(1.0, max(0.0, (100 - score) / 100))
        scored.append((round(value, 3), candidate["type"], candidate["id"], candidate))

    ranked = [item for _, _, _, item in sorted(scored, key=lambda row: (-row[0], row[1], row[2]))]

    # Prefer a spread of module types in the final shortlist.
    selected: list[dict] = []
    seen_types: set[str] = set()
    for candidate in ranked:
        if candidate["type"] in seen_types:
            continue
        selected.append(candidate)
        seen_types.add(candidate["type"])
    for candidate in ranked:
        if candidate not in selected:
            selected.append(candidate)

    return [_task_payload(item, profile) for item in selected[:3]]


def _task_payload(candidate: dict, profile: dict) -> dict:
    module_type = candidate["type"]
    ability = candidate["matched_ability"]
    score = profile.get(ability, 100)
    template = REASON_TEMPLATES.get(module_type, "能力画像提示{ability}需要优先干预。")
    reason = template.format(score=score, ability=ABILITY_LABELS.get(ability, ability))
    return {
        "type": module_type,
        "id": candidate["id"],
        "title": candidate["title"],
        "reason": reason,
        "priority": _priority_from_gap(score),
        "target_abilities": candidate["tags"]["ability_labels"],
        "source_evidence": (
            f"能力画像：{ABILITY_LABELS.get(ability, ability)} {score}"
            f"（{MODULE_LABELS.get(module_type, module_type)}的标签命中该能力缺口）。"
        ),
        "priority_label": _expected_lift(_priority_from_gap(score)),
        "difficulty_label": candidate["tags"]["difficulty"] or "自适应",
        "next_step_label": _next_step_label(module_type),
    }


def _priority_from_gap(score: float) -> int:
    if score < 55:
        return 96
    if score < 65:
        return 92
    if score < 75:
        return 88
    return 84


def readiness_rank(score: float) -> int:
    """Which difficulty band the learner's current score calls for."""

    if score < 65:
        return 1
    if score < 80:
        return 2
    return 3


def _difficulty_fit(score: float, rank: int) -> float:
    readiness = readiness_rank(score)
    if rank == readiness:
        return 1.0
    if abs(rank - readiness) == 1:
        return 0.5
    return 0.0


def _task_key(task: dict) -> str:
    return f"{task['type']}:{task['id']}"


def _pick_case(scores: dict, cases: list[dict]) -> dict:
    """Candidate selection on structured case tags only.

    Titles are content; matching on them made the planner depend on how a case
    happens to be named. This uses the machine-readable tags from
    ``catalog_tags.item_tags`` (abilities / difficulty / category) instead.
    """

    if not cases:
        return {}
    weakest = min(CORE_ABILITIES, key=lambda key: scores.get(key, 100))
    ranked = sorted(
        cases,
        key=lambda case: (-_case_fit_score(case, weakest), case["id"]),
    )
    return ranked[0]


def _case_fit_score(case: dict, weakest_ability: str) -> int:
    tags = item_tags("case", case)
    if weakest_ability not in tags["abilities"]:
        return 0
    rank = tags["difficulty_rank"]
    # A weak learner starts on basic material; an established gap in reasoning or
    # evidence handling needs a harder case to be informative.
    if weakest_ability in {"medical_knowledge", "key_information"}:
        return 4 if rank <= 1 else 2
    return 4 if rank >= 2 else 2


def _recommendation_reason(scores: dict, case: dict) -> str:
    weakest = min(CORE_ABILITIES, key=lambda key: scores.get(key, 100))
    labels = {
        "medical_knowledge": "医学知识基础需要巩固",
        "key_information": "关键信息提取需要更系统",
        "differential_diagnosis": "鉴别诊断链条需要拓宽",
        "evidence_integration": "证据整合和反证处理需要强化",
        "clinical_decision": "治疗决策和监测计划需要训练",
        "evidence_based_medicine": "循证医学意识需要提升",
    }
    return f"{labels[weakest]}，推荐继续训练“{case['title']}”。"


def _target_abilities(task_type: str) -> list[str]:
    mapping = {
        "knowledge_unit": ["医学知识"],
        "clinical_skill": ["技能操作", "临床决策"],
        "case": ["临床推理", "鉴别诊断"],
        "guideline": ["循证医学", "临床决策"],
        "sp_case": ["关键信息提取", "医患沟通", "人文关怀"],
    }
    return mapping.get(task_type, ["临床胜任力"])


def _source_evidence(task_type: str, target_abilities: list[str]) -> str:
    return f"能力画像提示{', '.join(target_abilities)}需要优先干预，系统匹配对应训练模块。"


def _expected_lift(priority: int) -> str:
    if priority >= 95:
        return "高优先级"
    if priority >= 90:
        return "中高优先级"
    if priority >= 85:
        return "建议优先训练"
    return "建议训练"


def _next_step_label(task_type: str) -> str:
    mapping = {
        "knowledge_unit": "进入知识单元",
        "clinical_skill": "进入技能训练",
        "case": "开始病例训练",
        "guideline": "进入指南PICO训练",
        "sp_case": "进入SP问诊训练",
    }
    return mapping.get(task_type, "进入训练")
