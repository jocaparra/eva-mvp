import os
import re
import time
from pathlib import Path
from typing import Optional, Sequence

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

DEFAULT_MODEL = "gemini-2.0-flash-lite"


def get_google_api_key() -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY não encontrada. Defina no arquivo .env na raiz do projeto."
        )
    return api_key


def truncate_text(text: str, max_chars: int) -> str:
    if not text or len(text) <= max_chars:
        return text or ""
    return text[: max_chars - 3].rstrip() + "..."


def _parse_retry_delay(error: str, attempt: int) -> float:
    for pattern in (
        r"retry in (\d+(?:\.\d+)?)s",
        r"retry_delay.*?seconds:\s*(\d+)",
        r"Please retry in (\d+(?:\.\d+)?)s",
    ):
        match = re.search(pattern, error, re.IGNORECASE | re.DOTALL)
        if match:
            return float(match.group(1)) + 2.0
    return min(30.0, 5.0 * (2**attempt))


def _is_rate_limit_error(error: Exception) -> bool:
    msg = str(error).lower()
    return any(
        token in msg
        for token in ("429", "quota", "rate limit", "resourceexhausted", "too many requests")
    )


def get_llm() -> ChatGoogleGenerativeAI:
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=0,
        google_api_key=get_google_api_key(),
        max_output_tokens=1024,
        max_retries=0,
    )


def invoke_llm(messages: Sequence[BaseMessage], max_retries: int = 5) -> str:
    """Invoke Gemini with automatic backoff on 429 / quota errors."""
    llm = get_llm()
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            return response.content
        except Exception as exc:
            last_error = exc
            if _is_rate_limit_error(exc) and attempt < max_retries - 1:
                delay = _parse_retry_delay(str(exc), attempt)
                time.sleep(delay)
                continue
            raise

    if last_error:
        raise last_error
    raise RuntimeError("LLM invocation failed")


def invoke_llm_with_pause(
    messages: Sequence[BaseMessage],
    pause_seconds: float = 2.0,
    **kwargs,
) -> str:
    if pause_seconds > 0:
        time.sleep(pause_seconds)
    return invoke_llm(messages, **kwargs)
