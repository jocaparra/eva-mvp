"""Recuperação de contexto do data room por deal_id."""

from __future__ import annotations

from typing import List

from app.ingestion.index import RetrievedChunk, get_vector_store
from app.llm import truncate_text
from app.state import Citation


def retrieve_for_deal(deal_id: str, queries: List[str], k: int = 5) -> List[RetrievedChunk]:
    """Busca chunks no índice sempre filtrado por deal_id."""
    if not deal_id or not queries:
        return []

    from app.database import session_scope

    seen: set[str] = set()
    results: List[RetrievedChunk] = []

    with session_scope() as session:
        store = get_vector_store(session)
        for query in queries:
            for chunk in store.query(deal_id, query, k=k):
                if chunk.chunk_id in seen:
                    continue
                seen.add(chunk.chunk_id)
                results.append(chunk)

    return results


def chunks_to_citations(chunks: List[RetrievedChunk], *, source: str = "data_room") -> List[Citation]:
    """Converte chunks recuperados em citações rastreáveis."""
    citations: List[Citation] = []
    for chunk in chunks:
        citations.append(
            {
                "source_file": chunk.source_file,
                "page": chunk.page,
                "chunk_id": chunk.chunk_id,
                "quote": truncate_text(chunk.text, 400),
                "source": source,
            }
        )
    return citations


def format_dataroom_context(chunks: List[RetrievedChunk]) -> str:
    """Formata trechos do data room para prompt do LLM."""
    if not chunks:
        return ""
    parts: List[str] = []
    for chunk in chunks:
        parts.append(
            f"[Fonte: {chunk.source_file} | pág. {chunk.page} | chunk={chunk.chunk_id}]\n"
            f"{chunk.text}"
        )
    return "\n\n---\n\n".join(parts)
