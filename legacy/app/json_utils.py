import json
import re
from typing import Callable, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm import invoke_llm


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_json_response(content: str) -> dict:
    return json.loads(_strip_json_fences(content))


def parse_json_with_llm_retry(
    content: str,
    fix_instruction: str,
    max_retries: int = 2,
) -> dict:
    """Parse JSON; on failure, ask LLM to fix and retry instead of returning empty data."""
    last_error: Optional[Exception] = None
    current = content

    for attempt in range(max_retries + 1):
        try:
            return parse_json_response(current)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            current = invoke_llm(
                [
                    SystemMessage(
                        content=(
                            "Corrija o JSON abaixo e retorne APENAS JSON válido, "
                            "sem markdown, sem texto extra."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"Erro: {exc}\n\nJSON inválido:\n{current}\n\n"
                            f"Instruções:\n{fix_instruction}"
                        )
                    ),
                ]
            )

    if last_error:
        raise last_error
    raise ValueError("Failed to parse JSON")


def invoke_json_llm(
    system_prompt: str,
    human_prompt: str,
    fix_instruction: str,
) -> dict:
    content = invoke_llm(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ]
    )
    return parse_json_with_llm_retry(content, fix_instruction)
