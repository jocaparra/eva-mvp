"""Testes da Etapa 1 — persistência do deal workspace."""

from __future__ import annotations

import os
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-stage1-tests")

from app.auth import create_access_token
from app.database import get_session_factory, init_db
from app.main import app
from app.repositories.deal_workspace import create_deal, get_deal_for_owner, to_deal_state


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    yield


@pytest.fixture
def db_session() -> Session:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()


def test_create_and_read_deal_repository(db_session: Session):
    deal = create_deal(
        db_session,
        company_name="Loggi",
        owner_phone="5511999999999",
    )
    loaded = get_deal_for_owner(db_session, deal.id, "5511999999999")
    state = to_deal_state(loaded)

    assert state.company_name == "Loggi"
    assert state.status == "draft"
    assert state.documents == []
    assert state.artifacts == []


def test_deal_isolation_by_owner(db_session: Session):
    deal = create_deal(db_session, company_name="Nubank", owner_phone="5511111111111")
    from app.repositories.deal_workspace import DealAccessDeniedError

    with pytest.raises(DealAccessDeniedError):
        get_deal_for_owner(db_session, deal.id, "5522222222222")


def test_create_and_get_deal_api():
    init_db()
    token = create_access_token("5511999999999")
    with TestClient(app) as client:
        create_res = client.post(
            "/deals",
            json={"company_name": "Apple Brasil"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 201, create_res.text
        body = create_res.json()
        deal_id = body["deal_id"]
        assert body["company_name"] == "Apple Brasil"
        assert body["status"] == "draft"
        assert UUID(deal_id)

        get_res = client.get(
            f"/deals/{deal_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_res.status_code == 200
        assert get_res.json()["deal_id"] == deal_id
