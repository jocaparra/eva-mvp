"""Testes B1–B4 — conversas persistentes e isolamento."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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
def headers_a():
    return {"Authorization": f"Bearer {create_access_token('5511111111111')}"}


@pytest.fixture
def headers_b():
    return {"Authorization": f"Bearer {create_access_token('5522222222222')}"}


def test_create_and_list_conversations(client, headers_a):
    res = client.post("/conversations", json={}, headers=headers_a)
    assert res.status_code == 201
    conv_id = res.json()["id"]

    res2 = client.get("/conversations", headers=headers_a)
    assert res2.status_code == 200
    assert any(c["id"] == conv_id for c in res2.json())


def test_messages_persist_and_title_from_first_user_message(client, headers_a):
    create = client.post("/conversations", json={}, headers=headers_a)
    conv_id = create.json()["id"]

    client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "user", "content": "Gerar CIM da Loggi para análise de M&A"},
        headers=headers_a,
    )
    client.post(
        f"/conversations/{conv_id}/messages",
        json={"role": "assistant", "content": "Processando..."},
        headers=headers_a,
    )

    detail = client.get(f"/conversations/{conv_id}", headers=headers_a)
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["messages"]) == 2
    assert "Loggi" in body["title"]


def test_conversation_isolation_by_owner(client, headers_a, headers_b):
    create = client.post("/conversations", json={}, headers=headers_a)
    conv_id = create.json()["id"]
    forbidden = client.get(f"/conversations/{conv_id}", headers=headers_b)
    assert forbidden.status_code == 403


def test_web_job_links_conversation_and_deal(client, headers_a, monkeypatch):
    async def _ok(_p):
        return True

    monkeypatch.setattr("app.main.check_access", _ok)
    monkeypatch.setattr("app.main.check_job_limit", _ok)
    monkeypatch.setattr("app.main.run_web_job_and_notify", lambda **kwargs: None)

    conv = client.post("/conversations", json={}, headers=headers_a).json()
    job_res = client.post(
        "/jobs/web",
        json={"message": "CIM da Nubank", "conversation_id": conv["id"]},
        headers=headers_a,
    )
    assert job_res.status_code == 202
    body = job_res.json()
    assert body["conversation_id"] == conv["id"]
    assert body["deal_id"]

    detail = client.get(f"/conversations/{conv['id']}", headers=headers_a).json()
    assert len(detail["messages"]) >= 1
    assert detail["deal_id"] is not None
