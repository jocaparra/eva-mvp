"""Canva Connect API — brand template autofill + PPTX export."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

CANVA_API_BASE = "https://api.canva.com/rest/v1"
CANVA_API_KEY = os.getenv("CANVA_API_KEY")
CANVA_BRAND_TEMPLATE_ID = os.getenv("CANVA_BRAND_TEMPLATE_ID")

POLL_INTERVAL_SEC = 2.0
AUTOFILL_MAX_WAIT_SEC = 120
EXPORT_MAX_WAIT_SEC = 120


def canva_configured() -> bool:
    return bool(CANVA_API_KEY and CANVA_BRAND_TEMPLATE_ID)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {CANVA_API_KEY}",
        "Content-Type": "application/json",
    }


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


# Template field name (normalized) -> our dataset key
_FIELD_ALIASES: dict[str, str] = {
    "companyname": "company_name",
    "company": "company_name",
    "empresa": "company_name",
    "nomeempresa": "company_name",
    "tagline": "tagline",
    "slogan": "tagline",
    "description": "description",
    "descricao": "description",
    "descrição": "description",
    "businessmodel": "business_model",
    "modelodenegocio": "business_model",
    "sector": "sector",
    "setor": "sector",
    "founded": "founded",
    "fundacao": "founded",
    "fundação": "founded",
    "headquarters": "headquarters",
    "sede": "headquarters",
    "founders": "founders",
    "fundadores": "founders",
    "employees": "employees",
    "funcionarios": "employees",
    "funcionários": "employees",
    "equipe": "employees",
    "marketposition": "market_position",
    "posicaodemercado": "market_position",
    "recentnews": "recent_news",
    "noticias": "recent_news",
    "notícias": "recent_news",
    "keyproducts": "key_products",
    "produtos": "key_products",
    "maincompetitors": "main_competitors",
    "concorrentes": "main_competitors",
    "revenue2022": "revenue_2022",
    "receita2022": "revenue_2022",
    "revenue2023": "revenue_2023",
    "receita2023": "revenue_2023",
    "revenue2024": "revenue_2024",
    "receita2024": "revenue_2024",
    "ebitda": "ebitda",
    "netmargin": "net_margin",
    "margemliquida": "net_margin",
    "growthyoy": "growth_yoy",
    "crescimento": "growth_yoy",
    "valuation": "valuation",
    "valuacao": "valuation",
    "valuação": "valuation",
    "evebitda": "ev_ebitda",
    "peratio": "pe_ratio",
    "evrevenue": "ev_revenue",
    "valuationlow": "valuation_low",
    "valuationmid": "valuation_mid",
    "valuationhigh": "valuation_high",
    "valuationmethod1": "valuation_method_1",
    "valuationmethod2": "valuation_method_2",
    "valuationmethod3": "valuation_method_3",
    "comparables": "comparables",
    "documenttype": "document_type",
    "reporttitle": "report_title",
    "titulo": "report_title",
    "título": "report_title",
    "content": "full_content",
    "conteudo": "full_content",
    "conteúdo": "full_content",
}


def build_canva_field_values(state: dict, doc_type: str) -> dict[str, str]:
    """Flat string map from structured research/financial data."""
    r = state.get("research_structured") or {}
    f = state.get("financial_structured") or {}
    company = r.get("company_name") or state.get("company_name", "Empresa")

    products = r.get("key_products") or []
    competitors = r.get("main_competitors") or []
    comps = f.get("comparable_companies") or []
    comp_lines = [
        f"{c.get('name')}: EV/EBITDA {c.get('ev_ebitda')}, P/L {c.get('pe')}"
        for c in comps[:3]
    ]

    doc_labels = {
        "CIM": "Confidential Information Memorandum",
        "VALUATION": "Valuation Report",
        "DUE_DILIGENCE": "Due Diligence Report",
    }

    values: dict[str, str] = {
        "company_name": str(company),
        "tagline": str(r.get("tagline") or ""),
        "description": str(r.get("description") or ""),
        "business_model": str(r.get("business_model") or ""),
        "sector": str(r.get("sector") or ""),
        "founded": str(r.get("founded") or ""),
        "headquarters": str(r.get("headquarters") or ""),
        "founders": str(r.get("founders") or ""),
        "employees": str(r.get("employees") or ""),
        "market_position": str(r.get("market_position") or ""),
        "recent_news": str(r.get("recent_news") or ""),
        "key_products": ", ".join(str(p) for p in products),
        "main_competitors": ", ".join(str(c) for c in competitors),
        "revenue_2022": str(f.get("revenue_2022") or ""),
        "revenue_2023": str(f.get("revenue_2023") or ""),
        "revenue_2024": str(f.get("revenue_2024") or ""),
        "ebitda": str(f.get("ebitda") or ""),
        "net_margin": str(f.get("net_margin") or ""),
        "growth_yoy": str(f.get("growth_yoy") or ""),
        "valuation": str(f.get("valuation") or ""),
        "ev_ebitda": str(f.get("ev_ebitda") or ""),
        "pe_ratio": str(f.get("pe_ratio") or ""),
        "ev_revenue": str(f.get("ev_revenue") or ""),
        "valuation_low": str(f.get("valuation_low") or ""),
        "valuation_mid": str(f.get("valuation_mid") or ""),
        "valuation_high": str(f.get("valuation_high") or ""),
        "valuation_method_1": str(f.get("valuation_method_1") or ""),
        "valuation_method_2": str(f.get("valuation_method_2") or ""),
        "valuation_method_3": str(f.get("valuation_method_3") or ""),
        "comparables": "\n".join(comp_lines),
        "document_type": doc_type,
        "report_title": f"{doc_labels.get(doc_type, doc_type)} — {company}",
    }

    from app.agents.document import build_content

    values["full_content"] = build_content(state, doc_type).strip()
    return values


def _resolve_value(field_name: str, field_values: dict[str, str]) -> Optional[str]:
    norm = _normalize_key(field_name)
    alias_key = _FIELD_ALIASES.get(norm)
    if alias_key:
        val = field_values.get(alias_key)
        if val:
            return val
    for alias_norm, our_key in _FIELD_ALIASES.items():
        if alias_norm in norm or norm in alias_norm:
            val = field_values.get(our_key)
            if val:
                return val
    return field_values.get("full_content") or field_values.get("company_name")


def _build_autofill_data(
    template_fields: dict[str, Any],
    field_values: dict[str, str],
) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for field_name, field_def in template_fields.items():
        field_type = (field_def or {}).get("type")
        if field_type == "text":
            text = _resolve_value(field_name, field_values)
            if text:
                data[field_name] = {"type": "text", "text": text[:8000]}
        # Images/charts skipped in sprint 1 (require asset_id / chart_data)
    return data


def get_brand_template_dataset(template_id: str) -> dict[str, Any]:
    url = f"{CANVA_API_BASE}/brand-templates/{template_id}/dataset"
    response = requests.get(url, headers=_headers(), timeout=30)
    response.raise_for_status()
    return response.json().get("dataset", {})


def create_autofill_job(
    template_id: str,
    data: dict[str, Any],
    *,
    title: str,
) -> str:
    url = f"{CANVA_API_BASE}/autofills"
    payload = {
        "brand_template_id": template_id,
        "title": title,
        "data": data,
    }
    response = requests.post(url, headers=_headers(), json=payload, timeout=30)
    response.raise_for_status()
    job = response.json().get("job", {})
    job_id = job.get("id")
    if not job_id:
        raise RuntimeError(f"Canva autofill não retornou job id: {response.json()}")
    return job_id


def wait_autofill_job(job_id: str) -> str:
    url = f"{CANVA_API_BASE}/autofills/{job_id}"
    deadline = time.time() + AUTOFILL_MAX_WAIT_SEC
    while time.time() < deadline:
        response = requests.get(url, headers=_headers(), timeout=30)
        response.raise_for_status()
        body = response.json()
        job = body.get("job", {})
        status = job.get("status")
        if status == "success":
            result = job.get("result", {})
            design = result.get("design", {})
            design_id = design.get("id")
            if design_id:
                return design_id
            raise RuntimeError(f"Canva autofill sem design id: {body}")
        if status == "failed":
            raise RuntimeError(f"Canva autofill falhou: {body}")
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"Canva autofill timeout ({AUTOFILL_MAX_WAIT_SEC}s)")


def create_export_job(design_id: str) -> str:
    url = f"{CANVA_API_BASE}/exports"
    payload = {
        "design_id": design_id,
        "format": {"type": "pptx"},
    }
    response = requests.post(url, headers=_headers(), json=payload, timeout=30)
    response.raise_for_status()
    job = response.json().get("job", {})
    job_id = job.get("id")
    if not job_id:
        raise RuntimeError(f"Canva export não retornou job id: {response.json()}")
    return job_id


def wait_export_job(job_id: str) -> str:
    url = f"{CANVA_API_BASE}/exports/{job_id}"
    deadline = time.time() + EXPORT_MAX_WAIT_SEC
    while time.time() < deadline:
        response = requests.get(url, headers=_headers(), timeout=30)
        response.raise_for_status()
        body = response.json()
        job = body.get("job", {})
        status = job.get("status")
        if status == "success":
            urls = job.get("urls") or []
            if urls:
                return urls[0]
            raise RuntimeError(f"Canva export sem URL: {body}")
        if status == "failed":
            raise RuntimeError(f"Canva export falhou: {body}")
        time.sleep(POLL_INTERVAL_SEC)
    raise TimeoutError(f"Canva export timeout ({EXPORT_MAX_WAIT_SEC}s)")


def download_pptx(download_url: str, output_path: str) -> None:
    response = requests.get(download_url, timeout=120)
    response.raise_for_status()
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as out_file:
        out_file.write(response.content)


def generate_pptx_from_brand_template(
    state: dict,
    doc_type: str,
    output_path: str,
    *,
    template_id: Optional[str] = None,
) -> None:
    template_id = template_id or CANVA_BRAND_TEMPLATE_ID
    if not template_id or not CANVA_API_KEY:
        raise ValueError("CANVA_API_KEY e CANVA_BRAND_TEMPLATE_ID são obrigatórios")

    field_values = build_canva_field_values(state, doc_type)
    template_fields = get_brand_template_dataset(template_id)
    autofill_data = _build_autofill_data(template_fields, field_values)
    if not autofill_data:
        raise RuntimeError(
            "Nenhum campo de texto compatível no template Canva. "
            "Verifique os nomes dos data fields no brand template."
        )

    title = field_values.get("report_title", field_values.get("company_name", "EVA Document"))
    autofill_job_id = create_autofill_job(template_id, autofill_data, title=title)
    design_id = wait_autofill_job(autofill_job_id)
    export_job_id = create_export_job(design_id)
    download_url = wait_export_job(export_job_id)
    download_pptx(download_url, output_path)
