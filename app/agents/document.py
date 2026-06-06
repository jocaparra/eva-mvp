import os
from datetime import date
from typing import List, Optional

import requests
from dotenv import load_dotenv

from app.state import JobState

load_dotenv()

PRESENTON_API_KEY = os.getenv("PRESENTON_API_KEY")
PRESENTON_URL = "https://api.presenton.ai/api/v1/ppt/presentation/generate"

TEMPLATE_MAP = {
    "CIM": "corporate",
    "VALUATION": "modern",
    "DUE_DILIGENCE": "professional",
}

N_SLIDES_MAP = {
    "CIM": 10,
    "VALUATION": 12,
    "DUE_DILIGENCE": 12,
}


def _join_items(items: Optional[List]) -> str:
    if not items:
        return "Não informado"
    return ", ".join(str(item) for item in items)


def build_content(state: dict, doc_type: str) -> str:
    r = state.get("research_structured", {})
    f = state.get("financial_structured", {})
    company = r.get("company_name") or state.get("company_name", "Empresa")

    if doc_type == "CIM":
        return f"""
        CIM — Confidential Information Memorandum: {company}

        Empresa: {company}
        Setor: {r.get("sector")}
        Fundação: {r.get("founded")} | Sede: {r.get("headquarters")}
        Fundadores: {r.get("founders")}
        Funcionários: {r.get("employees")}

        Descrição: {r.get("description")}
        Modelo de Negócio: {r.get("business_model")}
        Principais Produtos: {_join_items(r.get("key_products"))}
        Posição de Mercado: {r.get("market_position")}
        Principais Concorrentes: {_join_items(r.get("main_competitors"))}

        Dados Financeiros:
        Receita 2022: {f.get("revenue_2022")} | 2023: {f.get("revenue_2023")} | 2024: {f.get("revenue_2024")}
        EBITDA: {f.get("ebitda")} | Margem Líquida: {f.get("net_margin")}
        Crescimento: {f.get("growth_yoy")} | Valuation: {f.get("valuation")}

        Notícias Recentes: {r.get("recent_news")}
        Oportunidade de Investimento: empresa líder em {r.get("sector")} com
        crescimento consistente e posição defensável de mercado.
        """

    if doc_type == "VALUATION":
        comparables = f.get("comparable_companies", [])
        comp_text = "\n".join(
            f"- {c.get('name')}: EV/EBITDA {c.get('ev_ebitda')}, P/L {c.get('pe')}"
            for c in comparables
        )
        return f"""
        Valuation Report: {company}

        Empresa: {company} | Setor: {r.get("sector")}
        Descrição: {r.get("description")}

        Histórico Financeiro:
        Receita 2022: {f.get("revenue_2022")}
        Receita 2023: {f.get("revenue_2023")}
        Receita 2024: {f.get("revenue_2024")}
        EBITDA e Margem: {f.get("ebitda")}
        Crescimento YoY: {f.get("growth_yoy")}

        Múltiplos de Mercado:
        EV/EBITDA: {f.get("ev_ebitda")} | P/L: {f.get("pe_ratio")} | EV/Receita: {f.get("ev_revenue")}

        Empresas Comparáveis:
        {comp_text}

        Range de Valuation:
        Conservador: {f.get("valuation_low")}
        Base: {f.get("valuation_mid")}
        Otimista: {f.get("valuation_high")}

        Metodologia 1 — Múltiplo de Receita: {f.get("valuation_method_1")}
        Metodologia 2 — Múltiplo de EBITDA: {f.get("valuation_method_2")}
        Metodologia 3 — Comparáveis: {f.get("valuation_method_3")}
        """

    if doc_type == "DUE_DILIGENCE":
        red_flags = f.get("red_flags", "Nenhum crítico identificado")
        if isinstance(red_flags, list):
            red_flags = ", ".join(str(flag) for flag in red_flags)
        return f"""
        Due Diligence Report: {company}

        Empresa: {company} | Setor: {r.get("sector")}
        Fundação: {r.get("founded")} | Sede: {r.get("headquarters")}
        Fundadores: {r.get("founders")} | Funcionários: {r.get("employees")}

        Descrição: {r.get("description")}
        Modelo de Negócio: {r.get("business_model")}
        Posição de Mercado: {r.get("market_position")}

        Análise Financeira:
        Receita 2024: {f.get("revenue_2024")} | EBITDA: {f.get("ebitda")}
        Crescimento: {f.get("growth_yoy")} | Margem: {f.get("net_margin")}

        Riscos Identificados: {f.get("risk_score", "Médio")}
        Red Flags: {red_flags}
        Indicadores de Saúde Financeira: {f.get("financial_health", "Estável")}

        Concorrentes: {_join_items(r.get("main_competitors"))}
        Notícias Recentes: {r.get("recent_news")}
        """

    return f"Relatório institucional: {company}\n\n{r.get('description', '')}"


def _save_ppt_result(
    state: dict,
    *,
    output_path: str,
    filename: str,
    edit_url: Optional[str] = None,
) -> dict:
    state["output_path"] = output_path
    state["output_filename"] = filename
    state["ppt_path"] = output_path
    state["ppt_filename"] = filename
    if edit_url:
        state["edit_url"] = edit_url
    return state


def presenton_document(state: dict) -> dict:
    """Gera PPT via Presenton API (templates genéricos)."""
    doc_type = state.get("document_type", "CIM")
    company = state.get("research_structured", {}).get("company_name") or state.get(
        "company_name", "empresa"
    )
    job_id = state.get("job_id", "unknown")

    if not PRESENTON_API_KEY:
        raise ValueError(
            "PRESENTON_API_KEY não encontrada no .env. "
            "Gere sua chave em presenton.ai/api-key"
        )

    content = state.get("_generation_plain") or build_content(state, doc_type)
    payload = {
        "content": content,
        "n_slides": N_SLIDES_MAP.get(doc_type, 10),
        "language": "Portuguese",
        "template": TEMPLATE_MAP.get(doc_type, "modern"),
        "export_as": "pptx",
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PRESENTON_API_KEY}",
    }

    primary_template = TEMPLATE_MAP.get(doc_type, "modern")
    templates_to_try = [primary_template]
    if primary_template == "professional":
        templates_to_try.append("modern")

    response = None
    last_exc: Optional[Exception] = None
    for template in templates_to_try:
        payload["template"] = template
        try:
            response = requests.post(
                PRESENTON_URL, json=payload, headers=headers, timeout=120
            )
            print(f"[document_agent] Presenton status={response.status_code} template={template}")
            print(f"[document_agent] Presenton response={response.text[:500]}")
            response.raise_for_status()
            break
        except Exception as exc:
            last_exc = exc
            print(
                f"[document_agent] Presenton falhou template={template} "
                f"tipo={type(exc).__name__} msg={exc}"
            )
            if hasattr(exc, "response") and exc.response is not None:
                print(f"[document_agent] PRESENTON RESPONSE: {exc.response.text}")
            if template != templates_to_try[-1]:
                print("[document_agent] Retentando Presenton com template=modern")
                continue
            raise last_exc from exc

    if response is None:
        raise RuntimeError("Presenton não retornou resposta") from last_exc

    result = response.json()

    pptx_url = result.get("path")
    if not pptx_url:
        raise RuntimeError(f"Presenton não retornou URL: {result}")

    filename = f"{company}_{doc_type}_{date.today()}.pptx"
    output_path = f"outputs/{job_id}.pptx"
    os.makedirs("outputs", exist_ok=True)

    file_response = requests.get(pptx_url, timeout=60)
    file_response.raise_for_status()
    with open(output_path, "wb") as out_file:
        out_file.write(file_response.content)

    return _save_ppt_result(
        state,
        output_path=output_path,
        filename=filename,
        edit_url=result.get("edit_path"),
    )


def canva_document(state: dict) -> dict:
    """Gera PPT via Canva brand template (branding do cliente)."""
    from app.agents.canva_client import generate_pptx_from_brand_template

    doc_type = state.get("document_type", "CIM")
    company = state.get("research_structured", {}).get("company_name") or state.get(
        "company_name", "empresa"
    )
    job_id = state.get("job_id", "unknown")

    filename = f"{company}_{doc_type}_{date.today()}.pptx"
    output_path = f"outputs/{job_id}.pptx"

    generate_pptx_from_brand_template(state, doc_type, output_path)
    return _save_ppt_result(state, output_path=output_path, filename=filename)


def run_document_agent(state: dict) -> dict:
    doc_type = state.get("document_type", "CIM")
    company = state.get("research_structured", {}).get("company_name") or state.get(
        "company_name", "empresa"
    )
    client_id = state.get("client_id", "default")
    job_id = state.get("job_id", "unknown")

    from app.utils.template import cleanup_temp_template, get_template_path

    template_path = get_template_path(client_id, job_id=job_id)
    if template_path and os.path.exists(template_path):
        try:
            from app.agents.document_pptx import generate_pptx_from_template

            output_path = f"outputs/{job_id}.pptx"
            print(
                f"Document agent: template PPTX ({client_id}) → {template_path} "
                f"para {company} ({doc_type})"
            )
            result = generate_pptx_from_template(state, template_path, output_path)
            return _save_ppt_result(
                state,
                output_path=result["ppt_path"],
                filename=result["ppt_filename"],
            )
        except Exception as exc:
            print(f"Template PPTX falhou, fallback Presenton: {exc}")
        finally:
            cleanup_temp_template(template_path)

    try:
        print(f"Document agent: Presenton para {company} ({doc_type})")
        return presenton_document(state)
    except Exception as exc:
        import traceback

        print(f"[document_agent] ERRO tipo={type(exc).__name__} msg={exc}")
        print(f"[document_agent] TRACEBACK: {traceback.format_exc()}")
        if hasattr(exc, "response") and exc.response is not None:
            print(f"[document_agent] PRESENTON RESPONSE: {exc.response.text}")
        state["error"] = f"Erro no Document Agent: {exc}"
        return state


def document_node(state: JobState) -> dict:
    from app.artifact_types import resolve_artifact_type
    from app.generation.generate import generate

    artifact_type = state.get("artifact_type") or resolve_artifact_type(
        state.get("document_type", "CIM"),
        message=state.get("job_message", ""),
    )
    deal_state = dict(state)
    deal_state["artifact_type"] = artifact_type

    try:
        result = generate(artifact_type, deal_state)
    except Exception as exc:
        raise RuntimeError(f"Erro no Document Agent: {exc}") from exc

    payload = {
        "artifact_type": result.artifact_type,
        "file_path": result.file_path,
        "file_filename": result.file_filename,
        "ppt_path": result.file_path if result.format == "pptx" else state.get("ppt_path"),
        "ppt_filename": result.file_filename if result.format == "pptx" else state.get("ppt_filename"),
        "edit_url": state.get("edit_url"),
    }
    if result.format == "pptx":
        payload["ppt_path"] = result.file_path
        payload["ppt_filename"] = result.file_filename
    return payload
