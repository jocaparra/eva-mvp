from __future__ import annotations

import re
from datetime import date
from typing import Tuple

DOCUMENT_TYPES = ("CIM", "VALUATION", "DUE_DILIGENCE")

REQUIRED_SECTIONS = {
    "CIM": [
        "Resumo Executivo",
        "Visão Geral da Empresa",
        "Modelo de Negócio",
        "Mercado e Concorrentes",
        "KPIs Financeiros",
        "Oportunidade",
    ],
    "VALUATION": [
        "Sumário Executivo do Valuation",
        "Perfil da Empresa",
        "Histórico Financeiro",
        "Múltiplos de Mercado",
        "Metodologia de Valuation",
        "Range de Valuation",
        "Conclusão e Premissas",
    ],
    "DUE_DILIGENCE": [
        "Sumário Executivo",
        "Visão Geral da Empresa",
        "Análise Financeira",
        "Estrutura Societária e Governança",
        "Análise de Mercado e Concorrência",
        "Riscos Identificados",
        "Red Flags",
        "Conclusão e Score de Risco Final",
    ],
}

EXPECTED_SLIDE_COUNT = {
    "CIM": 7,
    "VALUATION": 8,
    "DUE_DILIGENCE": 9,
}

CONFIRMATION_MESSAGES = {
    "CIM": "Gerando CIM de {company}, aguarde...",
    "VALUATION": "Gerando Valuation de {company}, aguarde...",
    "DUE_DILIGENCE": "Iniciando Due Diligence de {company}, aguarde...",
}


def detect_document_type(message: str) -> str:
    msg = message.lower()
    if any(
        token in msg
        for token in ("due diligence", "diligência", "diligencia", " due diligence")
    ) or re.search(r"\bdd\b", msg):
        return "DUE_DILIGENCE"
    if any(token in msg for token in ("valuation", "vale quanto", "quanto vale")):
        return "VALUATION"
    if re.search(r"\bvalor\b", msg) and any(
        token in msg for token in ("valuation", "avalia", "avaliar", "precificar")
    ):
        return "VALUATION"
    return "CIM"


def extract_company_name(message: str) -> str:
    text = message.strip()
    text = re.sub(
        r"(?i)^(?:gerar|fazer|criar|analisar|iniciar|montar|preparar)\s+",
        "",
        text,
    )
    text = re.sub(r"(?i)^(?:um|uma|o|a)\s+", "", text)
    text = re.sub(r"(?i)\b(?:cim|valuation|valuacao|valuação)\b", " ", text)
    text = re.sub(
        r"(?i)\b(?:due diligence|diligência|diligencia|dd)\b",
        " ",
        text,
    )
    text = re.sub(r"(?i)\b(?:da|de|do|das|dos|of|the|para|em|na|no)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,-")
    return text or message.strip()


def parse_job_message(message: str) -> Tuple[str, str]:
    document_type = detect_document_type(message)
    company_name = extract_company_name(message)
    return document_type, company_name


def confirmation_message(document_type: str, company_name: str) -> str:
    template = CONFIRMATION_MESSAGES.get(document_type, CONFIRMATION_MESSAGES["CIM"])
    return template.format(company=company_name)


def build_output_filename(company_name: str, document_type: str) -> str:
    safe = re.sub(r"[^\w\s-]", "", company_name).strip().replace(" ", "_")
    safe = safe or "empresa"
    today = date.today().isoformat()
    return f"{safe}_{document_type}_{today}.pptx"
