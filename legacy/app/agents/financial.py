import json
import os

import yfinance as yf
from langchain_core.messages import HumanMessage, SystemMessage

from app.citations.matching import audit_financial_structured, audits_to_serializable
from app.ingestion.retrieval import (
    chunks_to_citations,
    format_dataroom_context,
    retrieve_for_deal,
)
from app.json_utils import invoke_json_llm, parse_json_with_llm_retry
from app.llm import invoke_llm_with_pause, truncate_text
from app.state import Citation, JobState

FINANCIAL_FIX = (
    "Retorne JSON válido com todos os campos financeiros preenchidos. "
    "Nunca use N/D. Estime valores com 'est.' quando necessário."
)

FINANCIAL_DATAROOM_QUERIES = [
    "{company} receita faturamento 2022 2023 2024",
    "{company} EBITDA margem lucro demonstrativo financeiro",
    "{company} valuation múltiplo EV EBITDA P/L",
]


def _target_is_public(company_name: str) -> bool:
    """Detecta se o alvo parece ser empresa pública listada."""
    if os.environ.get("YAHOO_FINANCE_TICKER"):
        return True
    try:
        search = yf.Search(company_name, max_results=1)
        quotes = search.quotes or []
        if not quotes:
            return False
        symbol = quotes[0].get("symbol")
        quote_type = str(quotes[0].get("quoteType", "")).upper()
        return bool(symbol) and quote_type in {"EQUITY", "ETF"}
    except Exception:
        return False


def _fetch_yahoo_finance(company_name: str) -> dict:
    ticker = os.environ.get("YAHOO_FINANCE_TICKER")
    if not ticker:
        search = yf.Search(company_name, max_results=1)
        quotes = search.quotes
        if not quotes:
            return {}
        ticker = quotes[0].get("symbol")

    if not ticker:
        return {}

    info = yf.Ticker(ticker).info
    return {
        "ticker": ticker,
        "company_name": info.get("longName") or info.get("shortName"),
        "revenue": info.get("totalRevenue"),
        "revenue_growth": info.get("revenueGrowth"),
        "ebitda": info.get("ebitda"),
        "ebitda_margin": info.get("ebitdaMargins"),
        "net_income": info.get("netIncomeToCommon"),
        "employees": info.get("fullTimeEmployees"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "_source": "external",
    }


def _yahoo_citation(yahoo_data: dict) -> Citation:
    ticker = yahoo_data.get("ticker", "yahoo")
    return {
        "source_file": f"yahoo_finance:{ticker}",
        "page": 1,
        "chunk_id": f"external-yahoo-{ticker}",
        "quote": truncate_text(json.dumps(yahoo_data, default=str), 400),
        "source": "external",
    }


def _financial_prompt(
    company_name: str,
    research_context: str,
    dataroom_context: str,
    yahoo_data: dict,
    legacy_client_context: str = "",
) -> str:
    dataroom_block = ""
    if dataroom_context.strip():
        dataroom_block = (
            "\n\nFONTE PRIMÁRIA — documentos financeiros do data room "
            "(priorize números destes trechos):\n"
            f"{truncate_text(dataroom_context, 6000)}\n"
        )

    yahoo_block = ""
    if yahoo_data:
        yahoo_block = (
            "\n\nFONTE EXTERNA — Yahoo Finance (complemento para comparáveis/públicos):\n"
            f"{json.dumps(yahoo_data, default=str)}\n"
        )

    legacy_block = ""
    if legacy_client_context.strip() and not dataroom_context.strip():
        legacy_block = (
            "\n\nContexto legado do cliente:\n"
            f"{truncate_text(legacy_client_context, 4000)}\n"
        )

    return (
        f"Você é um analista financeiro sênior. Com base nos dados sobre "
        f"{company_name}, extraia e CALCULE os dados financeiros.\n\n"
        "Priorize números dos documentos do data room. Use Yahoo Finance apenas "
        "como complemento para comparáveis ou empresas públicas.\n\n"
        "Retorne APENAS este JSON:\n"
        "{\n"
        "  'revenue_2022': str,\n"
        "  'revenue_2023': str,\n"
        "  'revenue_2024': str,\n"
        "  'ebitda': str,\n"
        "  'net_margin': str,\n"
        "  'growth_yoy': str,\n"
        "  'valuation': str,\n"
        "  'ev_ebitda': str,\n"
        "  'pe_ratio': str,\n"
        "  'ev_revenue': str,\n"
        "  'comparable_companies': [\n"
        "    {'name': str, 'ev_ebitda': str, 'pe': str},\n"
        "    {'name': str, 'ev_ebitda': str, 'pe': str},\n"
        "    {'name': str, 'ev_ebitda': str, 'pe': str}\n"
        "  ],\n"
        "  'valuation_low': str,\n"
        "  'valuation_mid': str,\n"
        "  'valuation_high': str,\n"
        "  'valuation_method_1': str,\n"
        "  'valuation_method_2': str,\n"
        "  'valuation_method_3': str,\n"
        "  'red_flags': [str],\n"
        "  'risk_score': str,\n"
        "  'risk_justification': str,\n"
        "  'risks': [{'risco': str, 'nivel': str, 'mitigacao': str}]\n"
        "}\n\n"
        "NUNCA retorne N/D. Estime com 'est.' se necessário.\n"
        "Retorne APENAS o JSON.\n\n"
        f"Pesquisa estruturada:\n{research_context}\n"
        f"{dataroom_block}{yahoo_block}{legacy_block}"
    )


def _fallback_financial_structured(company_name: str, yahoo: dict, research: dict) -> dict:
    sector = research.get("sector", "setor est.")
    competitors = research.get("main_competitors") or [
        "Concorrente A est.",
        "Concorrente B est.",
        "Concorrente C est.",
    ]
    comp_rows = [
        {"name": str(c), "ev_ebitda": "10x est.", "pe": "20x est."}
        for c in competitors[:3]
    ]
    rev = yahoo.get("revenue")
    rev_str = f"R$ {rev/1e9:.1f}B est." if rev else "R$ 1.0B est."
    return {
        "revenue_2022": rev_str,
        "revenue_2023": rev_str,
        "revenue_2024": rev_str,
        "ebitda": "30% margem est.",
        "net_margin": "15% est.",
        "growth_yoy": "+8% ao ano est.",
        "valuation": rev_str,
        "ev_ebitda": "10x est.",
        "pe_ratio": "22x est.",
        "ev_revenue": "4x est.",
        "comparable_companies": comp_rows,
        "valuation_low": "R$ 800M est.",
        "valuation_mid": "R$ 1.2B est.",
        "valuation_high": "R$ 1.6B est.",
        "valuation_method_1": f"Múltiplo de receita 3x a 5x para {sector}",
        "valuation_method_2": "Múltiplo de EBITDA 8x a 12x est.",
        "valuation_method_3": "Média de comparáveis do setor est.",
        "red_flags": ["Monitorar volatilidade macroeconômica est."],
        "risk_score": "Médio",
        "risk_justification": f"Risco moderado típico do setor de {company_name} est.",
        "risks": [
            {
                "risco": "Concorrência intensa est.",
                "nivel": "Médio",
                "mitigacao": "Diferenciação de produto est.",
            }
        ],
    }


def _attach_field_citations(financial: dict, citations: list[Citation]) -> dict:
    """Associa citações com status explícito; None quando sem fonte data_room."""
    audits = audit_financial_structured(financial, citations)
    financial["_field_audits"] = audits_to_serializable(audits)
    financial["_field_citations"] = {
        field: audit.citation for field, audit in audits.items()
    }
    return financial


def _to_kpis(financial: dict, citations: list[Citation]) -> dict:
    kpis = {
        "revenue": financial.get("revenue_2024"),
        "ebitda": financial.get("ebitda"),
        "ebitda_margin": financial.get("net_margin"),
        "revenue_growth": financial.get("growth_yoy"),
        "valuation": financial.get("valuation"),
        "valuation_low": financial.get("valuation_low"),
        "valuation_mid": financial.get("valuation_mid"),
        "valuation_high": financial.get("valuation_high"),
        "comparables": [
            {
                "empresa": c.get("name"),
                "ev_ebitda": c.get("ev_ebitda"),
                "pe": c.get("pe"),
            }
            for c in financial.get("comparable_companies", [])
        ],
        "assumptions": [
            financial.get("valuation_method_1", ""),
            financial.get("valuation_method_2", ""),
            financial.get("valuation_method_3", ""),
        ],
        "red_flags": financial.get("red_flags", []),
        "risk_score": financial.get("risk_score"),
        "risk_justification": financial.get("risk_justification"),
        "risks": financial.get("risks", []),
    }
    field_citations = financial.get("_field_citations") or {}
    if field_citations:
        kpis["field_citations"] = field_citations
    if citations:
        kpis["sources"] = citations
    return kpis


def _revenue_history(financial: dict) -> list:
    return [
        {"ano": 2022, "valor": financial.get("revenue_2022", "est.")},
        {"ano": 2023, "valor": financial.get("revenue_2023", "est.")},
        {"ano": 2024, "valor": financial.get("revenue_2024", "est.")},
    ]


def financial_node(state: JobState) -> dict:
    company_name = state["company_name"]
    deal_id = state.get("deal_id") or ""
    research = state.get("research_structured") or {}
    legacy_client_context = state.get("client_context") or ""
    research_context = truncate_text(json.dumps(research, ensure_ascii=False), 3000)

    # 1) Fonte primária: data room
    dataroom_queries = [q.format(company=company_name) for q in FINANCIAL_DATAROOM_QUERIES]
    dataroom_chunks = retrieve_for_deal(deal_id, dataroom_queries, k=5) if deal_id else []
    dataroom_citations = chunks_to_citations(dataroom_chunks, source="data_room")
    dataroom_context = format_dataroom_context(dataroom_chunks)

    # 2) Yahoo Finance opcional — só para públicos/comparáveis
    yahoo_data: dict = {}
    financial_citations: list[Citation] = list(dataroom_citations)
    if _target_is_public(company_name):
        yahoo_data = _fetch_yahoo_finance(company_name)
        if yahoo_data:
            financial_citations.append(_yahoo_citation(yahoo_data))

    prompt = _financial_prompt(
        company_name,
        research_context,
        dataroom_context,
        yahoo_data,
        legacy_client_context,
    )

    try:
        content = invoke_llm_with_pause(
            [
                SystemMessage(content="Analista financeiro sênior. Retorne apenas JSON."),
                HumanMessage(content=prompt),
            ],
            pause_seconds=3.0,
        )
        financial_structured = parse_json_with_llm_retry(content, FINANCIAL_FIX)
    except Exception:
        try:
            financial_structured = invoke_json_llm(
                "Retorne JSON financeiro completo.",
                prompt,
                FINANCIAL_FIX,
            )
        except Exception:
            financial_structured = _fallback_financial_structured(
                company_name, yahoo_data, research
            )

    financial_structured = _attach_field_citations(financial_structured, dataroom_citations)
    kpis = _to_kpis(financial_structured, financial_citations)
    if yahoo_data:
        kpis["yahoo_finance"] = yahoo_data

    return {
        "financial_structured": financial_structured,
        "kpis": kpis,
        "revenue_history": _revenue_history(financial_structured),
        "revenue_breakdown": [],
        "financial_citations": financial_citations,
        "retrieved_context": (state.get("retrieved_context") or []) + dataroom_citations,
    }
