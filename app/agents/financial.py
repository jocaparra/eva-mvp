import json
import os
import re

import yfinance as yf
from langchain_core.messages import HumanMessage, SystemMessage

from app.json_utils import invoke_json_llm, parse_json_with_llm_retry
from app.llm import invoke_llm_with_pause, truncate_text
from app.state import JobState

FINANCIAL_FIX = (
    "Retorne JSON válido com todos os campos financeiros preenchidos. "
    "Nunca use N/D. Estime valores com 'est.' quando necessário."
)


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
    }


def _financial_prompt(
    company_name: str,
    research_context: str,
    yahoo_data: dict,
    client_context: str = "",
) -> str:
    client_block = ""
    if client_context.strip():
        client_block = (
            f"\n\nDocumento confidencial do cliente (priorize números e fatos deste texto):\n"
            f"{truncate_text(client_context, 4000)}\n"
        )

    return (
        f"Você é um analista financeiro sênior. Com base nos dados de pesquisa sobre "
        f"{company_name}, extraia e CALCULE os dados financeiros.\n\n"
        "Se os dados exatos não estiverem disponíveis, use seu conhecimento sobre "
        "a empresa e o setor para fazer estimativas razoáveis e sinalizadas como 'est.'\n\n"
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
        "NUNCA retorne N/D. Se não souber o valor exato, estime com base no setor "
        "e sinalize com 'est.' no final do valor.\n"
        "Retorne APENAS o JSON.\n\n"
        f"Pesquisa estruturada:\n{research_context}\n\n"
        f"Yahoo Finance:\n{json.dumps(yahoo_data, default=str)}{client_block}"
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


def _to_kpis(financial: dict) -> dict:
    return {
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


def _revenue_history(financial: dict) -> list:
    return [
        {"ano": 2022, "valor": financial.get("revenue_2022", "est.")},
        {"ano": 2023, "valor": financial.get("revenue_2023", "est.")},
        {"ano": 2024, "valor": financial.get("revenue_2024", "est.")},
    ]


def financial_node(state: JobState) -> dict:
    company_name = state["company_name"]
    yahoo_data = _fetch_yahoo_finance(company_name)
    research = state.get("research_structured") or {}
    client_context = state.get("client_context") or ""
    research_context = truncate_text(json.dumps(research, ensure_ascii=False), 3000)

    prompt = _financial_prompt(
        company_name, research_context, yahoo_data, client_context
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

    kpis = _to_kpis(financial_structured)
    if yahoo_data:
        kpis["yahoo_finance"] = yahoo_data

    return {
        "financial_structured": financial_structured,
        "kpis": kpis,
        "revenue_history": _revenue_history(financial_structured),
        "revenue_breakdown": [],
    }
