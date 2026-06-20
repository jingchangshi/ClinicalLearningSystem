from app.services.serializers import CORE_ABILITIES

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


def weakest_abilities(profile: dict, limit: int = 2) -> list[str]:
    return sorted(CORE_ABILITIES, key=lambda key: profile[key])[:limit]


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
    weak_keys = weakest_abilities(student_profile, limit=4)
    recommended_tasks: list[dict] = []

    for key in weak_keys:
        recommended_tasks.extend(_tasks_for_ability(key, student_profile, recent_activity))

    if student_profile.get("communication", 100) < 70 or student_profile.get("humanistic_care", 100) < 70:
        task = _first_task(
            recent_activity.get("sp_cases", []),
            "sp_case",
            "沟通或人文关怀评分偏低，建议通过标准化病人训练问诊表达和共情回应。",
            75,
        )
        if task:
            recommended_tasks.append(task)

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
            )
        )
    return [task for task in tasks if task]


def _first_task(items: list[dict], task_type: str, reason: str, priority: int) -> dict | None:
    if not items:
        return None
    item = items[0]
    return _make_task(task_type, item, reason, priority)


def _case_task(cases: list[dict], title_keywords: list[str], reason: str, priority: int) -> dict | None:
    for keyword in title_keywords:
        for case in cases:
            text = f"{case.get('title', '')} {case.get('difficulty', '')} {case.get('disease_category', '')}"
            if keyword in text:
                return _make_task("case", case, reason, priority)
    return _first_task(cases, "case", reason, priority)


def _make_task(task_type: str, item: dict, reason: str, priority: int) -> dict:
    return {
        "type": task_type,
        "id": item["id"],
        "title": item["title"],
        "reason": reason,
        "priority": priority,
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
