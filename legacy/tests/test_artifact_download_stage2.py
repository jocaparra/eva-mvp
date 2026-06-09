"""Etapa 2 — download autenticado de artefatos via SQLAlchemy."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.auth import create_access_token
from app.database import init_db
from app.main import app
from app.repositories.deal_workspace import create_deal
from app.repositories.workspace_artifact import upsert_artifact_from_pipeline


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


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


@pytest.fixture
def owner_headers():
    return {"Authorization": f"Bearer {create_access_token('5511999999999')}"}


@pytest.fixture
def other_headers():
    return {"Authorization": f"Bearer {create_access_token('5511888888888')}"}


def _artifact_with_file(db: Session, ppt: Path):
    deal = create_deal(db, company_name="Nubank", owner_phone="5511999999999")
    artifact = upsert_artifact_from_pipeline(
        db,
        deal_id=deal.id,
        owner_phone="5511999999999",
        artifact_type="cim_pptx",
        pipeline_result={
            "file_path": str(ppt),
            "field_audits": {},
            "financial_citations": [],
            "qa_issues": [],
            "qa_passed": True,
            "audit_mode": "full",
        },
    )
    return deal, artifact


def test_download_artifact_with_bearer_token(client, db_session, owner_headers, tmp_path):
    ppt = tmp_path / "nubank_cim.pptx"
    ppt.write_bytes(b"fake-pptx-content")
    deal, artifact = _artifact_with_file(db_session, ppt)

    res = client.get(
        f"/deals/{deal.id}/artifacts/{artifact.id}/download",
        headers=owner_headers,
    )
    assert res.status_code == 200
    assert res.content == b"fake-pptx-content"
    assert "nubank_cim.pptx" in res.headers.get("content-disposition", "")


def test_download_artifact_with_query_token(client, db_session, tmp_path):
    ppt = tmp_path / "memo.docx"
    ppt.write_bytes(b"fake-docx")
    deal, artifact = _artifact_with_file(db_session, ppt)
    token = create_access_token("5511999999999")

    res = client.get(
        f"/deals/{deal.id}/artifacts/{artifact.id}/download?token={token}",
    )
    assert res.status_code == 200
    assert res.content == b"fake-docx"


def test_download_artifact_requires_auth(client, db_session, tmp_path):
    ppt = tmp_path / "nubank_cim.pptx"
    ppt.write_bytes(b"x")
    deal, artifact = _artifact_with_file(db_session, ppt)

    res = client.get(f"/deals/{deal.id}/artifacts/{artifact.id}/download")
    assert res.status_code == 401


def test_download_artifact_denies_other_owner(client, db_session, other_headers, tmp_path):
    ppt = tmp_path / "nubank_cim.pptx"
    ppt.write_bytes(b"x")
    deal, artifact = _artifact_with_file(db_session, ppt)

    res = client.get(
        f"/deals/{deal.id}/artifacts/{artifact.id}/download",
        headers=other_headers,
    )
    assert res.status_code == 403


def test_download_artifact_missing_file(client, db_session, owner_headers):
    deal = create_deal(db_session, company_name="Alvo", owner_phone="5511999999999")
    artifact = upsert_artifact_from_pipeline(
        db_session,
        deal_id=deal.id,
        owner_phone="5511999999999",
        artifact_type="cim_pptx",
        pipeline_result={
            "file_path": f"/tmp/missing-{uuid4()}.pptx",
            "field_audits": {},
            "qa_issues": [],
            "qa_passed": True,
        },
    )

    res = client.get(
        f"/deals/{deal.id}/artifacts/{artifact.id}/download",
        headers=owner_headers,
    )
    assert res.status_code == 404
