"""Testes da Etapa 3 — research/financial com RAG e citações."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-stage3-tests")
os.environ.pop("GOOGLE_API_KEY", None)
os.environ.pop("TAVILY_API_KEY", None)

from app.agents.financial import financial_node
from app.agents.research import research_node
from app.database import get_session_factory, init_db
from app.repositories.deal_workspace import create_deal
from app.services.document_ingestion import ingest_deal_document


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def db_session() -> Session:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()


def _make_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _mock_synthesize(company_name: str, **kwargs) -> dict:
    dataroom = kwargs.get("dataroom_context", "")
    return {
        "company_name": company_name,
        "description": "Empresa de logística urbana com receita consolidada.",
        "sector": "Logística",
        "business_model": dataroom[:120] if dataroom else "Modelo est.",
        "key_products": ["Entregas", "Fulfillment", "Tracking"],
        "main_competitors": ["Concorrente A", "Concorrente B", "Concorrente C"],
        "tagline": "Logística urbana",
        "founded": "2015",
        "headquarters": "São Paulo, Brasil",
        "founders": "Fundadores",
        "employees": "500",
        "market_position": "Líder regional",
        "recent_news": "Expansão",
        "sector_image_keyword": "logistics",
    }


def _mock_financial_json(*args, **kwargs) -> dict:
    return {
        "revenue_2022": "R$ 40M",
        "revenue_2023": "R$ 50M",
        "revenue_2024": "R$ 50 milhões",
        "ebitda": "15%",
        "net_margin": "10%",
        "growth_yoy": "+25%",
        "valuation": "R$ 200M",
        "ev_ebitda": "8x",
        "pe_ratio": "18x",
        "ev_revenue": "4x",
        "comparable_companies": [],
        "valuation_low": "R$ 150M",
        "valuation_mid": "R$ 200M",
        "valuation_high": "R$ 250M",
        "valuation_method_1": "DCF",
        "valuation_method_2": "Comparáveis",
        "valuation_method_3": "Transações",
        "red_flags": [],
        "risk_score": "Baixo",
        "risk_justification": "Crescimento sólido",
        "risks": [],
    }


@patch("app.agents.research._synthesize_research", side_effect=_mock_synthesize)
@patch("app.agents.research._tavily_search", return_value=["Setor logístico aquecido"])
def test_research_returns_citations_from_uploaded_document(
    _mock_tavily,
    _mock_synth,
    db_session: Session,
):
    deal = create_deal(db_session, company_name="Loggi", owner_phone="5511999999999")
    pdf = _make_pdf("Receita consolidada 2024: R$ 50 milhões. Margem EBITDA 15%.")
    ingest_deal_document(
        db_session,
        deal_id=deal.id,
        owner_phone="5511999999999",
        filename="teaser.pdf",
        content=pdf,
        mime_type="application/pdf",
    )

    result = research_node(
        {
            "job_id": "job-test",
            "company_name": "Loggi",
            "document_type": "CIM",
            "deal_id": str(deal.id),
        }
    )

    dataroom_citations = [
        c for c in result.get("research_citations", []) if c.get("source") == "data_room"
    ]
    assert dataroom_citations, "Esperava citações do data room"
    assert dataroom_citations[0]["source_file"] == "teaser.pdf"
    assert dataroom_citations[0]["page"] == 1
    assert "50 milhões" in dataroom_citations[0]["quote"]

    external = [c for c in result.get("research_citations", []) if c.get("source") == "external"]
    assert external, "Esperava citação externa complementar"


@patch("app.agents.financial.invoke_json_llm", side_effect=_mock_financial_json)
@patch("app.agents.financial._target_is_public", return_value=False)
def test_financial_uses_dataroom_citations(
    _mock_public,
    _mock_llm,
    db_session: Session,
):
    deal = create_deal(db_session, company_name="Loggi", owner_phone="5511999999999")
    pdf = _make_pdf("Receita 2024: R$ 50 milhões. EBITDA margin 15%.")
    ingest_deal_document(
        db_session,
        deal_id=deal.id,
        owner_phone="5511999999999",
        filename="financials.pdf",
        content=pdf,
        mime_type="application/pdf",
    )

    result = financial_node(
        {
            "job_id": "job-test",
            "company_name": "Loggi",
            "document_type": "VALUATION",
            "deal_id": str(deal.id),
            "research_structured": {"sector": "Logística"},
            "retrieved_context": [],
        }
    )

    citations = result.get("financial_citations") or []
    dataroom = [c for c in citations if c.get("source") == "data_room"]
    assert dataroom
    assert dataroom[0]["source_file"] == "financials.pdf"

    field_citations = (result.get("financial_structured") or {}).get("_field_citations") or {}
    assert "revenue_2024" in field_citations
    assert field_citations["revenue_2024"]["source_file"] == "financials.pdf"
