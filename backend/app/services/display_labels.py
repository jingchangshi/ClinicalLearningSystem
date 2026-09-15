"""One Chinese display vocabulary for every teacher- and student-facing surface.

The database keeps stable English keys on purpose: they are the contract between
scoring, the competency projector and the audit trail. What a teacher or a
student reads is decided here, once, so a page cannot drift back into printing
``stage_1_basic_recognition``, ``case`` or ``module_type`` at a human.

The pathway stage titles come from ``recommendation_service.PATHWAY_STAGES``
instead of a second hand-written list, so the label and the stage definition can
never disagree.
"""

from app.services.recommendation_service import PATHWAY_STAGES
from app.services.serializers import ABILITY_LABELS

MODULE_LABELS = {
    "knowledge": "基础知识学习",
    "skill": "临床技能训练",
    "case": "病例推理训练",
    "guideline": "指南循证学习",
    "sp": "SP模拟问诊",
    # Catalog keys reach the same activity from the recommendation side.
    "knowledge_unit": "基础知识学习",
    "clinical_skill": "临床技能训练",
    "sp_case": "SP模拟问诊",
}

EVENT_TYPE_LABELS = {
    "knowledge_quiz_submitted": "知识测验完成",
    "skill_session_submitted": "临床技能训练完成",
    "case_session_scored": "病例推理训练完成",
    "guideline_pico_submitted": "指南 PICO 训练完成",
    "sp_osce_submitted": "SP 问诊训练完成",
    "teacher_score_confirmed": "教师评分确认",
}

PATHWAY_STAGE_LABELS = {
    stage["key"]: f"阶段{index}：{stage['title']}"
    for index, stage in enumerate(PATHWAY_STAGES, start=1)
}

# Stage keys that older rows still carry after a rename or a bad write.
LEGACY_STAGE_KEYS = {
    "stage_1_basic_knowledge": "stage_1_basic_recognition",
}


def module_label(key: str) -> str:
    return MODULE_LABELS.get(key, key)


def stage_label(key: str) -> str:
    return PATHWAY_STAGE_LABELS.get(LEGACY_STAGE_KEYS.get(key, key), key)


def event_label(key: str) -> str:
    return EVENT_TYPE_LABELS.get(key, key)


def competency_label(key: str) -> str:
    return ABILITY_LABELS.get(key, key)


def competency_changes(updates: dict) -> list[dict]:
    """Turn a stored ``{key: {before, after, delta}}`` blob into display rows."""

    rows = []
    for key, value in updates.items():
        before = value.get("before")
        after = value.get("after")
        delta = value.get("delta")
        if delta is None and before is not None and after is not None:
            delta = round(after - before, 1)
        rows.append(
            {
                "key": key,
                "label": competency_label(key),
                "before": before,
                "after": after,
                "delta": delta,
            }
        )
    return rows
