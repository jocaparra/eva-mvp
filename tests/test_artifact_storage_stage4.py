"""Etapa 4 — object storage para artefatos (sobrevive a redeploy)."""

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
from app.main import JobStatus, _run_job, app
from app.repositories.deal_workspace import create_deal
from app.repositories.workspace_artifact import upsert_artifact_from_pipeline
from app.services.artifact_persistence import persist_pipeline_artifact
from app.storage.artifact_storage import get_artifact_storage, reset_artifact_storage


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def artifact_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_STORAGE", "local")
    monkeypatch.setenv("ARTIFACT_STORAGE_LOCAL_PATH", str(tmp_path / "artifacts"))
    reset_artifact_storage()
    yield tmp_path / "artifacts"
    reset_artifact_storage()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def headers():
    return {"Authorization": f"Bearer {create_access_token('5511999999999')}"}


def test_persist_pipeline_moves_file_to_storage_key(artifact_root):
    outputs = Path("outputs")
    outputs.mkdir(exist_ok=True)
    local = outputs / f"stage4-{uuid4().hex}.pptx"
    local.write_bytes(b"stored-by-stage4")
    deal_id = str(uuid4())
    job_id = str(uuid4())

    result = persist_pipeline_artifact(
        {"file_path": str(local), "ppt_filename": "deal.pptx"},
        deal_id=deal_id,
        job_id=job_id,
    )

    key = result["file_path"]
    assert key.startswith("artifacts/")
    assert get_artifact_storage().get_bytes(key) == b"stored-by-stage4"
    local.unlink()


def test_download_survives_redeploy_clearing_outputs(
    client, headers, artifact_root, db_session_factory
):
    from app.database import get_session_factory

    factory = get_session_factory()
    session = factory()
    try:
        deal = create_deal(session, company_name="Nubank", owner_phone="5511999999999")
        outputs = Path("outputs")
        outputs.mkdir(exist_ok=True)
        local = outputs / f"redeploy-{uuid4().hex}.pptx"
        local.write_bytes(b"survives-redeploy")

        persisted = persist_pipeline_artifact(
            {"file_path": str(local), "ppt_filename": "Nubank_CIM.pptx", "qa_passed": True},
            deal_id=str(deal.id),
            job_id=str(uuid4()),
        )
        artifact = upsert_artifact_from_pipeline(
            session,
            deal_id=deal.id,
            owner_phone="5511999999999",
            artifact_type="cim_pptx",
            pipeline_result=persisted,
        )
        session.commit()
        artifact_id = str(artifact.id)
        deal_id = str(deal.id)
    finally:
        session.close()

    local.unlink()
    assert not local.exists()

    res = client.get(
        f"/deals/{deal_id}/artifacts/{artifact_id}/download",
        headers=headers,
    )
    assert res.status_code == 200
    assert res.content == b"survives-redeploy"


@pytest.fixture
def db_session_factory():
    from app.database import get_session_factory

    return get_session_factory()


def test_run_job_persists_storage_key(client, headers, artifact_root, monkeypatch):
    async def _ok(_p):
        return True

    monkeypatch.setattr("app.main.check_access", _ok)
    monkeypatch.setattr("app.main.check_job_limit", _ok)
    monkeypatch.setattr("app.main.run_web_job_and_notify", lambda **kwargs: None)

    outputs = Path("outputs")
    outputs.mkdir(exist_ok=True)

    def fake_pipeline(job_id, company_name, document_type, client_id, **kwargs):
        local = outputs / f"{job_id}.pptx"
        local.write_bytes(b"pipeline-output")
        return {
            "ppt_path": str(local),
            "ppt_filename": "Nubank_CIM.pptx",
            "qa_passed": True,
            "qa_issues": [],
            "field_audits": {},
            "financial_citations": [],
            "artifact_type": "cim_pptx",
            "audit_mode": "full",
        }

    monkeypatch.setattr("app.main.run_pipeline", fake_pipeline)

    conv = client.post("/conversations", json={}, headers=headers).json()
    job_res = client.post(
        "/jobs/web",
        json={"message": "CIM da Nubank", "conversation_id": conv["id"]},
        headers=headers,
    )
    job_id = job_res.json()["id"]
    deal_id = job_res.json()["deal_id"]

    _run_job(job_id, "Nubank", "CIM", "5511999999999")

    local_ephemeral = outputs / f"{job_id}.pptx"
    if local_ephemeral.exists():
        local_ephemeral.unlink()

    status = client.get(f"/jobs/{job_id}/status", headers=headers)
    assert status.json()["status"] == JobStatus.DONE.value
    assert status.json()["ppt_path"].startswith("artifacts/")

    deal = client.get(f"/deal/{deal_id}", headers=headers).json()
    artifact_id = next(d["artifact_id"] for d in deal["documentos"] if d.get("artifact_id"))
    download = client.get(
        f"/deals/{deal_id}/artifacts/{artifact_id}/download",
        headers=headers,
    )
    assert download.status_code == 200
    assert download.content == b"pipeline-output"
