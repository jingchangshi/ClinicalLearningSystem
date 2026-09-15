from app.services.scoring_llm import evaluate_case_submission


CASE = {"title": "SLE", "standard_diagnosis": "SLE"}
ANSWERS = [{"step": "key_information", "answer_text": "发热 皮疹 ANA 蛋白尿"}]
DIMENSIONS = [
    "medical_knowledge", "key_information", "differential_diagnosis",
    "evidence_integration", "clinical_decision", "evidence_based_medicine",
]


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def chat_json(self, *_args):
        return self.response


class FailingLLM:
    def chat_json(self, *_args):
        raise TimeoutError("provider timed out")


class DisabledLLM:
    def chat_json(self, *_args):
        return {"_fallback": True}


def test_uses_validated_ai_evaluation_when_available():
    response = {
        "dimensions": {key: {"score": 80, "confidence": 0.8, "evidence": ["reason"], "missing_points": [], "feedback": "good"} for key in DIMENSIONS},
        "strengths": ["reasoning is explicit"], "priority_gaps": ["add safety monitoring"],
        "overall_feedback": "Continue to explain evidence.", "safety_flags": [],
    }
    result = evaluate_case_submission(CASE, ANSWERS, {}, FakeLLM(response))
    assert result["evaluation_mode"] == "ai"
    assert result["total_score"] == 80
    assert result["degraded"] is False


def test_invalid_llm_payload_degrades_to_rule_evaluator():
    result = evaluate_case_submission(CASE, ANSWERS, {}, FakeLLM({"dimensions": {}}))
    assert result["evaluation_mode"] == "rule_fallback"
    assert result["degraded"] is True
    assert result["ai_score"] is None


def test_llm_exception_degrades_to_rule_evaluator():
    result = evaluate_case_submission(CASE, ANSWERS, {}, FailingLLM())
    assert result["evaluation_mode"] == "rule_fallback"
    assert result["degraded"] is True
    assert result["ai_score"] is None


def test_disabled_llm_uses_rule_fallback_without_http_failure():
    result = evaluate_case_submission(CASE, ANSWERS, {}, DisabledLLM())
    assert result["evaluation_mode"] == "rule_fallback"
    assert result["degraded"] is True
    assert result["rule_score"] is not None
