import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm import invoke_llm


def extract_company_name(message: str) -> str:
    """Extract clean company name from user message using LLM."""
    try:
        response = invoke_llm(
            [
                SystemMessage(
                    content=(
                        "Extraia APENAS o nome da empresa desta mensagem. "
                        "Retorne somente o nome, sem mais nada. Exemplos:\n"
                        "'Faça um valuation da Apple' → Apple\n"
                        "'Gerar CIM da Magazine Luiza' → Magazine Luiza\n"
                        "'Due diligence Nubank' → Nubank"
                    )
                ),
                HumanMessage(content=f"Mensagem: {message}"),
            ]
        )
        name = response.strip().strip('"').strip("'")
        name = re.sub(r"^(?i)(a empresa|empresa)\s+", "", name).strip()
        return name or message.strip()
    except Exception:
        return message.strip()
