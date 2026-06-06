import os
import re
import time
from pathlib import Path
from typing import Optional, Sequence, Union

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langchain_anthropic import ChatAnthropic

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

DEFAULT_MODEL = "claude-sonnet-4-20250514"


def get_anthropic_api_key() -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY não encontrada. Defina no arquivo .env na raiz do projeto."
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
        for token in ("429", "quota", "rate limit", "overloaded", "too many requests")
    )


def _message_content_to_str(content: Union[str, list, None]) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            elif hasattr(block, "text"):
                parts.append(str(block.text))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def get_llm() -> ChatAnthropic:
    model = os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
    return ChatAnthropic(
        model=model,
        temperature=0,
        api_key=get_anthropic_api_key(),
        max_tokens=4096,
        max_retries=0,
    )


def invoke_llm(messages: Sequence[BaseMessage], max_retries: int = 5) -> str:
    """Invoke Claude with automatic backoff on 429 / rate limits."""
    llm = get_llm()
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            return _message_content_to_str(response.content)
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
