"""Testes da Etapa 2 — ingestão e vector store isolado por deal."""

from __future__ import annotations

import io
import os

import pytest
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.database import get_session_factory, init_db
from app.ingestion.chunking import chunk_segments
from app.ingestion.embeddings import embed_texts
from app.ingestion.index import get_vector_store
from app.ingestion.loaders import TextSegment, load_pdf
from app.repositories.deal_workspace import create_deal
from app.services.document_ingestion import ingest_deal_document


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


def _make_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_chunk_carries_source_file_and_page(db_session: Session):
    pdf = _make_pdf("Receita consolidada 2023: R$ 50 milhões na página 1.")
    segments = load_pdf(pdf)
    assert segments[0].page == 1

    deal = create_deal(db_session, company_name="Alvo SA", owner_phone="5511999999999")
    chunks = chunk_segments(
        segments,
        deal_id=str(deal.id),
        document_id="00000000-0000-0000-0000-000000000001",
        source_file="financials.pdf",
    )
    assert chunks
    assert chunks[0].source_file == "financials.pdf"
    assert chunks[0].page == 1
    assert "Receita" in chunks[0].text


def test_query_does_not_return_chunks_from_other_deal(db_session: Session):
    deal_a = create_deal(db_session, company_name="Empresa A", owner_phone="5511111111111")
    deal_b = create_deal(db_session, company_name="Empresa B", owner_phone="5522222222222")

    segments_a = [TextSegment(page=1, text="Receita operacional Empresa A cresceu 20%")]
    segments_b = [TextSegment(page=1, text="Margem EBITDA Empresa B estável em 35%")]

    chunks_a = chunk_segments(
        segments_a,
        deal_id=str(deal_a.id),
        document_id="00000000-0000-0000-0000-00000000000a",
        source_file="a.pdf",
    )
    chunks_b = chunk_segments(
        segments_b,
        deal_id=str(deal_b.id),
        document_id="00000000-0000-0000-0000-00000000000b",
        source_file="b.pdf",
    )

    store = get_vector_store(db_session)
    store.upsert(chunks_a, embed_texts([c.text for c in chunks_a]))
    store.upsert(chunks_b, embed_texts([c.text for c in chunks_b]))

    results = store.query(str(deal_a.id), "Receita operacional", k=5)
    assert results
    assert all(r.deal_id == str(deal_a.id) for r in results)
    assert all("Empresa A" in r.text for r in results)
    assert not any("Empresa B" in r.text for r in results)


def test_retrieve_for_deal_never_returns_other_deal_chunks(db_session: Session):
    """Garante isolamento via retrieve_for_deal (camada usada por research/financial)."""
    from app.ingestion.retrieval import retrieve_for_deal

    deal_a = create_deal(db_session, company_name="Empresa A", owner_phone="5511111111111")
    deal_b = create_deal(db_session, company_name="Empresa B", owner_phone="5522222222222")

    store = get_vector_store(db_session)
    chunks_a = chunk_segments(
        [TextSegment(page=1, text="Receita operacional Empresa A cresceu 20%")],
        deal_id=str(deal_a.id),
        document_id="00000000-0000-0000-0000-00000000000a",
        source_file="a.pdf",
    )
    chunks_b = chunk_segments(
        [TextSegment(page=1, text="Margem EBITDA Empresa B estável em 35%")],
        deal_id=str(deal_b.id),
        document_id="00000000-0000-0000-0000-00000000000b",
        source_file="b.pdf",
    )
    store.upsert(chunks_a, embed_texts([c.text for c in chunks_a]))
    store.upsert(chunks_b, embed_texts([c.text for c in chunks_b]))
    db_session.commit()

    results = retrieve_for_deal(str(deal_a.id), ["Receita operacional Empresa A"], k=5)
    assert results
    assert all(r.deal_id == str(deal_a.id) for r in results)
    assert not any("Empresa B" in r.text for r in results)


def test_ingest_deal_document_end_to_end(db_session: Session):
    deal = create_deal(db_session, company_name="Loggi", owner_phone="5511999999999")
    pdf = _make_pdf("Volume de entregas: 2 milhões/mês. Página 3 do data room.")

    document, chunk_count = ingest_deal_document(
        db_session,
        deal_id=deal.id,
        owner_phone="5511999999999",
        filename="operacoes.pdf",
        content=pdf,
        mime_type="application/pdf",
    )

    assert document.status == "indexed"
    assert chunk_count >= 1

    store = get_vector_store(db_session)
    hits = store.query(str(deal.id), "entregas volume", k=3)
    assert hits
    assert hits[0].source_file == "operacoes.pdf"
    assert hits[0].page == 1
