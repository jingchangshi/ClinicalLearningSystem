from datetime import datetime

from app.models import CompetencyProfile
from app.services.llm_service import llm_service


def score_guideline_pico(
    guideline: dict,
    payload: dict,
    recommendations: list[dict],
    pico_examples: list[dict],
) -> dict:
    scoring = _score_pico(payload, recommendations)
    return {
        "score": scoring["score"],
        "detail": scoring["detail"],
        "feedback": _feedback_with_llm(guideline, payload, scoring),
        "recommended_answer": _recommended_answer(guideline, recommendations, pico_examples),
        "scoring_rationale": _scoring_rationale(guideline, payload, scoring),
    }


def update_evidence_profile(profile: CompetencyProfile, score: float) -> None:
    profile.evidence_based_medicine = round(profile.evidence_based_medicine * 0.7 + score * 0.3, 1)
    profile.updated_at = datetime.utcnow()


def _score_pico(payload: dict, recommendations: list[dict]) -> dict:
    pico_text = _normalize(payload["pico"])
    answer_text = _normalize(payload["answer"])
    question_text = _normalize(payload["clinical_question"])
    combined = f"{question_text} {pico_text} {answer_text}"
    recommendation_text = " ".join(_normalize(item.get("text", "")) for item in recommendations)
    grade_text = " ".join(_normalize(item.get("grade", "")) for item in recommendations)

    detail = {
        "pico_completeness": _pico_completeness(pico_text),
        "guideline_match": _keyword_score(answer_text, recommendation_text),
        "grade_understanding": _grade_score(answer_text, grade_text),
        "clinical_applicability": _clinical_score(combined),
        "risk_individualization": _risk_score(combined),
    }
    score = round(sum(detail.values()) / len(detail), 1)
    return {"score": score, "detail": detail}


def _pico_completeness(pico_text: str) -> float:
    markers = ["p", "i", "c", "o", "患者", "干预", "对照", "结局"]
    hits = sum(1 for marker in markers if marker in pico_text)
    return round(min(100.0, hits / 4 * 100), 1)


def _keyword_score(answer_text: str, source_text: str) -> float:
    candidates = [
        "羟氯喹",
        "糖皮质激素",
        "免疫抑制剂",
        "利妥昔单抗",
        "环磷酰胺",
        "诱导缓解",
        "感染",
        "肾脏",
        "肺部",
        "器官受累",
    ]
    keywords = [keyword for keyword in candidates if keyword in source_text]
    if not keywords:
        return 0.0
    hits = sum(1 for token in keywords if token in answer_text)
    return round(min(100.0, hits / min(4, len(keywords)) * 100), 1)


def _grade_score(answer_text: str, grade_text: str) -> float:
    grade_keywords = ["强推荐", "有条件推荐", "专家共识", "推荐等级", "证据", "共识"]
    hits = sum(1 for keyword in grade_keywords if keyword in grade_text and keyword in answer_text)
    if any(grade in answer_text for grade in ["强推荐", "有条件推荐", "专家共识"]):
        hits += 1
    return round(min(100.0, hits / 2 * 100), 1)


def _clinical_score(text: str) -> float:
    keywords = ["疾病活动", "器官受累", "肾", "肺", "感染", "妊娠", "禁忌", "监测", "随访", "患者"]
    hits = sum(1 for keyword in keywords if keyword in text)
    return round(min(100.0, hits / 3 * 100), 1)


def _risk_score(text: str) -> float:
    keywords = ["风险", "感染", "不良反应", "个体化", "禁忌", "肝", "肾", "妊娠", "监测", "随访"]
    hits = sum(1 for keyword in keywords if keyword in text)
    return round(min(100.0, hits / 3 * 100), 1)


def _recommended_answer(guideline: dict, recommendations: list[dict], pico_examples: list[dict]) -> str:
    recommendation_lines = [
        f"{item.get('text', '')}（{item.get('grade', '未标注等级')}）"
        for item in recommendations
    ]
    example = pico_examples[0] if pico_examples else {}
    pico = (
        f"P：{example.get('p', guideline.get('disease_category', '目标患者'))}；"
        f"I：{example.get('i', '指南推荐干预')}；"
        f"C：{example.get('c', '替代方案或常规治疗')}；"
        f"O：{example.get('o', '疗效和安全性结局')}"
    )
    return f"建议先形成结构化 PICO：{pico}。回答时应引用：{' '.join(recommendation_lines)}，并说明患者器官受累、感染风险、禁忌证和随访监测。"


def _feedback(scoring: dict) -> str:
    detail = scoring["detail"]
    messages = []
    if scoring["score"] >= 85:
        messages.append("循证回答结构完整，能较好结合指南推荐与临床适用性。")
    elif scoring["score"] >= 70:
        messages.append("已覆盖主要指南信息，但推荐等级或个体化风险说明仍需加强。")
    else:
        messages.append("PICO 结构和指南推荐匹配不足，建议重新按患者、干预、对照、结局组织答案。")
    if detail["pico_completeness"] < 80:
        messages.append("PICO 需明确 P/I/C/O 四要素。")
    if detail["grade_understanding"] < 80:
        messages.append("请写明强推荐、有条件推荐或专家共识等推荐等级。")
    if detail["risk_individualization"] < 80:
        messages.append("需补充感染、不良反应、禁忌证和随访监测。")
    return "".join(messages)


def _feedback_with_llm(guideline: dict, payload: dict, scoring: dict) -> str:
    fallback = _feedback(scoring)
    return llm_service.chat_completion(
        "你是循证医学课程导师，请基于PICO作答评分生成结构化形成性反馈。",
        (
            f"指南：{guideline.get('title')}\n"
            f"学生临床问题：{payload.get('clinical_question')}\n"
            f"学生PICO：{payload.get('pico')}\n"
            f"学生回答：{payload.get('answer')}\n"
            f"评分细项：{scoring['detail']}\n"
            "请输出不超过120字，包含优点、主要缺口和下一步修改建议。"
        ),
        fallback,
    )


def _scoring_rationale(guideline: dict, payload: dict, scoring: dict) -> str:
    fallback = (
        f"系统依据PICO完整性、指南推荐匹配、推荐等级理解、临床适用性和风险个体化五项计算，"
        f"综合得分为{scoring['score']}。"
    )
    return llm_service.generate_guideline_rationale(guideline, payload, scoring, fallback)


def _normalize(value: str) -> str:
    return value.strip().lower()
