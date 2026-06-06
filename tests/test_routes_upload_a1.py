"""Etapa A1 — rotas sem colisão; A2 — storage opcional."""

from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-routes-a1")
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
def auth_headers():
    token = create_access_token("5511999999999")
    return {"Authorization": f"Bearer {token}"}


def test_no_duplicate_route_methods():
    """Falha se existir mais de um handler para o mesmo (path, method)."""
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            key = (path, method)
            if key in seen:
                duplicates.append(key)
            seen.add(key)
    assert not duplicates, f"Rotas duplicadas: {duplicates}"


def test_upload_route_removed(client, auth_headers):
    """POST /upload foi removido — ingestão via /conversations/{id}/documents."""
    with patch("app.db.get_supabase", return_value=None):
        res = client.post(
            "/upload",
            headers=auth_headers,
            files={"file": ("teaser.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf")},
        )
    assert res.status_code == 404


def test_files_upload_returns_409_when_storage_off(client, auth_headers):
    with patch("app.db.get_supabase", return_value=None):
        res = client.post(
            "/files/upload",
            headers=auth_headers,
            files={"file": ("ref.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
    assert res.status_code == 409
    assert "não configurado" in res.json()["detail"].lower()


def test_files_list_ok_when_storage_off(client, auth_headers):
    with patch("app.db.get_supabase", return_value=None):
        res = client.get("/files", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["storage_enabled"] is False
    assert body["files"] == []


def test_me_includes_storage_enabled(client, auth_headers):
    with patch("app.db.get_supabase", return_value=None):
        res = client.get("/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["storage_enabled"] is False
    assert res.json()["phone"] == "5511999999999"
