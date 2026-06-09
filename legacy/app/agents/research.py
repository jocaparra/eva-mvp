import os
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from langchain_community.tools.tavily_search import TavilySearchResults

from app.ingestion.retrieval import (
    chunks_to_citations,
    format_dataroom_context,
    retrieve_for_deal,
)
from app.json_utils import invoke_json_llm
from app.llm import truncate_text
from app.media import download_file
from app.state import Citation, JobState

MAX_SNIPPET_CHARS = 350
MAX_SEARCH_CONTEXT = 6000

DATAROOM_QUERIES = {
    "CIM": [
        "{company} overview negócio modelo receita produtos",
        "{company} mercado concorrentes posicionamento fundadores",
    ],
    "VALUATION": [
        "{company} receita EBITDA margens histórico financeiro",
        "{company} valuation múltiplos comparáveis transações",
    ],
    "DUE_DILIGENCE": [
        "{company} litígios riscos regulatório governança",
        "{company} passivo contingências operação compliance",
    ],
}

EXTERNAL_QUERIES = {
    "CIM": [
        "{company} market competitors sector trends",
    ],
    "VALUATION": [
        "{company} sector multiples comparable public companies",
    ],
    "DUE_DILIGENCE": [
        "{company} industry regulatory landscape",
    ],
}

STRUCTURE_FIX = (
    "Retorne JSON válido com todos os campos. Textos limpos em português, "
    "sem markdown, sem URLs, sem pipes."
)


def _tavily_search(query: str) -> list[str]:
    if not os.getenv("TAVILY_API_KEY"):
        return []
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


def _external_citations(snippets: list[str]) -> List[Citation]:
    citations: List[Citation] = []
    for idx, snippet in enumerate(snippets, start=1):
        citations.append(
            {
                "source_file": "web_search",
                "page": idx,
                "chunk_id": f"external-{idx}",
                "quote": truncate_text(snippet, 400),
                "source": "external",
            }
        )
    return citations


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


def _synthesize_research(
    company_name: str,
    *,
    dataroom_context: str,
    external_context: str,
    legacy_client_context: str = "",
) -> dict:
    dataroom_block = ""
    if dataroom_context.strip():
        dataroom_block = (
            "\n\nFONTE PRIMÁRIA — documentos confidenciais do data room do cliente "
            "(priorize estes dados; cite a origem mentalmente):\n"
            f"{truncate_text(dataroom_context, 6000)}\n"
        )

    external_block = ""
    if external_context.strip():
        external_block = (
            "\n\nFONTE COMPLEMENTAR EXTERNA — mercado/comparáveis (use apenas para "
            "contexto setorial; marque como estimativa se não confirmado no data room):\n"
            f"{truncate_text(external_context, 3000)}\n"
        )

    legacy_block = ""
    if legacy_client_context.strip() and not dataroom_context.strip():
        legacy_block = (
            "\n\nContexto adicional enviado pelo cliente:\n"
            f"{truncate_text(legacy_client_context, 4000)}\n"
        )

    prompt = (
        f"Você recebeu dados sobre {company_name}.\n"
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
        "- Priorize fatos dos documentos do data room sobre fontes externas\n"
        "- Nunca inclua pipes |, URLs, hífens ---, ou qualquer formatação markdown\n"
        "- Todos os textos devem ser frases limpas em português\n"
        "- Se um dado não estiver no data room, use fonte externa ou estimativa 'est.'\n"
        "- Retorne APENAS o JSON, sem texto antes ou depois\n"
        f"{dataroom_block}{external_block}{legacy_block}"
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
    deal_id = state.get("deal_id") or ""

    # 1) Fonte primária: data room indexado por deal
    dataroom_queries = [
        q.format(company=company_name)
        for q in DATAROOM_QUERIES.get(document_type, DATAROOM_QUERIES["CIM"])
    ]
    dataroom_chunks = retrieve_for_deal(deal_id, dataroom_queries, k=5) if deal_id else []
    dataroom_citations = chunks_to_citations(dataroom_chunks, source="data_room")
    dataroom_context = format_dataroom_context(dataroom_chunks)

    # 2) Fonte complementar externa: Tavily (mercado/comparáveis)
    external_queries = [
        q.format(company=company_name)
        for q in EXTERNAL_QUERIES.get(document_type, EXTERNAL_QUERIES["CIM"])
    ]
    external_snippets: list[str] = []
    for query in external_queries:
        external_snippets.extend(_tavily_search(query))
    external_citations = _external_citations(external_snippets)
    external_context = "\n\n".join(external_snippets)

    legacy_client_context = state.get("client_context") or ""
    research_structured = _synthesize_research(
        company_name,
        dataroom_context=dataroom_context,
        external_context=external_context,
        legacy_client_context=legacy_client_context,
    )
    research_structured["company_name"] = company_name

    all_citations: List[Citation] = dataroom_citations + external_citations

    logo_path = None
    if external_snippets:
        try:
            domain = _extract_domain(external_snippets, company_name)
            if domain:
                logo_path = _download_logo(domain, job_id)
        except Exception:
            pass

    result = {
        "research_structured": research_structured,
        "research_data": research_structured.get("description", ""),
        "research_citations": all_citations,
        "retrieved_context": dataroom_citations,
    }
    if logo_path:
        result["logo_path"] = logo_path
    return result
