"""Testes da Etapa 4 — QA factual e política legado."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-stage4-tests")

from app.agents.qa_factual import run_factual_qa, validate_factual
from app.citations.matching import (
    CitationStatus,
    audit_financial_field,
    audit_financial_structured,
)
from app.state import Citation


def _citation(quote: str, source: str = "data_room", source_file: str = "teaser.pdf") -> Citation:
    return {
        "source_file": source_file,
        "page": 1,
        "chunk_id": "chunk-1",
        "quote": quote,
        "source": source,
    }


def test_number_present_in_source_passes():
    financial = {"revenue_2024": "R$ 50 milhões", "ebitda": "15% est."}
    citations = [_citation("Receita consolidada 2024: R$ 50 milhões. Margem EBITDA 15%.")]

    issues, audits = validate_factual(
        {
            "financial_structured": financial,
            "financial_citations": citations,
            "deal_id": "deal-1",
        }
    )
    assert not issues
    assert audits["revenue_2024"]["status"] == CitationStatus.CITED.value
    assert audits["revenue_2024"]["citation"] is not None


def test_number_absent_from_source_is_issue():
    financial = {"revenue_2024": "R$ 99 milhões"}
    citations = [_citation("Receita consolidada 2024: R$ 50 milhões.")]

    issues, audits = validate_factual(
        {
            "financial_structured": financial,
            "financial_citations": citations,
            "deal_id": "deal-1",
        }
    )
    assert any("revenue_2024" in issue for issue in issues)
    assert audits["revenue_2024"]["status"] == CitationStatus.DIVERGENT.value
    assert audits["revenue_2024"]["citation"] is None


def test_number_without_any_source_is_uncited():
    financial = {"revenue_2024": "R$ 50 milhões"}
    audit = audit_financial_field("revenue_2024", financial["revenue_2024"], [])

    assert audit.status == CitationStatus.UNCITED
    assert audit.citation is None

    issues, audits = validate_factual(
        {
            "financial_structured": financial,
            "financial_citations": [],
            "deal_id": "deal-1",
        }
    )
    assert any("sem citação" in issue for issue in issues)


def test_normalized_match_across_formats():
    """R$ 12,5 mi vs 12.500.000 na fonte deve casar."""
    financial = {"revenue_2024": "R$ 12,5 mi"}
    citations = [_citation("Receita anual de 12.500.000 reais conforme DRE.")]

    audit = audit_financial_field("revenue_2024", financial["revenue_2024"], citations)
    assert audit.status == CitationStatus.CITED


def test_legacy_flow_exempt_from_factual_qa():
    result = run_factual_qa(
        {
            "deal_id": "",
            "audit_mode": "legacy",
            "financial_structured": {"revenue_2024": "R$ 50 milhões"},
            "financial_citations": [],
            "ppt_path": "outputs/test.pptx",
        }
    )
    assert result["audit_mode"] == "legacy"
    assert result["qa_passed"] is True
    assert any("não auditável" in issue for issue in result["qa_issues"])


def test_field_citations_always_explicit_none_when_uncited():
    financial = {"revenue_2024": "R$ 50 milhões", "ebitda": "20% est."}
    audits = audit_financial_structured(financial, [])
    assert audits["revenue_2024"].citation is None
    assert audits["revenue_2024"].status == CitationStatus.UNCITED
    assert audits["ebitda"].status == CitationStatus.ESTIMATE
