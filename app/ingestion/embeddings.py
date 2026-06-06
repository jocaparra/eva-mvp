"""Geração de embeddings — Voyage AI (parceiro Anthropic) ou determinístico em testes."""

from __future__ import annotations

import hashlib
import os
from typing import List

EMBEDDING_DIM = 768
VOYAGE_EMBEDDING_MODEL = os.getenv("VOYAGE_EMBEDDING_MODEL", "voyage-3-lite")


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


def _fit_embedding(vector: List[float], dim: int = EMBEDDING_DIM) -> List[float]:
    if len(vector) == dim:
        return vector
    if len(vector) > dim:
        return vector[:dim]
    return vector + [0.0] * (dim - len(vector))


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Gera embeddings para uma lista de textos."""
    if not texts:
        return []

    voyage_key = os.getenv("VOYAGE_API_KEY", "").strip()
    if not voyage_key:
        return [_deterministic_embedding(t) for t in texts]

    import voyageai

    client = voyageai.Client(api_key=voyage_key)
    # Anthropic não expõe embeddings; Voyage é o parceiro recomendado (mesma dim compatível com pgvector).
    output_dim = min(EMBEDDING_DIM, 512)  # voyage-3-lite suporta 512 nativamente
    result = client.embed(
        texts,
        model=VOYAGE_EMBEDDING_MODEL,
        output_dimension=output_dim,
    )
    return [_fit_embedding(list(vec)) for vec in result.embeddings]
