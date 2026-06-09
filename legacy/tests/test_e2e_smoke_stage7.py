"""Etapa 7 — smoke test end-to-end (offline, sem Supabase nem APIs externas).

Simula o roteiro manual:
  1. Login
  2. Conversa + upload PDF → chunks indexados
  3. Job CIM → conclui
  4. Revisão — citações apontam para o PDF; QA sem UNCITED bloqueante
  5. Download autenticado
  6. Aprovação
"""

from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-e2e")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["VOYAGE_API_KEY"] = ""

from app.auth import create_access_token
from app.citations.matching import CitationStatus, audit_financial_field, audits_to_serializable
from app.database import init_db
from app.main import JobStatus, _run_job, app
from app.storage.artifact_storage import reset_artifact_storage


COMPANY = "Loggi"
PDF_NAME = "loggi_dataroom.pdf"
PDF_TEXT = (
    "Loggi Transportes Ltda — DRE consolidada. "
    "Receita consolidada 2024: R$ 50 milhões."
)
REVENUE_VALUE = "R$ 50 milhões"


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def artifact_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_STORAGE", "local")
    monkeypatch.setenv("ARTIFACT_STORAGE_LOCAL_PATH", str(tmp_path / "artifacts"))
    reset_artifact_storage()
    yield
    reset_artifact_storage()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def access_ok(monkeypatch):
    async def _ok(_phone):
        return True

    monkeypatch.setattr("app.main.check_access", _ok)
    monkeypatch.setattr("app.main.check_job_limit", _ok)
    monkeypatch.setattr("app.main.run_web_job_and_notify", lambda **kwargs: None)


def _make_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _cited_audits(source_file: str) -> dict:
    citations = [
        {
            "source_file": source_file,
            "page": 1,
            "chunk_id": "chunk-loggi-revenue",
            "quote": "Receita consolidada 2024: R$ 50 milhões.",
            "source": "data_room",
        }
    ]
    audits = audits_to_serializable(
        {
            "revenue_2024": audit_financial_field(
                "revenue_2024", REVENUE_VALUE, citations
            )
        }
    )
    return audits, citations


def test_e2e_smoke_login_upload_job_review_download_approve(
    client, access_ok, artifact_root, tmp_path, monkeypatch
):
    """Fluxo completo web sem Supabase (pipeline mockado)."""
    phone = "5511999999999"

    # 1 — Login
    with patch("app.db.get_supabase", return_value=None):
        login = client.post("/auth/dev-login", json={"phone": phone})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2 — Conversa + upload PDF
    with patch("app.db.get_supabase", return_value=None):
        conv = client.post("/conversations", json={}, headers=headers)
        assert conv.status_code == 201
        conv_id = conv.json()["id"]

        pdf = _make_pdf(PDF_TEXT)
        upload = client.post(
            f"/conversations/{conv_id}/documents",
            headers=headers,
            files={"file": (PDF_NAME, io.BytesIO(pdf), "application/pdf")},
        )
    assert upload.status_code == 200, upload.text
    upload_body = upload.json()
    deal_id = upload_body["deal_id"]
    assert upload_body["chunk_count"] >= 1

    with patch("app.db.get_supabase", return_value=None):
        deal_ws = client.get(f"/deals/{deal_id}", headers=headers).json()
    assert any(d["source_file"] == PDF_NAME for d in deal_ws["documents"])

    # 3 — Job CIM
    field_audits, financial_citations = _cited_audits(PDF_NAME)

    def fake_pipeline(job_id, company_name, document_type, client_id, **kwargs):
        ppt = tmp_path / f"{job_id}.pptx"
        ppt.write_bytes(b"e2e-smoke-pptx")
        return {
            "ppt_path": str(ppt),
            "ppt_filename": f"{COMPANY}_CIM.pptx",
            "qa_passed": True,
            "qa_issues": [],
            "field_audits": field_audits,
            "financial_citations": financial_citations,
            "artifact_type": "cim_pptx",
            "audit_mode": "full",
        }

    monkeypatch.setattr("app.main.run_pipeline", fake_pipeline)

    with patch("app.db.get_supabase", return_value=None):
        job_res = client.post(
            "/jobs/web",
            json={"message": f"CIM da {COMPANY}", "conversation_id": conv_id},
            headers=headers,
        )
    assert job_res.status_code == 202
    job_id = job_res.json()["id"]
    assert job_res.json()["deal_id"] == deal_id

    _run_job(job_id, COMPANY, "CIM", phone)

    with patch("app.db.get_supabase", return_value=None):
        status = client.get(f"/jobs/{job_id}/status", headers=headers)
    assert status.json()["status"] == JobStatus.DONE.value

    # 4 — Revisão: citações → PDF; sem UNCITED bloqueante
    deal_detail = client.get(f"/deal/{deal_id}", headers=headers).json()
    artifact_id = next(
        d["artifact_id"] for d in deal_detail["documentos"] if d.get("artifact_id")
    )

    with patch("app.db.get_supabase", return_value=None):
        review = client.get(
            f"/deals/{deal_id}/artifacts/{artifact_id}",
            headers=headers,
        )
    assert review.status_code == 200
    review_body = review.json()
    assert review_body["qa_passed"] is True
    assert review_body["blocking_issues"] == []

    audit = review_body["field_audits"]["revenue_2024"]
    assert audit["status"] == CitationStatus.CITED.value
    assert audit["citation"]["source_file"] == PDF_NAME
    assert audit["match_delta_pct"] is not None
    assert audit["match_delta_pct"] < 8.0

    # 5 — Download autenticado
    with patch("app.db.get_supabase", return_value=None):
        download = client.get(
            f"/deals/{deal_id}/artifacts/{artifact_id}/download",
            headers=headers,
        )
    assert download.status_code == 200
    assert download.content == b"e2e-smoke-pptx"

    # 6 — Aprovação
    with patch("app.db.get_supabase", return_value=None):
        approved = client.post(
            f"/deals/{deal_id}/artifacts/{artifact_id}/approve",
            json={},
            headers=headers,
        )
    assert approved.status_code == 201
    assert approved.json()["artifact"]["approved"] is True
    assert approved.json()["approval"]["override"] is False

    with patch("app.db.get_supabase", return_value=None):
        conv_final = client.get(f"/conversations/{conv_id}", headers=headers).json()
    assert any(
        "pronto" in m["content"].lower()
        for m in conv_final["messages"]
        if m["role"] == "assistant"
    )

    with patch("app.db.get_supabase", return_value=None):
        deals_list = client.get("/deals", headers=headers).json()
    assert any(d["id"] == deal_id and d["has_ready_artifact"] for d in deals_list)
