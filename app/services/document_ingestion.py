"""Orquestra ingestão: upload → parse → chunk → embed → index."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Tuple

from sqlalchemy.orm import Session

from app.ingestion.chunking import chunk_segments
from app.ingestion.embeddings import embed_texts
from app.ingestion.index import get_vector_store
from app.ingestion.loaders import is_ingestible, load_document
from app.models.deal_workspace import WorkspaceDocument
from app.repositories.deal_workspace import DealAccessDeniedError, DealNotFoundError, get_deal_for_owner

UPLOAD_ROOT = Path(
    os.getenv(
        "DEAL_UPLOAD_PATH",
        str(Path(__file__).resolve().parent.parent.parent / "uploads" / "deal_workspace"),
    )
)


def ingest_deal_document(
    session: Session,
    *,
    deal_id: uuid.UUID,
    owner_phone: str,
    filename: str,
    content: bytes,
    mime_type: str = "",
) -> Tuple[WorkspaceDocument, int]:
    """
    Ingere documento no data room do deal.
    Retorna (documento, quantidade de chunks indexados).
    """
    if not is_ingestible(filename, mime_type):
        raise ValueError(f"Tipo de arquivo não suportado: {filename}")

    try:
        get_deal_for_owner(session, deal_id, owner_phone)
    except DealNotFoundError:
        raise
    except DealAccessDeniedError:
        raise

    doc = WorkspaceDocument(
        deal_id=deal_id,
        source_file=filename,
        mime_type=mime_type or None,
        status="processing",
    )
    session.add(doc)
    session.flush()

    storage_dir = UPLOAD_ROOT / str(deal_id) / str(doc.id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / filename
    storage_path.write_bytes(content)
    doc.storage_path = str(storage_path)

    segments = load_document(content, filename, mime_type)
    chunks = chunk_segments(
        segments,
        deal_id=str(deal_id),
        document_id=str(doc.id),
        source_file=filename,
    )
    embeddings = embed_texts([c.text for c in chunks]) if chunks else []

    store = get_vector_store(session)
    store.upsert(chunks, embeddings)

    doc.status = "indexed" if chunks else "empty"
    session.flush()
    session.refresh(doc)
    return doc, len(chunks)
