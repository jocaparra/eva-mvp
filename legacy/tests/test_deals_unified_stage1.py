"""Etapa 1 — deals unificados em SQLAlchemy (sem Supabase)."""

from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.auth import create_access_token
from app.database import init_db
from app.main import app


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


def _make_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_list_deals_without_supabase(client, headers):
    with patch("app.db.get_supabase", return_value=None):
        res = client.get("/deals", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_upload_in_conversation_visible_in_deal_routes(client, headers):
    with patch("app.db.get_supabase", return_value=None):
        conv = client.post("/conversations", json={}, headers=headers)
        assert conv.status_code == 201
        conv_id = conv.json()["id"]

        pdf = _make_pdf("Receita Empresa Unificada 2024 no data room.")
        upload = client.post(
            f"/conversations/{conv_id}/documents",
            headers=headers,
            files={"file": ("dataroom.pdf", io.BytesIO(pdf), "application/pdf")},
        )
        assert upload.status_code == 200, upload.text
        deal_id = upload.json()["deal_id"]

        detail = client.get(f"/deal/{deal_id}", headers=headers)
        assert detail.status_code == 200
        body = detail.json()
        assert any(
            d.get("source_file") == "dataroom.pdf" or d.get("nome") == "dataroom.pdf"
            for d in body["documentos"]
        )

        listing = client.get("/deals", headers=headers)
        assert listing.status_code == 200
        deals = listing.json()
        match = next(d for d in deals if d["id"] == deal_id)
        assert match["document_count"] >= 1
        assert any(doc["source_file"] == "dataroom.pdf" for doc in match["documentos"])

        workspace = client.get(f"/deals/{deal_id}", headers=headers)
        assert workspace.status_code == 200
        assert len(workspace.json()["documents"]) >= 1
