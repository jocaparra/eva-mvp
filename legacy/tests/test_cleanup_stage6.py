"""Etapa 6 — limpeza: sem POST /upload, sem 503 por falta de Supabase."""

from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-stage6")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.auth import create_access_token
from app.database import get_engine, init_db
from app.main import app
from app.repositories.deal_workspace import create_deal
from app.services.document_ingestion import ingest_deal_document


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def headers():
    return {"Authorization": f"Bearer {create_access_token('5511999999999')}"}


def test_init_db_registers_all_models():
    inspector = inspect(get_engine())
    tables = set(inspector.get_table_names())
    expected = {
        "deal_workspaces",
        "workspace_documents",
        "workspace_artifacts",
        "document_chunks",
        "conversations",
        "messages",
        "generation_jobs",
    }
    assert expected.issubset(tables)


def test_upload_route_removed(client, headers):
    with patch("app.db.get_supabase", return_value=None):
        res = client.post(
            "/upload",
            headers=headers,
            files={"file": ("x.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
    assert res.status_code == 404


def _make_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_deal_download_no_503_without_supabase(client, headers):
    from app.database import get_session_factory

    factory = get_session_factory()
    session = factory()
    try:
        deal = create_deal(session, company_name="Alvo", owner_phone="5511999999999")
        pdf = _make_pdf("Conteudo data room para download legado.")
        doc, _ = ingest_deal_document(
            session,
            deal_id=deal.id,
            owner_phone="5511999999999",
            filename="dataroom.pdf",
            content=pdf,
            mime_type="application/pdf",
        )
        session.commit()
        deal_id = str(deal.id)
        doc_id = str(doc.id)
    finally:
        session.close()

    with patch("app.db.get_supabase", return_value=None):
        res = client.get(f"/deal/{deal_id}/download/{doc_id}", headers=headers)
    assert res.status_code == 200
    assert len(res.content) > 0


def test_no_product_route_503_without_supabase(client, headers):
    """Rotas de produto web não retornam 503 quando Supabase está ausente."""
    with patch("app.db.get_supabase", return_value=None):
        checks = [
            client.get("/deals", headers=headers),
            client.get("/me", headers=headers),
            client.get("/files", headers=headers),
            client.get("/conversations", headers=headers),
        ]
    for res in checks:
        assert res.status_code != 503, f"{res.request.url} returned 503"
