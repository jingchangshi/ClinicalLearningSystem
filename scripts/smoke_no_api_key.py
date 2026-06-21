#!/usr/bin/env python3
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("LLM_API_KEY", None)

from app.services.case_generator import generate_case_payload, validate_case_payload
from app.services.guideline_scoring import score_guideline_pico
from app.services.llm_service import llm_service
from app.services.sp_patient import generate_patient_reply, score_sp_session


def main() -> None:
    assert llm_service.chat_completion("system", "user", fallback="fallback-text") == "fallback-text"
    assert llm_service.chat_json("system", "user", fallback={"ok": True}) == {"ok": True}

    case_payload = generate_case_payload(
        {
            "disease_category": "系统性红斑狼疮",
            "difficulty": "基础",
            "teaching_goal": "训练基础疾病识别",
            "required_elements": ["发热", "皮疹", "关节痛"],
            "target_abilities": ["医学知识", "关键信息提取"],
        }
    )
    validate_case_payload(case_payload)

    sp_case = {
        "title": "发热皮疹青年女性问诊",
        "disease_category": "系统性红斑狼疮",
        "opening_statement": "医生，我最近总是低烧，脸上起红斑。",
        "hidden_history": {
            "duration": "大概一个月。",
            "fever": "最高38度左右。",
            "pain": "双手小关节疼。",
            "associated": "还有口腔溃疡。",
        },
        "expected_tasks": ["问清发热和皮疹特点", "表达共情", "总结诊断计划"],
    }
    transcript = [{"role": "patient", "message": sp_case["opening_statement"]}]
    reply = generate_patient_reply(sp_case, transcript, "我理解您担心。请问发热多久了？")
    assert reply
    sp_score = score_sp_session(
        sp_case,
        transcript + [{"role": "student", "message": "请问发热多久了？有关节痛吗？"}],
        "初步考虑系统性红斑狼疮，需鉴别感染，完善检查并解释风险。",
    )
    assert 0 <= sp_score["total_score"] <= 100

    guideline_score = score_guideline_pico(
        {"disease_category": "系统性红斑狼疮"},
        {
            "clinical_question": "活动性SLE是否应使用羟氯喹？",
            "pico": "P：活动性SLE患者\nI：羟氯喹\nC：不用羟氯喹\nO：复发率和不良反应",
            "answer": "指南强推荐无禁忌时使用羟氯喹，并结合感染风险和监测个体化处理。",
        },
        [{"text": "无禁忌时推荐羟氯喹作为基础治疗。", "grade": "强推荐"}],
        [{"p": "活动性SLE患者", "i": "羟氯喹", "c": "不用羟氯喹", "o": "复发率"}],
    )
    assert 0 <= guideline_score["score"] <= 100
    assert guideline_score["scoring_rationale"]
    print("no-api-key smoke ok")


if __name__ == "__main__":
    main()
