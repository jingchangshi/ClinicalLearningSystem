"""No identifier-shaped content may reach the provider (ARCH §10 invariant).

The guard is deliberately conservative: it covers labelled names, demographics,
contact details and record numbers, and it never rewrites clinical findings.
Free-text names without any label or demographic marker are documented debt
(ARCH §12) and are addressed at the input boundary, not by guessing here.
"""

import json

from app.core.deidentify import deidentify, deidentify_text, redact_phi
from app.services.llm_service import prompt_json


def test_redacts_identifiers_and_reports_kinds():
    text = (
        "患者姓名：张三，手机号 13812345678，邮箱 zhang@example.com，"
        "身份证 11010119900307123X，住院号：ZY2024001234。"
    )
    redacted, findings = redact_phi(text)
    assert "13812345678" not in redacted
    assert "zhang@example.com" not in redacted
    assert "11010119900307123X" not in redacted
    assert "ZY2024001234" not in redacted
    assert "张三" not in redacted
    assert set(findings) >= {"mainland_mobile", "email", "national_id", "medical_record_number"}


def test_keeps_clinical_numbers_intact():
    text = "体温 38.6℃，白细胞 3.0×10^9/L，补体C3 0.45 g/L，CRP 62 mg/L，年龄 32 岁。"
    redacted, findings = redact_phi(text)
    assert redacted == text
    assert findings == []


def test_common_clinical_phrases_are_not_mistaken_for_names():
    text = "患者出现发热、皮疹，患者拒绝住院，患者家属要求会诊。"
    redacted, findings = redact_phi(text)
    assert redacted == text
    assert findings == []


def test_inline_name_without_colon_is_redacted():
    redacted, findings = redact_phi("患者王五，男，32岁，因发热入院。")
    assert "王五" not in redacted
    assert "labelled_name_demographic" in findings
    assert "因发热入院" in redacted


def test_header_style_name_is_redacted():
    redacted, findings = redact_phi("姓名李四  性别女  年龄 29 岁")
    assert "李四" not in redacted
    assert "labelled_name_inline" in findings
    assert "年龄 29 岁" in redacted


def test_prompt_json_redacts_nested_payloads():
    payload = {
        "case": {
            "history": "患者姓名：李四，联系电话 13900001111，既往体健。",
            "contacts": ["wang@hospital.cn"],
        },
        "answers": ["我的手机号是 13712345678"],
    }
    rendered = prompt_json(payload)
    for leaked in ("李四", "13900001111", "13712345678", "wang@hospital.cn"):
        assert leaked not in rendered
    parsed = json.loads(rendered)
    assert parsed["case"]["contacts"] == ["[邮箱]"]
    assert "既往体健" in parsed["case"]["history"]


def test_deidentify_returns_original_object_when_clean():
    payload = {"history": "发热、皮疹、ANA阳性。"}
    assert deidentify(payload) is payload


def test_deidentify_text_handles_empty_input():
    assert deidentify_text("") == ""


def test_provider_client_sanitises_every_message(monkeypatch):
    """Even a prompt assembled with str.format() is redacted before sending."""

    from app.services import llm_service as module

    captured: dict = {}

    class _FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)

            class _Message:
                content = "ok"

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            self.chat = type("_Chat", (), {"completions": _FakeCompletions()})()

    monkeypatch.setattr(module, "OpenAI", _FakeOpenAI)
    module.OpenAICompatibleClient().chat(
        [
            {"role": "system", "content": "病例：患者姓名：王五，住院号 A123456"},
            {"role": "user", "content": "手机号 13500001111，评分依据见上。"},
        ]
    )
    sent = json.dumps(captured["messages"], ensure_ascii=False)
    assert "王五" not in sent
    assert "A123456" not in sent
    assert "13500001111" not in sent
    assert "评分依据见上" in sent
