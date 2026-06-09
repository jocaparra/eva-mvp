"""Tipos de artefato suportados, seções esperadas e resolução de formato."""

from __future__ import annotations

import re
from typing import Optional

# Etapa 6 — narrativos; model_xlsx fica fora (proveniência por célula).
SUPPORTED_ARTIFACT_TYPES = ("cim_pptx", "memo_docx")

ARTIFACT_MIME = {
    "cim_pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "memo_docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

ARTIFACT_EXTENSION = {
    "cim_pptx": ".pptx",
    "memo_docx": ".docx",
}

REQUIRED_SECTIONS = {
    "cim_pptx": [
        "Resumo Executivo",
        "Visão Geral da Empresa",
        "Modelo de Negócio",
        "Mercado e Concorrentes",
        "KPIs Financeiros",
        "Oportunidade",
        "Referências",
    ],
    "memo_docx": [
        "Sumário Executivo",
        "Contexto e Tese de Investimento",
        "Perfil da Empresa",
        "Análise Financeira",
        "Riscos e Mitigantes",
        "Conclusão",
        "Referências",
    ],
}

# Proxy estrutural por formato
EXPECTED_SLIDE_COUNT = {
    "cim_pptx": 7,
}

EXPECTED_HEADING_COUNT = {
    "memo_docx": 6,
}

# Compatibilidade com document_type legado (LangGraph / jobs)
LEGACY_DOCUMENT_TYPES = ("CIM", "VALUATION", "DUE_DILIGENCE")


def detect_memo_intent(message: str) -> bool:
    msg = message.lower()
    return any(token in msg for token in ("memo", "memorando", "investment memo", "nota de investimento"))


def resolve_artifact_type(
    document_type: str,
    message: str = "",
    explicit: Optional[str] = None,
) -> str:
    """Resolve artifact_type a partir de parâmetro explícito, mensagem ou document_type legado."""
    if explicit and explicit in SUPPORTED_ARTIFACT_TYPES:
        return explicit
    if detect_memo_intent(message):
        return "memo_docx"
    if document_type == "CIM":
        return "cim_pptx"
    # Valuation / DD narrativos → memo DOCX na etapa 6
    if document_type in ("VALUATION", "DUE_DILIGENCE"):
        return "memo_docx"
    return "cim_pptx"


def artifact_type_for_storage(artifact_type: str, document_type: str) -> str:
    """Chave persistida no workspace (compatível com upsert por tipo)."""
    if artifact_type in SUPPORTED_ARTIFACT_TYPES:
        return artifact_type
    return resolve_artifact_type(document_type)
