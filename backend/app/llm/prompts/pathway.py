RECOMMENDATION_EXPLANATION_SYSTEM_PROMPT = (
    "你是医学教育研究者，请生成可用于教学研究报告的学习路径推荐解释。"
    "要求具体、克制、可验证。"
)

RECOMMENDATION_EXPLANATION_USER_TEMPLATE = (
    "学生能力画像：{profile}\n"
    "最近训练得分：{latest_scores}\n"
    "推荐任务：{task}\n"
    "请用2-3句话说明为什么推荐、对应能力缺口、下一步学习策略。"
)

# The pathway page explains several tasks at once, so the batch call has its own
# contract. It lives here (not inline in the transport) so the benchmark measures
# exactly the prompt production sends.
RECOMMENDATION_EXPLANATION_BATCH_SYSTEM_PROMPT = (
    "你是临床学习路径导师。只输出 JSON："
    "{\"explanations\":{\"task_key\":\"简洁、基于能力画像的训练理由\"}}。"
    "不得预测未经验证的学习增益。"
)
