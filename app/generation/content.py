"""Conteúdo narrativo compartilhado — independente do renderer (PPT/DOCX)."""

from __future__ import annotations

from typing import Any, List, Optional


def _join_items(items: Any) -> str:
    if not items:
        return "Não informado"
    if isinstance(items, list):
        return ", ".join(str(item) for item in items)
    return str(items)


def _company(deal_state: dict) -> str:
    research = deal_state.get("research_structured") or {}
    return research.get("company_name") or deal_state.get("company_name", "Empresa")


def _sections_cim(deal_state: dict) -> dict[str, str]:
    r = deal_state.get("research_structured") or {}
    f = deal_state.get("financial_structured") or {}
    company = _company(deal_state)
    return {
        "Resumo Executivo": (
            f"CIM — {company}: oportunidade de investimento em {r.get('sector', 'setor relevante')} "
            f"com posição {r.get('market_position', 'competitiva')}."
        ),
        "Visão Geral da Empresa": (
            f"{company} | Fundação: {r.get('founded')} | Sede: {r.get('headquarters')} | "
            f"Funcionários: {r.get('employees')}\n{r.get('description', '')}"
        ),
        "Modelo de Negócio": str(r.get("business_model") or "Modelo em análise."),
        "Mercado e Concorrentes": (
            f"Posição: {r.get('market_position')}. Concorrentes: {_join_items(r.get('main_competitors'))}."
        ),
        "KPIs Financeiros": (
            f"Receita 2022: {f.get('revenue_2022')} | 2023: {f.get('revenue_2023')} | "
            f"2024: {f.get('revenue_2024')}\nEBITDA: {f.get('ebitda')} | Margem: {f.get('net_margin')} | "
            f"Crescimento: {f.get('growth_yoy')}"
        ),
        "Oportunidade": (
            f"Empresa líder em {r.get('sector')} com crescimento consistente. "
            f"Valuation indicativo: {f.get('valuation', 'em análise')}."
        ),
    }


def _sections_memo(deal_state: dict) -> dict[str, str]:
    r = deal_state.get("research_structured") or {}
    f = deal_state.get("financial_structured") or {}
    company = _company(deal_state)
    comparables = f.get("comparable_companies") or []
    comp_text = "\n".join(
        f"- {c.get('name')}: EV/EBITDA {c.get('ev_ebitda')}, P/L {c.get('pe')}"
        for c in comparables[:5]
    ) or "Comparáveis do setor em análise."
    red_flags = f.get("red_flags") or []
    if isinstance(red_flags, list):
        flags = ", ".join(str(x) for x in red_flags) or "Nenhum crítico identificado"
    else:
        flags = str(red_flags)
    return {
        "Sumário Executivo": (
            f"Investment memo — {company}: {r.get('description', '')[:500]}"
        ),
        "Contexto e Tese de Investimento": (
            f"Setor: {r.get('sector')}. Modelo: {r.get('business_model')}. "
            f"Notícias recentes: {r.get('recent_news', '—')}"
        ),
        "Perfil da Empresa": (
            f"{company} | {r.get('headquarters')} | Fundadores: {r.get('founders')} | "
            f"Produtos: {_join_items(r.get('key_products'))}"
        ),
        "Análise Financeira": (
            f"Receita 2024: {f.get('revenue_2024')} | EBITDA: {f.get('ebitda')} | "
            f"Crescimento: {f.get('growth_yoy')}\nValuation: {f.get('valuation')} | "
            f"Range: {f.get('valuation_low')} – {f.get('valuation_high')}\n{comp_text}"
        ),
        "Riscos e Mitigantes": (
            f"Score: {f.get('risk_score', 'Médio')}. Red flags: {flags}. "
            f"{f.get('risk_justification', '')}"
        ),
        "Conclusão": (
            f"Conclusão preliminar sobre {company}: tese sujeita a due diligence complementar "
            f"e validação das premissas financeiras citadas."
        ),
    }


def build_document_sections(deal_state: dict, artifact_type: str) -> dict[str, str]:
    """Seções narrativas keyed by título — mesma espinha para PPT e DOCX."""
    if artifact_type == "memo_docx":
        return _sections_memo(deal_state)
    return _sections_cim(deal_state)


def build_plain_content(deal_state: dict, artifact_type: str) -> str:
    """Texto contínuo (ex.: payload Presenton)."""
    sections = build_document_sections(deal_state, artifact_type)
    company = _company(deal_state)
    parts = [f"Documento: {company}\n"]
    for title, body in sections.items():
        parts.append(f"\n{title}\n{body}")
    return "\n".join(parts)
