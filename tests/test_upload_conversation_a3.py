"""Teste A3/A4 — upload no deal da conversa alimenta o índice."""

from __future__ import annotations

import io
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.auth import create_access_token
from app.database import get_session_factory, init_db
from app.ingestion.index import get_vector_store
from app.main import app


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


def _make_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def headers():
    return {"Authorization": f"Bearer {create_access_token('5511999999999')}"}


def test_conversation_upload_indexes_pdf(client, headers):
    conv = client.post("/conversations", json={}, headers=headers)
    assert conv.status_code == 201
    conv_id = conv.json()["id"]

    pdf = _make_pdf("Receita operacional Empresa Chat cresceu 20% no data room.")
    upload = client.post(
        f"/conversations/{conv_id}/documents",
        headers=headers,
        files={"file": ("teaser-chat.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    body = upload.json()
    assert body["chunk_count"] >= 1
    deal_id = body["deal_id"]

    deal = client.get(f"/deals/{deal_id}", headers=headers)
    assert deal.status_code == 200
    docs = deal.json()["documents"]
    assert any(d["source_file"] == "teaser-chat.pdf" for d in docs)

    factory = get_session_factory()
    session = factory()
    try:
        store = get_vector_store(session)
        hits = store.query(deal_id, "Receita operacional Empresa Chat", k=3)
        assert hits
        assert all(h.deal_id == deal_id for h in hits)
        assert any("Empresa Chat" in h.text for h in hits)
    finally:
        session.close()
