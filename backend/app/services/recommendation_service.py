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
    return {
        "case": case,
        "pathway_stage": stage,
        "reason": _recommendation_reason(latest, case),
    }


def build_learning_pathway(student_profile: dict, recent_activity: dict) -> dict:
    current_stage = determine_pathway_stage(student_profile)
    weak_keys = weakest_abilities(student_profile, limit=5, use_expanded=True)
    recommended_tasks: list[dict] = []

    for key in weak_keys:
        recommended_tasks.extend(_tasks_for_ability(key, student_profile, recent_activity))

    unique_tasks = _dedupe_tasks(recommended_tasks)
    return {
        "current_stage": current_stage,
        "weak_abilities": weak_keys,
        "recommended_tasks": unique_tasks,
    }


def _pick_case(scores: dict, cases: list[dict]) -> dict:
    title_preference = None
    if scores.get("differential_diagnosis", 100) < 60:
        title_preference = ["SLE与感染鉴别病例", "成人Still病病例"]
    elif scores.get("medical_knowledge", 100) < 60:
        title_preference = ["SLE基础病例"]
    elif scores.get("clinical_decision", 100) < 60:
        title_preference = ["ANCA相关血管炎病例"]
    elif scores.get("total_score", 0) > 85:
        title_preference = ["皮肌炎/抗合成酶综合征病例"]

    if title_preference:
        for title in title_preference:
            for case in cases:
                if title in case["title"]:
                    return case
    return cases[0]


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


def _tasks_for_ability(key: str, profile: dict, recent_activity: dict) -> list[dict]:
    tasks = []
    score = profile.get(key, 100)
    if key == "medical_knowledge":
        tasks.append(
            _first_task(
                recent_activity.get("knowledge_units", []),
                "knowledge_unit",
                f"医学知识得分 {score}，建议先补齐核心概念。",
                95,
            )
        )
        tasks.append(
            _case_task(
                recent_activity.get("cases", []),
                ["基础", "SLE基础", "生成病例"],
                f"医学知识薄弱，需要通过基础病例迁移应用。",
                90,
            )
        )
    elif key == "key_information":
        tasks.append(
            _first_task(
                recent_activity.get("sp_cases", []),
                "sp_case",
                f"关键信息提取得分 {score}，建议通过 SP 问诊训练信息收集。",
                95,
            )
        )
        tasks.append(
            _first_task(
                recent_activity.get("clinical_skills", []),
                "clinical_skill",
                "通过查体或操作流程训练补充体征信息采集能力。",
                90,
            )
        )
        tasks.append(
            _case_task(
                recent_activity.get("cases", []),
                ["基础", "SLE基础"],
                "通过基础病例练习关键阳性和关键阴性提取。",
                88,
            )
        )
    elif key == "differential_diagnosis":
        tasks.append(
            _case_task(
                recent_activity.get("cases", []),
                ["感染", "成人Still", "鉴别", "进阶"],
                f"鉴别诊断得分 {score}，建议训练复杂症状群病例。",
                96,
            )
        )
        tasks.append(
            _first_task(
                recent_activity.get("sp_cases", []),
                "sp_case",
                "通过 SP 问诊补充鉴别诊断所需病史线索。",
                86,
            )
        )
    elif key == "evidence_integration":
        tasks.append(
            _case_task(
                recent_activity.get("cases", []),
                ["血管炎", "感染", "进阶"],
                f"证据整合得分 {score}，建议训练支持证据与反证权重。",
                94,
            )
        )
        tasks.append(
            _first_task(
                recent_activity.get("guidelines", []),
                "guideline",
                "结合指南 PICO 练习提升证据整合。",
                84,
            )
        )
    elif key == "clinical_decision":
        tasks.append(
            _first_task(
                recent_activity.get("guidelines", []),
                "guideline",
                f"临床决策得分 {score}，建议先阅读治疗推荐和风险监测。",
                94,
            )
        )
        tasks.append(
            _first_task(
                recent_activity.get("clinical_skills", []),
                "clinical_skill",
                "通过技能站训练将适应证、禁忌证和安全监测纳入决策。",
                90,
            )
        )
        tasks.append(
            _case_task(
                recent_activity.get("cases", []),
                ["血管炎", "皮肌炎", "高阶", "进阶"],
                "通过高阶病例练习治疗决策、感染筛查和随访计划。",
                88,
            )
        )
    elif key == "evidence_based_medicine":
        tasks.append(
            _first_task(
                recent_activity.get("guidelines", []),
                "guideline",
                f"循证医学得分 {score}，建议完成指南 PICO 学习任务。",
                96,
                source_evidence="指南PICO训练记录提示证据等级和临床适用性表达不足。",
            )
        )
    elif key == "skill_operation":
        tasks.append(
            _first_task(
                recent_activity.get("clinical_skills", []),
                "clinical_skill",
                f"技能操作得分 {score}，建议完成临床技能步骤训练。",
                95,
                source_evidence="技能步骤评分提示完整性、顺序或安全性仍需加强。",
            )
        )
    elif key == "communication":
        tasks.append(
            _first_task(
                recent_activity.get("sp_cases", []),
                "sp_case",
                f"医患沟通得分 {score}，建议通过 SP 问诊训练表达结构与回应方式。",
                94,
                source_evidence="SP-OSCE沟通表达评分低于目标水平。",
            )
        )
    elif key == "humanistic_care":
        tasks.append(
            _first_task(
                recent_activity.get("sp_cases", []),
                "sp_case",
                f"人文关怀得分 {score}，建议通过标准化病人训练共情回应。",
                92,
                source_evidence="SP-OSCE人文关怀维度提示需加强患者担忧回应。",
            )
        )
    return [task for task in tasks if task]


def _first_task(
    items: list[dict],
    task_type: str,
    reason: str,
    priority: int,
    source_evidence: str | None = None,
) -> dict | None:
    if not items:
        return None
    item = items[0]
    return _make_task(task_type, item, reason, priority, source_evidence)


def _case_task(cases: list[dict], title_keywords: list[str], reason: str, priority: int) -> dict | None:
    for keyword in title_keywords:
        for case in cases:
            text = f"{case.get('title', '')} {case.get('difficulty', '')} {case.get('disease_category', '')}"
            if keyword in text:
                return _make_task("case", case, reason, priority)
    return _first_task(cases, "case", reason, priority)


def _make_task(
    task_type: str,
    item: dict,
    reason: str,
    priority: int,
    source_evidence: str | None = None,
) -> dict:
    target_abilities = _target_abilities(task_type)
    return {
        "type": task_type,
        "id": item["id"],
        "title": item["title"],
        "reason": reason,
        "priority": priority,
        "target_abilities": target_abilities,
        "source_evidence": source_evidence or _source_evidence(task_type, target_abilities),
        "expected_lift": _expected_lift(priority),
        "difficulty_label": item.get("difficulty") or item.get("level") or "自适应",
        "next_step_label": _next_step_label(task_type),
    }


def _dedupe_tasks(tasks: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for task in sorted(tasks, key=lambda item: item["priority"], reverse=True):
        key = (task["type"], task["id"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(task)
    return unique


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
        return "+12%"
    if priority >= 90:
        return "+10%"
    if priority >= 85:
        return "+8%"
    return "+5%"


def _next_step_label(task_type: str) -> str:
    mapping = {
        "knowledge_unit": "进入知识单元",
        "clinical_skill": "进入技能训练",
        "case": "开始病例训练",
        "guideline": "进入指南PICO训练",
        "sp_case": "进入SP问诊训练",
    }
    return mapping.get(task_type, "进入训练")
