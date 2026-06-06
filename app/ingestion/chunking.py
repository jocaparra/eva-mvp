"""Chunking com overlap; cada chunk carrega metadados de fonte."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List

from app.ingestion.loaders import TextSegment

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


@dataclass(frozen=True)
class Chunk:
    """Chunk indexável com rastreabilidade à fonte."""

    deal_id: str
    document_id: str
    source_file: str
    page: int
    chunk_id: str
    chunk_index: int
    text: str


def _split_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def chunk_segments(
    segments: List[TextSegment],
    *,
    deal_id: str,
    document_id: str,
    source_file: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Chunk]:
    """Gera chunks a partir de segmentos preservando page/source_file."""
    result: List[Chunk] = []
    chunk_index = 0
    for segment in segments:
        for piece in _split_text(segment.text, chunk_size, overlap):
            result.append(
                Chunk(
                    deal_id=deal_id,
                    document_id=document_id,
                    source_file=source_file,
                    page=segment.page,
                    chunk_id=str(uuid.uuid4()),
                    chunk_index=chunk_index,
                    text=piece,
                )
            )
            chunk_index += 1
    return result
