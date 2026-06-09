"""Etapa 3 — jobs web persistidos em SQLAlchemy (sem Supabase)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.auth import create_access_token
from app.database import init_db
from app.main import JobStatus, _run_job, app


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


@pytest.fixture
def access_ok(monkeypatch):
    async def _ok(_phone):
        return True

    monkeypatch.setattr("app.main.check_access", _ok)
    monkeypatch.setattr("app.main.check_job_limit", _ok)


def test_job_status_reads_sqlalchemy_without_supabase(client, headers, access_ok, monkeypatch):
    monkeypatch.setattr("app.main.run_web_job_and_notify", lambda **kwargs: None)

    with patch("app.db.get_supabase", return_value=None):
        conv = client.post("/conversations", json={}, headers=headers).json()
        res = client.post(
            "/jobs/web",
            json={"message": "CIM da Nubank", "conversation_id": conv["id"]},
            headers=headers,
        )
    assert res.status_code == 202
    job_id = res.json()["id"]

    with patch("app.db.get_supabase", return_value=None):
        status = client.get(f"/jobs/{job_id}/status", headers=headers)
    assert status.status_code == 200
    body = status.json()
    assert body["id"] == job_id
    assert body["status"] == JobStatus.PENDING.value
    assert body["conversation_id"] == conv["id"]
    assert body["deal_id"]


def test_run_job_completes_artifact_and_conversation(client, headers, access_ok, tmp_path, monkeypatch):
    def fake_pipeline(job_id, company_name, document_type, client_id, **kwargs):
        ppt = tmp_path / "nubank_cim.pptx"
        ppt.write_bytes(b"fake-pptx")
        return {
            "ppt_path": str(ppt),
            "ppt_filename": "Nubank_CIM.pptx",
            "qa_passed": True,
            "qa_issues": [],
            "field_audits": {},
            "financial_citations": [],
            "artifact_type": "cim_pptx",
            "audit_mode": "full",
        }

    monkeypatch.setattr("app.main.run_pipeline", fake_pipeline)
    monkeypatch.setattr("app.main.run_web_job_and_notify", lambda **kwargs: None)

    with patch("app.db.get_supabase", return_value=None):
        conv = client.post("/conversations", json={}, headers=headers).json()
        job_res = client.post(
            "/jobs/web",
            json={"message": "CIM da Nubank", "conversation_id": conv["id"]},
            headers=headers,
        )
    assert job_res.status_code == 202
    job_id = job_res.json()["id"]
    deal_id = job_res.json()["deal_id"]

    _run_job(job_id, "Nubank", "CIM", "5511999999999")

    with patch("app.db.get_supabase", return_value=None):
        status = client.get(f"/jobs/{job_id}/status", headers=headers)
        assert status.status_code == 200
        assert status.json()["status"] == JobStatus.DONE.value
        assert status.json()["qa_passed"] is True

        deal = client.get(f"/deal/{deal_id}", headers=headers)
        assert deal.status_code == 200
        docs = deal.json()["documentos"]
        assert any(d.get("artifact_id") for d in docs)

        conv_detail = client.get(f"/conversations/{conv['id']}", headers=headers).json()
        assistant_msgs = [m for m in conv_detail["messages"] if m["role"] == "assistant"]
        assert any("pronto" in m["content"].lower() for m in assistant_msgs)

        artifact_id = next(d["artifact_id"] for d in docs if d.get("artifact_id"))
        download = client.get(
            f"/deals/{deal_id}/artifacts/{artifact_id}/download",
            headers=headers,
        )
        assert download.status_code == 200
        assert download.content == b"fake-pptx"


def test_run_job_error_finalizes_conversation(client, headers, access_ok, monkeypatch):
    monkeypatch.setattr("app.main.run_pipeline", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr("app.main.run_web_job_and_notify", lambda **kwargs: None)

    with patch("app.db.get_supabase", return_value=None):
        conv = client.post("/conversations", json={}, headers=headers).json()
        job_res = client.post(
            "/jobs/web",
            json={"message": "CIM da Nubank", "conversation_id": conv["id"]},
            headers=headers,
        )
    job_id = job_res.json()["id"]
    _run_job(job_id, "Nubank", "CIM", "5511999999999")

    with patch("app.db.get_supabase", return_value=None):
        status = client.get(f"/jobs/{job_id}/status", headers=headers)
        assert status.json()["status"] == JobStatus.ERROR.value

        conv_detail = client.get(f"/conversations/{conv['id']}", headers=headers).json()
        assert any("Erro" in m["content"] for m in conv_detail["messages"] if m["role"] == "assistant")
