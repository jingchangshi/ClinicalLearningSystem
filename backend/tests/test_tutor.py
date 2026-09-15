"""The tutor must stay Socratic, bounded, and silent about hidden answers."""

from app.core.reasoning_steps import REQUIRED_STEP_KEYS
from app.models import TutorTurn
from app.services import tutor_service
from app.services.tutor_service import build_reasoning_state, leaks_hidden_answer

from tests.factories import ANSWER_TEXTS, make_case, make_student


def _login(client, username="learner"):
    assert client.post("/api/auth/login", json={"username": username, "password": "secret1"}).status_code == 200


def _start(client):
    return client.post("/api/sessions/start", json={"case_id": 1}).json()["id"]


def _seed(db_factory):
    db = db_factory()
    case = make_case(db)
    make_student(db, username="learner")
    db.commit()
    hidden = (case.standard_diagnosis, case.treatment_plan)
    db.close()
    return hidden


def test_reasoning_state_tracks_covered_and_missing_elements():
    state = build_reasoning_state(
        {},
        "differential_diagnosis",
        "考虑感染与淋巴瘤需要排除，但还没有讨论HLH。",
        [],
    )
    assert "感染" in state["evidence_already_covered"]
    assert "HLH" in state["evidence_already_covered"]
    assert "淋巴瘤" in state["evidence_already_covered"]
    assert "血管炎" in state["missing_reasoning_elements"]
    assert state["turn_count"] == 0
    assert state["completion_state"] == "in_progress"


def test_state_is_not_started_without_an_answer():
    state = build_reasoning_state({}, "treatment", "", [])
    assert state["completion_state"] == "not_started"
    assert state["safety_gap"]


def test_tutor_state_carries_step_specific_signals():
    state = build_reasoning_state({}, "treatment", "使用激素治疗，不需要其他评估。", [])
    assert state["misconceptions"]
    assert state["dimension"] == "clinical_decision"
    assert state["max_turns"] == tutor_service.MAX_TUTOR_TURNS_PER_STEP


def test_hidden_answer_guard_rejects_treatment_plan_text():
    case = {"standard_diagnosis": "系统性红斑狼疮", "treatment_plan": "激素联合羟氯喹并长期随访监测"}
    assert leaks_hidden_answer("标准治疗是激素联合羟氯喹并长期随访监测。", case)
    assert not leaks_hidden_answer("你的鉴别诊断里哪一个最危险？", case)


def test_short_diagnosis_label_leak_is_rejected():
    case = {"standard_diagnosis": "系统性红斑狼疮"}
    for question in (
        "你的诊断应该是系统性红斑狼疮。",
        "诊断：系统性红斑狼疮",
        "正确答案是系统性红斑狼疮",
        "系统性红斑狼疮",
        "标准诊断是系统性红斑狼疮。",
    ):
        assert leaks_hidden_answer(question, case), question


def test_short_diagnosis_label_is_allowed_when_the_student_raised_it():
    case = {"standard_diagnosis": "系统性红斑狼疮"}
    student = "我考虑系统性红斑狼疮，因为发热伴皮疹和ANA阳性。"
    # The student already named it, so re-using it adds no information.
    assert not leaks_hidden_answer("你考虑系统性红斑狼疮的依据是什么？", case, student_text=student)
    # Without that context the same question would be revealing the answer.
    assert leaks_hidden_answer("你考虑系统性红斑狼疮的依据是什么？", case)


def test_legitimate_disease_related_questions_are_allowed():
    case = {"standard_diagnosis": "系统性红斑狼疮", "treatment_plan": "激素联合羟氯喹治疗并随访"}
    for question in (
        "是否需要先排除感染？依据是什么？",
        "哪一种器官受累最会改变你的处理决策？",
        "你会先做哪项检查来验证活动度？",
    ):
        assert not leaks_hidden_answer(question, case), question


def test_tutor_falls_back_to_a_rule_question_on_a_label_leak(db_factory, client, monkeypatch):
    db = db_factory()
    case = make_case(db, diagnosis="系统性红斑狼疮")
    make_student(db, username="learner")
    db.commit()
    db.close()

    _login(client)
    session_id = _start(client)
    client.post(
        f"/api/sessions/{session_id}/answers",
        json={"step": "initial_diagnosis", "answer_text": "发热皮疹，考虑感染可能。"},
    )

    monkeypatch.setattr(
        tutor_service.llm_service,
        "chat_completion",
        lambda system_prompt, user_prompt, fallback: "你的诊断应该是系统性红斑狼疮。",
    )
    payload = client.post(f"/api/sessions/{session_id}/tutor", json={"step": "initial_diagnosis"}).json()
    question = payload["tutor_question"]
    # The leaky model output was rejected and a rule question was used instead.
    assert question
    assert "系统性红斑狼疮" not in question
    assert question != "你的诊断应该是系统性红斑狼疮。"


def test_multi_turn_conversation_persists_and_advances(db_factory, client):
    hidden = _seed(db_factory)
    _login(client)
    session_id = _start(client)
    client.post(
        f"/api/sessions/{session_id}/answers",
        json={"step": "key_information", "answer_text": "发热皮疹。"},
    )

    first = client.post(f"/api/sessions/{session_id}/tutor", json={"step": "key_information"}).json()
    assert first["tutor_question"]
    assert first["state"]["turn_count"] == 1
    assert len(first["turns"]) == 1

    second = client.post(
        f"/api/sessions/{session_id}/tutor",
        json={"step": "key_information", "message": "因为ANA阳性提示自身免疫病。"},
    ).json()
    assert [turn["role"] for turn in second["turns"]] == ["tutor", "student", "tutor"]
    assert second["turns"][1]["message"].startswith("因为")
    assert second["state"]["student_turn_count"] == 1
    assert second["state"]["turn_count"] == 2

    # No hidden diagnosis or treatment plan may appear anywhere in the coaching text.
    for turn in second["turns"]:
        for secret in hidden:
            assert secret not in turn["message"]

    db = db_factory()
    assert db.query(TutorTurn).filter(TutorTurn.session_id == session_id).count() == 3
    db.close()


def test_tutor_stops_and_does_not_leak_ai_answer(db_factory, client, monkeypatch):
    db = db_factory()
    case = make_case(db)
    make_student(db, username="learner")
    db.commit()
    treatment_plan = case.treatment_plan
    db.close()

    _login(client)
    session_id = _start(client)
    client.post(
        f"/api/sessions/{session_id}/answers",
        json={"step": "treatment", "answer_text": ANSWER_TEXTS["treatment"]},
    )

    class _LeakyLLM:
        def chat_completion(self, system_prompt, user_prompt, fallback):
            return f"标准治疗是{treatment_plan}"

    monkeypatch.setattr(tutor_service.llm_service, "chat_completion", _LeakyLLM().chat_completion)
    payload = client.post(f"/api/sessions/{session_id}/tutor", json={"step": "treatment"}).json()
    assert treatment_plan not in payload["tutor_question"]
    assert payload["tutor_question"]


def test_tutor_caps_turns_per_step(db_factory, client, monkeypatch):
    _seed(db_factory)
    monkeypatch.setattr(tutor_service, "MAX_TUTOR_TURNS_PER_STEP", 2)
    _login(client)
    session_id = _start(client)
    client.post(
        f"/api/sessions/{session_id}/answers",
        json={"step": "examination", "answer_text": "需要补体检查。"},
    )

    client.post(f"/api/sessions/{session_id}/tutor", json={"step": "examination"})
    client.post(f"/api/sessions/{session_id}/tutor", json={"step": "examination", "message": "用来评估活动度。"})
    stopped = client.post(f"/api/sessions/{session_id}/tutor", json={"step": "examination"}).json()

    assert stopped["tutor_question"] is None
    assert stopped["stopped_reason"] in {"max_turns_reached", "coverage_sufficient"}


def test_tutor_rejects_unknown_step_and_completed_session(db_factory, client):
    _seed(db_factory)
    _login(client)
    session_id = _start(client)

    assert client.post(f"/api/sessions/{session_id}/tutor", json={"step": "reasoning"}).status_code == 400

    for step in REQUIRED_STEP_KEYS:
        client.post(
            f"/api/sessions/{session_id}/answers",
            json={"step": step, "answer_text": ANSWER_TEXTS[step]},
        )
    assert client.post(f"/api/sessions/{session_id}/submit").status_code == 200
    assert client.post(f"/api/sessions/{session_id}/tutor", json={"step": "treatment"}).status_code == 409


def test_coach_endpoint_still_returns_one_question(db_factory, client):
    _seed(db_factory)
    _login(client)
    session_id = _start(client)
    response = client.post(
        f"/api/sessions/{session_id}/coach",
        json={"step": "key_information", "answer_text": "发热皮疹。"},
    )
    assert response.status_code == 200
    assert response.json()["message"]
    assert response.json()["reasoning_step"] == "key_information"
