import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from langchain_community.tools.tavily_search import TavilySearchResults

from app.json_utils import invoke_json_llm
from app.llm import truncate_text
from app.media import download_file
from app.state import JobState

MAX_SNIPPET_CHARS = 350
MAX_SEARCH_CONTEXT = 6000

SEARCH_QUERIES = {
    "CIM": [
        "{company} company overview business model",
        "{company} financial revenue market competitors buyers",
    ],
    "VALUATION": [
        "{company} revenue EBITDA margins historical financials",
        "{company} sector multiples comparable transactions valuation",
    ],
    "DUE_DILIGENCE": [
        "{company} litigation lawsuits regulatory issues",
        "{company} founders reputation negative news operational risks governance",
    ],
}

STRUCTURE_FIX = (
    "Retorne JSON válido com todos os campos. Textos limpos em português, "
    "sem markdown, sem URLs, sem pipes."
)


def _tavily_search(query: str) -> list[str]:
    tavily = TavilySearchResults(
        max_results=3,
        api_key=os.environ["TAVILY_API_KEY"],
    )
    results = tavily.invoke({"query": query})
    snippets: list[str] = []

    for item in results:
        if isinstance(item, dict):
            title = item.get("title", "N/A")
            content = truncate_text(item.get("content", ""), MAX_SNIPPET_CHARS)
            snippets.append(f"{title}\n{content}")
        else:
            snippets.append(truncate_text(str(item), MAX_SNIPPET_CHARS))

    return snippets


def _extract_domain(results: list[str], company_name: str) -> Optional[str]:
    url_pattern = re.compile(r"https?://[^\s\)\]\>\"']+", re.IGNORECASE)
    skip_domains = {
        "google.com",
        "facebook.com",
        "linkedin.com",
        "wikipedia.org",
        "twitter.com",
        "x.com",
    }

    for text in results:
        for url in url_pattern.findall(text):
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")
            if not domain or "." not in domain:
                continue
            if any(skip in domain for skip in skip_domains):
                continue
            return domain

    slug = re.sub(r"[^a-z0-9]", "", company_name.lower())
    if slug:
        return f"{slug}.com"
    return None


def _download_logo(domain: str, job_id: str) -> Optional[str]:
    try:
        logo_path = Path(f"/tmp/{job_id}_logo.png")
        if download_file(f"https://logo.clearbit.com/{domain}", logo_path):
            return str(logo_path)
        if download_file(
            f"https://www.google.com/s2/favicons?domain={domain}&sz=256",
            logo_path,
        ):
            return str(logo_path)
    except Exception:
        return None
    return None


def _fallback_research_structured(company_name: str) -> dict:
    return {
        "company_name": company_name,
        "tagline": f"Líder consolidada em seu segmento est.",
        "founded": "Anos 2000 est.",
        "headquarters": "Brasil est.",
        "sector": "Serviços est.",
        "description": (
            f"{company_name} atua em seu mercado principal com presença "
            f"relevante no Brasil est."
        ),
        "business_model": (
            "Receita recorrente via produtos e serviços core est."
        ),
        "key_products": [
            "Produto principal est.",
            "Serviço core est.",
            "Plataforma digital est.",
        ],
        "founders": "Fundadores de referência no setor est.",
        "employees": "Milhares de colaboradores est.",
        "market_position": f"{company_name} mantém posição competitiva est.",
        "main_competitors": [
            "Concorrente regional est.",
            "Concorrente nacional est.",
            "Player global est.",
        ],
        "recent_news": "Expansão e novos produtos recentes est.",
        "sector_image_keyword": "business office",
    }


def _synthesize_research(company_name: str, raw_research_data: str) -> dict:
    prompt = (
        f"Você recebeu dados brutos de pesquisa sobre {company_name}.\n"
        "Sintetize em um relatório estruturado em JSON com exatamente estes campos:\n\n"
        "{\n"
        "  'company_name': str,\n"
        "  'tagline': str (máx 10 palavras),\n"
        "  'founded': str (ano ou período),\n"
        "  'headquarters': str (cidade, país),\n"
        "  'sector': str (setor principal),\n"
        "  'description': str (2-3 frases claras sobre o que a empresa faz),\n"
        "  'business_model': str (como a empresa ganha dinheiro, 2-3 frases),\n"
        "  'key_products': [str, str, str] (3 principais produtos ou serviços),\n"
        "  'founders': str (nomes dos fundadores),\n"
        "  'employees': str (número aproximado de funcionários),\n"
        "  'market_position': str (posição no mercado, 1-2 frases),\n"
        "  'main_competitors': [str, str, str] (3 concorrentes principais),\n"
        "  'recent_news': str (notícia ou evento relevante recente, 1-2 frases),\n"
        "  'sector_image_keyword': str (palavra-chave em inglês para buscar imagem)\n"
        "}\n\n"
        "REGRAS ABSOLUTAS:\n"
        "- Nunca inclua pipes |, URLs, hífens ---, ou qualquer formatação markdown\n"
        "- Todos os textos devem ser frases limpas em português\n"
        "- Se um dado não estiver disponível, escreva uma estimativa razoável "
        "baseada no que você sabe sobre a empresa, NUNCA retorne 'N/D' ou vazio\n"
        "- Retorne APENAS o JSON, sem texto antes ou depois\n\n"
        f"Dados brutos: {raw_research_data}"
    )
    try:
        return invoke_json_llm(
            "Você sintetiza pesquisa empresarial em JSON limpo.",
            prompt,
            STRUCTURE_FIX,
        )
    except Exception:
        return _fallback_research_structured(company_name)


def research_node(state: JobState) -> dict:
    company_name = state["company_name"]
    job_id = state["job_id"]
    document_type = state.get("document_type", "CIM")

    queries = [
        q.format(company=company_name)
        for q in SEARCH_QUERIES.get(document_type, SEARCH_QUERIES["CIM"])
    ]

    raw_results: list[str] = []
    for query in queries:
        raw_results.extend(_tavily_search(query))

    raw_research_data = truncate_text("\n\n".join(raw_results), MAX_SEARCH_CONTEXT)
    research_structured = _synthesize_research(company_name, raw_research_data)
    research_structured["company_name"] = company_name

    logo_path = None
    try:
        domain = _extract_domain(raw_results, company_name)
        if domain:
            logo_path = _download_logo(domain, job_id)
    except Exception:
        pass

    result = {
        "research_structured": research_structured,
        "research_data": research_structured.get("description", ""),
    }
    if logo_path:
        result["logo_path"] = logo_path
    return result
