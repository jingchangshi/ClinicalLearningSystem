"""The AI path and the rule fallback must both be real, distinguishable and recorded."""

import importlib

import pytest

from app.core.reasoning_steps import REQUIRED_STEP_KEYS
from app.models import Score
from app.services.scoring_llm import evaluate_case_submission

from tests.factories import ANSWER_TEXTS, make_case, make_student

CASE = {"title": "SLE基础病例", "standard_diagnosis": "系统性红斑狼疮"}
ANSWERS = [{"step": step, "answer_text": text} for step, text in ANSWER_TEXTS.items()]


class _FakeLLM:
    def __init__(self, payload):
        self.payload = payload

    def chat_json(self, system_prompt, user_prompt, fallback, task_type=None):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class _FakeReasoningLLM:
    """Stands in for llm_service while a route-level AI evaluation is requested."""

    def __init__(self, evaluation):
        self.evaluation = evaluation

    def chat_json(self, system_prompt, user_prompt, fallback, task_type=None):
        return self.evaluation


def _ai_payload():
    return {
        "dimensions": {
            key: {
                "score": 72,
                "confidence": 0.7,
                "evidence": ["学生提到了发热"],
                "missing_points": ["缺少补体"],
                "feedback": "继续补充证据",
            }
            for key in (
                "medical_knowledge",
                "key_information",
                "differential_diagnosis",
                "evidence_integration",
                "clinical_decision",
                "evidence_based_medicine",
            )
        },
        "strengths": ["推理链条清晰"],
        "priority_gaps": ["证据权重不足"],
        "overall_feedback": "整体尚可，需强化证据整合。",
        "safety_flags": ["未提及感染筛查"],
    }


def test_valid_structured_response_is_recorded_as_ai():
    result = evaluate_case_submission(CASE, ANSWERS, {}, _FakeLLM(_ai_payload()))

    assert result["evaluation_mode"] == "ai"
    assert result["degraded"] is False
    assert result["ai_score"] is not None
    assert result["evaluation_detail"]["mode"] == "ai"
    assert result["evaluation_detail"]["dimensions"]["medical_knowledge"]["source"] == "ai"
    assert result["evaluation_detail"]["dimensions"]["medical_knowledge"]["evidence"]
    assert result["safety_flags"] == ["未提及感染筛查"]


@pytest.mark.parametrize(
    "payload",
    [
        {"_fallback": True},  # no API key configured
        RuntimeError("provider unreachable"),  # provider failure
        {"medical_knowledge": 90},  # malformed / wrong shape
        {"dimensions": {"medical_knowledge": {"score": 1}}},  # incomplete dimensions
    ],
)
def test_unavailable_or_malformed_ai_falls_back_and_says_so(payload):
    result = evaluate_case_submission(CASE, ANSWERS, {}, _FakeLLM(payload))

    assert result["evaluation_mode"] == "rule_fallback"
    assert result["degraded"] is True
    assert result["ai_score"] is None
    assert result["rule_score"] is not None
    detail = result["evaluation_detail"]
    assert detail["mode"] == "rule_fallback"
    # The rule path still explains itself: "why this score?" always has an answer.
    assert set(detail["dimensions"]) == {
        "medical_knowledge",
        "key_information",
        "differential_diagnosis",
        "evidence_integration",
        "clinical_decision",
        "evidence_based_medicine",
    }
    for dimension in detail["dimensions"].values():
        assert dimension["source"] == "rule"
        assert dimension["evidence"]
        assert 0 <= dimension["confidence"] <= 1
    assert isinstance(result["safety_flags"], list)


def test_submit_stores_provenance_for_the_ai_path(db_factory, client, monkeypatch):
    from app.core import llm_config
    from app.routes import sessions as sessions_routes

    db = db_factory()
    make_case(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200
    session_id = client.post("/api/sessions/start", json={"case_id": 1}).json()["id"]
    for step, text in ANSWER_TEXTS.items():
        client.post(f"/api/sessions/{session_id}/answers", json={"step": step, "answer_text": text})

    def fake_score(case, answers, rubric):
        return evaluate_case_submission(case, answers, rubric, _FakeReasoningLLM(_ai_payload()))

    # Provenance must come from the live configuration, not from a constant.
    monkeypatch.setattr(llm_config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(llm_config, "LLM_MODEL", "deepseek-flash")
    monkeypatch.setattr(llm_config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(sessions_routes, "score_student_answer", fake_score)
    monkeypatch.setattr(
        sessions_routes,
        "generate_learning_recommendation",
        lambda profile, scores, cases: {
            "case": cases[0],
            "reason": "继续训练",
            "pathway_stage": "stage_1_basic_recognition",
        },
    )

    response = client.post(f"/api/sessions/{session_id}/submit")
    assert response.status_code == 200
    assert response.json()["summary"]["evaluation_mode"] == "ai"
    assert response.json()["summary"]["degraded"] is False

    db = db_factory()
    score = db.query(Score).filter(Score.session_id == session_id).one()
    assert score.evaluation_mode == "ai"
    assert score.provider
    assert score.model
    assert score.degraded is False
    assert score.ai_score is not None
    assert score.rule_score is not None
    assert score.prompt_version and score.rubric_version and score.evaluator_version
    db.close()


def test_submit_stores_degraded_flag_for_the_fallback_path(db_factory, client):
    db = db_factory()
    make_case(db)
    make_student(db, username="learner")
    db.commit()
    db.close()

    assert client.post("/api/auth/login", json={"username": "learner", "password": "secret1"}).status_code == 200
    session_id = client.post("/api/sessions/start", json={"case_id": 1}).json()["id"]
    for step in REQUIRED_STEP_KEYS:
        client.post(
            f"/api/sessions/{session_id}/answers",
            json={"step": step, "answer_text": ANSWER_TEXTS[step]},
        )
    response = client.post(f"/api/sessions/{session_id}/submit")
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["evaluation_mode"] == "rule_fallback"
    assert summary["degraded"] is True

    db = db_factory()
    score = db.query(Score).filter(Score.session_id == session_id).one()
    assert score.evaluation_mode == "rule_fallback"
    assert score.provider is None
    assert score.model is None
    assert score.degraded is True
    assert score.ai_score is None
    db.close()


def test_canonical_llm_config_wins_over_deprecated_aliases(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "canonical-key")
    monkeypatch.setenv("LLM_MODEL", "canonical-model")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "legacy-model")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://legacy.example.com")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)

    config = importlib.reload(importlib.import_module("app.core.llm_config"))
    try:
        assert config.LLM_API_KEY == "canonical-key"
        assert config.LLM_MODEL == "canonical-model"
        assert config.LLM_PROVIDER == "openai"
        summary = config.llm_config_summary()
        assert summary["provider"] == "openai"
        assert summary["api_key_source"] == "LLM_API_KEY"
        assert "api_key" not in summary
        assert "canonical-key" not in str(summary)
    finally:
        for name in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL"):
            monkeypatch.delenv(name, raising=False)
        importlib.reload(config)
