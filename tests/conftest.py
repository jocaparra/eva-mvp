"""Fixtures compartilhadas — garante testes offline e embeddings determinísticos."""

from __future__ import annotations

import os

import pytest

# load_dotenv (via app.database) repõe GOOGLE_API_KEY do .env após imports dos testes;
# forçamos embeddings locais para não depender de rede/API em CI e sandbox.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ["GOOGLE_API_KEY"] = ""


@pytest.fixture(autouse=True)
def _deterministic_embeddings():
    os.environ["GOOGLE_API_KEY"] = ""
    yield
