TEACHER_INSIGHT_SYSTEM_PROMPT = "你是医学教育质量改进顾问，请基于班级数据生成教师端教学洞察。"

TEACHER_INSIGHT_USER_TEMPLATE = (
    "班级短板：{weak_dimensions}\n"
    "训练分布：{training_summary}\n"
    "请输出2句话，包含班级共性问题和下一步教学干预建议。"
)
