"""Machine-readable tags for every trainable catalog item.

§14 of the architecture: the adaptive planner must be structured — abilities,
difficulty, prerequisites, disease category — instead of matching on how an item
happens to be titled. Tags are derived from each module's structured content
fields; the title is only a last-resort fallback when those fields carry no
signal at all.
"""

from app.services.serializers import ABILITY_LABELS, CORE_ABILITIES, ALL_COMPETENCIES

ABILITY_KEYWORDS = {
    "medical_knowledge": ("诊断", "疾病", "知识", "识别", "概念", "分类标准"),
    "key_information": ("信息", "病史", "查体", "采集", "体征", "问诊"),
    "differential_diagnosis": ("鉴别", "排除", "鉴别诊断"),
    "evidence_integration": ("证据", "整合", "反证", "权重", "支持", "矛盾"),
    "clinical_decision": ("治疗", "决策", "监测", "随访", "安全", "风险", "禁忌"),
    "evidence_based_medicine": ("指南", "循证", "文献", "证据等级", "推荐"),
    "skill_operation": ("操作", "步骤", "无菌", "查体", "技能"),
    "communication": ("沟通", "表达", "共情", "告知", "问诊"),
    "humanistic_care": ("人文", "关怀", "担忧", "尊重", "情绪"),
}

DIFFICULTY_RANK = {
    "基础": 1,
    "basic": 1,
    "初级": 1,
    "进阶": 2,
    "intermediate": 2,
    "中级": 2,
    "高阶": 3,
    "advanced": 3,
    "高级": 3,
}

# Minimum competency required before a harder item is offered.
PREREQUISITES_BY_RANK = {
    1: {},
    2: {"medical_knowledge": 55},
    3: {"medical_knowledge": 65, "differential_diagnosis": 60},
}

CONTENT_FIELDS = {
    "case": ("learning_objectives", "chief_complaint", "disease_category", "difficulty"),
    "knowledge_unit": ("learning_objectives", "key_points", "category", "level"),
    "clinical_skill": ("indication", "category", "common_errors", "difficulty"),
    "guideline": ("summary", "disease_category", "source_type"),
    "sp_case": ("expected_tasks", "disease_category", "difficulty"),
}

MODULE_LABELS = {
    "case": "病例训练",
    "knowledge_unit": "基础知识",
    "clinical_skill": "临床技能",
    "guideline": "循证指南",
    "sp_case": "标准化病人",
}


def difficulty_rank(value: str | None) -> int:
    return DIFFICULTY_RANK.get(str(value or "").strip().lower(), 1)


def item_tags(module_type: str, item: dict) -> dict:
    """Abilities, difficulty and prerequisites for one catalog item."""

    fields = CONTENT_FIELDS.get(module_type, ())
    text = " ".join(_flatten(item.get(field)) for field in fields)
    abilities = [
        ability
        for ability, keywords in ABILITY_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
    if not abilities:
        abilities = [ability for ability, keywords in ABILITY_KEYWORDS.items() if any(k in _flatten(item.get("title")) for k in keywords)]
    if not abilities:
        abilities = list(CORE_ABILITIES)
    rank = difficulty_rank(item.get("difficulty") or item.get("level"))
    return {
        "abilities": abilities,
        "ability_labels": [ABILITY_LABELS.get(ability, ability) for ability in abilities],
        "difficulty": item.get("difficulty") or item.get("level"),
        "difficulty_rank": rank,
        "disease_category": item.get("disease_category") or item.get("category"),
        "prerequisites": PREREQUISITES_BY_RANK.get(rank, {}),
    }


def _flatten(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(item) for item in value)
    return str(value)


def core_ability_keys() -> list[str]:
    return list(CORE_ABILITIES)


def all_ability_keys() -> list[str]:
    return list(ALL_COMPETENCIES)
