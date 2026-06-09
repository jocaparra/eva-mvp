"""Testes da Etapa 5 — aprovação humana com audit por campo."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.auth import create_access_token
from app.citations.matching import CitationStatus, audit_financial_field, audits_to_serializable
from app.database import init_db
from app.main import app
from app.repositories.deal_workspace import create_deal
from app.repositories.workspace_artifact import (
    AlreadyApprovedError,
    ApprovalBlockedError,
    approve_artifact,
    upsert_artifact_from_pipeline,
)
from app.state import Citation


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def db_session() -> Session:
    from app.database import get_session_factory

    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()


def _citation(quote: str) -> Citation:
    return {
        "source_file": "dre.pdf",
        "page": 2,
        "chunk_id": "chunk-dre",
        "quote": quote,
        "source": "data_room",
    }


def _sample_field_audits(*, divergent: bool = False) -> dict:
    financial = {"revenue_2024": "R$ 50 milhões" if not divergent else "R$ 99 milhões"}
    citations = [_citation("Receita consolidada 2024: R$ 50 milhões.")]
    audits = audits_to_serializable(
        {"revenue_2024": audit_financial_field("revenue_2024", financial["revenue_2024"], citations)}
    )
    return audits


def _persist_artifact(db: Session, deal_id: UUID, phone: str, *, divergent: bool = False):
    audits = _sample_field_audits(divergent=divergent)
    ppt = Path("outputs/media-test.pptx")
    return upsert_artifact_from_pipeline(
        db,
        deal_id=deal_id,
        owner_phone=phone,
        artifact_type="CIM",
        pipeline_result={
            "ppt_path": str(ppt) if ppt.exists() else None,
            "field_audits": audits,
            "financial_citations": [_citation("Receita consolidada 2024: R$ 50 milhões.")],
            "qa_issues": [] if not divergent else ["Campo divergente"],
            "qa_passed": not divergent,
            "audit_mode": "full",
        },
    )


def test_review_exposes_field_audit_with_delta(db_session: Session):
    deal = create_deal(db_session, company_name="Alvo SA", owner_phone="5511999999999")
    artifact = _persist_artifact(db_session, deal.id, "5511999999999")

    token = create_access_token("5511999999999")
    with TestClient(app) as client:
        res = client.get(
            f"/deals/{deal.id}/artifacts/{artifact.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 200
    body = res.json()
    audit = body["field_audits"]["revenue_2024"]
    assert audit["status"] == CitationStatus.CITED.value
    assert audit["match_delta_pct"] is not None
    assert audit["match_delta_pct"] < 8.0
    assert body["blocking_issues"] == []


def test_divergent_exposes_source_candidates(db_session: Session):
    deal = create_deal(db_session, company_name="Alvo SA", owner_phone="5511999999999")
    artifact = _persist_artifact(db_session, deal.id, "5511999999999", divergent=True)

    token = create_access_token("5511999999999")
    with TestClient(app) as client:
        res = client.get(
            f"/deals/{deal.id}/artifacts/{artifact.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    audit = res.json()["field_audits"]["revenue_2024"]
    assert audit["status"] == CitationStatus.DIVERGENT.value
    assert audit["source_candidates"]
    assert audit["source_candidates"][0]["best_delta_pct"] is not None
    assert res.json()["blocking_issues"]


def test_approve_clean_artifact(db_session: Session):
    deal = create_deal(db_session, company_name="Alvo SA", owner_phone="5511999999999")
    artifact = _persist_artifact(db_session, deal.id, "5511999999999")

    token = create_access_token("5511999999999")
    with TestClient(app) as client:
        res = client.post(
            f"/deals/{deal.id}/artifacts/{artifact.id}/approve",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 201
    body = res.json()
    assert body["artifact"]["approved"] is True
    assert body["approval"]["approver_phone"] == "5511999999999"
    assert body["approval"]["artifact_version"] == 1
    assert body["approval"]["override"] is False


def test_approve_blocking_without_override_fails(db_session: Session):
    deal = create_deal(db_session, company_name="Alvo SA", owner_phone="5511999999999")
    artifact = _persist_artifact(db_session, deal.id, "5511999999999", divergent=True)

    token = create_access_token("5511999999999")
    with TestClient(app) as client:
        res = client.post(
            f"/deals/{deal.id}/artifacts/{artifact.id}/approve",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 422
    assert "blocking_issues" in res.json()["detail"]


def test_approve_with_override_records_reason(db_session: Session):
    deal = create_deal(db_session, company_name="Alvo SA", owner_phone="5511999999999")
    artifact = _persist_artifact(db_session, deal.id, "5511999999999", divergent=True)

    token = create_access_token("5511999999999")
    with TestClient(app) as client:
        res = client.post(
            f"/deals/{deal.id}/artifacts/{artifact.id}/approve",
            json={"override_reason": "Número correto conforme call com CFO."},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert res.status_code == 201
    approval = res.json()["approval"]
    assert approval["override"] is True
    assert approval["had_blocking_issues"] is True
    assert "CFO" in approval["override_reason"]


def test_regeneration_invalidates_approval(db_session: Session):
    deal = create_deal(db_session, company_name="Alvo SA", owner_phone="5511999999999")
    artifact = _persist_artifact(db_session, deal.id, "5511999999999")
    approve_artifact(
        db_session,
        deal_id=deal.id,
        artifact_id=artifact.id,
        owner_phone="5511999999999",
    )

    upsert_artifact_from_pipeline(
        db_session,
        deal_id=deal.id,
        owner_phone="5511999999999",
        artifact_type="CIM",
        pipeline_result={
            "ppt_path": None,
            "field_audits": _sample_field_audits(),
            "financial_citations": [],
            "qa_issues": [],
            "qa_passed": True,
            "audit_mode": "full",
        },
    )
    db_session.refresh(artifact)

    assert artifact.version == 2
    assert artifact.approved is False

    new_approval = approve_artifact(
        db_session,
        deal_id=deal.id,
        artifact_id=artifact.id,
        owner_phone="5511999999999",
    )
    assert new_approval.artifact_version == 2

    with pytest.raises(AlreadyApprovedError):
        approve_artifact(
            db_session,
            deal_id=deal.id,
            artifact_id=artifact.id,
            owner_phone="5511999999999",
        )


def test_approval_history_is_immutable(db_session: Session):
    deal = create_deal(db_session, company_name="Alvo SA", owner_phone="5511999999999")
    artifact = _persist_artifact(db_session, deal.id, "5511999999999", divergent=True)

    approve_artifact(
        db_session,
        deal_id=deal.id,
        artifact_id=artifact.id,
        owner_phone="5511999999999",
        override_reason="Aceito com ressalva.",
    )

    upsert_artifact_from_pipeline(
        db_session,
        deal_id=deal.id,
        owner_phone="5511999999999",
        artifact_type="CIM",
        pipeline_result={
            "ppt_path": None,
            "field_audits": _sample_field_audits(),
            "financial_citations": [],
            "qa_issues": [],
            "qa_passed": True,
            "audit_mode": "full",
        },
    )

    token = create_access_token("5511999999999")
    with TestClient(app) as client:
        res = client.get(
            f"/deals/{deal.id}/artifacts/{artifact.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    history = res.json()["approval_history"]
    assert len(history) == 1
    assert history[0]["artifact_version"] == 1
    assert history[0]["override"] is True
    assert res.json()["active_approval"] is None
