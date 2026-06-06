"""Fixtures compartilhadas — garante testes offline e embeddings determinísticos."""

from __future__ import annotations

import os

import pytest

# load_dotenv repõe chaves do .env após imports; forçamos modo offline em CI.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["VOYAGE_API_KEY"] = ""


@pytest.fixture(autouse=True)
def _offline_llm_and_embeddings():
    os.environ["ANTHROPIC_API_KEY"] = ""
    os.environ["VOYAGE_API_KEY"] = ""
    yield
