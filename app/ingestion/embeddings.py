"""Geração de embeddings — abstração sobre provedor (Gemini por padrão)."""

from __future__ import annotations

import hashlib
import os
from typing import List

EMBEDDING_DIM = 768
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/text-embedding-004")


def _deterministic_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """Embedding determinístico para testes locais sem API key."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: List[float] = []
    seed = int.from_bytes(digest[:8], "big")
    for i in range(dim):
        seed = (seed * 1103515245 + 12345 + i) & 0x7FFFFFFF
        values.append((seed / 0x7FFFFFFF) * 2 - 1)
    norm = sum(v * v for v in values) ** 0.5 or 1.0
    return [v / norm for v in values]


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Gera embeddings para uma lista de textos."""
    if not texts:
        return []

    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        return [_deterministic_embedding(t) for t in texts]

    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    model = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
    )
    return model.embed_documents(texts)
