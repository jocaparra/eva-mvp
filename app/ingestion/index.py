"""Vector store com pgvector (Postgres) e fallback SQLite para dev/testes."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.database import is_postgres_configured
from app.ingestion.chunking import Chunk
from app.ingestion.embeddings import EMBEDDING_DIM, embed_texts
from app.models.document_chunk import DocumentChunk


@dataclass(frozen=True)
class RetrievedChunk:
    """Chunk recuperado pela busca semântica."""

    chunk_id: str
    deal_id: str
    source_file: str
    page: int
    text: str
    score: float


class VectorStore(ABC):
    """Interface de indexação — evita lock-in de provedor."""

    @abstractmethod
    def upsert(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        """Insere ou substitui chunks de um documento."""

    @abstractmethod
    def query(self, deal_id: str, text: str, k: int = 5) -> List[RetrievedChunk]:
        """Busca semântica sempre filtrada por deal_id."""


class SqlAlchemyVectorStore(VectorStore):
    """Implementação SQLAlchemy com pgvector ou similaridade em Python (SQLite)."""

    def __init__(self, session: Session):
        self._session = session
        self._use_pgvector = is_postgres_configured()

    def upsert(self, chunks: List[Chunk], embeddings: List[List[float]]) -> None:
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("chunks e embeddings devem ter o mesmo tamanho")

        document_id = chunks[0].document_id
        self._session.query(DocumentChunk).filter(
            DocumentChunk.document_id == uuid.UUID(document_id)
        ).delete(synchronize_session=False)

        for chunk, embedding in zip(chunks, embeddings):
            row = DocumentChunk(
                id=uuid.UUID(chunk.chunk_id),
                deal_id=uuid.UUID(chunk.deal_id),
                document_id=uuid.UUID(chunk.document_id),
                source_file=chunk.source_file,
                page=chunk.page,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                embedding=embedding,
            )
            self._session.add(row)
        self._session.flush()

    def query(self, deal_id: str, text: str, k: int = 5) -> List[RetrievedChunk]:
        if not text.strip():
            return []

        query_embedding = embed_texts([text])[0]
        deal_uuid = uuid.UUID(deal_id)

        rows = (
            self._session.query(DocumentChunk)
            .filter(DocumentChunk.deal_id == deal_uuid)
            .all()
        )
        if not rows:
            return []

        if self._use_pgvector:
            return self._query_pgvector(deal_uuid, query_embedding, k)

        scored = []
        query_vec = np.array(query_embedding, dtype=float)
        for row in rows:
            vec = np.array(row.embedding or [], dtype=float)
            if vec.size == 0:
                continue
            score = float(np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec)))
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)

        return [
            RetrievedChunk(
                chunk_id=str(row.id),
                deal_id=str(row.deal_id),
                source_file=row.source_file,
                page=row.page,
                text=row.text,
                score=score,
            )
            for score, row in scored[:k]
        ]

    def _query_pgvector(self, deal_uuid: uuid.UUID, query_embedding: List[float], k: int) -> List[RetrievedChunk]:
        from sqlalchemy import select

        distance = DocumentChunk.embedding.cosine_distance(query_embedding)
        stmt = (
            select(DocumentChunk, distance.label("distance"))
            .where(DocumentChunk.deal_id == deal_uuid)
            .order_by(distance)
            .limit(k)
        )
        results = self._session.execute(stmt).all()
        retrieved: List[RetrievedChunk] = []
        for row, dist in results:
            score = 1.0 - float(dist)
            retrieved.append(
                RetrievedChunk(
                    chunk_id=str(row.id),
                    deal_id=str(row.deal_id),
                    source_file=row.source_file,
                    page=row.page,
                    text=row.text,
                    score=score,
                )
            )
        return retrieved


def get_vector_store(session: Session) -> VectorStore:
    """Factory do vector store."""
    return SqlAlchemyVectorStore(session)
