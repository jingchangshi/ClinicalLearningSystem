import os

LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
LLM_BASE_URL = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("LLM_BASE_URL") or "https://api.deepseek.com"
LLM_MODEL = os.getenv("DEEPSEEK_MODEL") or os.getenv("LLM_MODEL") or "deepseek-chat"
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "12"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
