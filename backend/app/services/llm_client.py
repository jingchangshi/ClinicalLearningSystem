from typing import Any

from app.services.llm_service import (
    chat_json,
    chat_text,
    generate_learning_recommendation,
    generate_reasoning_question,
    score_student_answer,
)


def normalize_openai_payload(value: Any) -> Any:
    return value
