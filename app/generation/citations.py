"""Camada compartilhada de citações — consumida por todos os renderers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from app.state import Citation


@dataclass(frozen=True)
class CitationBundle:
    """Citações deduplicadas prontas para injeção em qualquer formato."""

    citations: Tuple[Citation, ...]
    reference_lines: Tuple[str, ...]

    @property
    def has_citations(self) -> bool:
        return bool(self.citations)

    def references_heading(self) -> str:
        return "Referências"

    def references_body(self) -> str:
        return "\n".join(self.reference_lines)


def collect_citations(deal_state: dict) -> CitationBundle:
    """Agrega citações de research + financial, deduplica por chunk_id."""
    raw: List[Citation] = []
    raw.extend(deal_state.get("financial_citations") or [])
    raw.extend(deal_state.get("research_citations") or [])
    raw.extend(deal_state.get("retrieved_context") or [])

    seen: set[str] = set()
    citations: List[Citation] = []
    for citation in raw:
        if not citation:
            continue
        key = citation.get("chunk_id") or (
            f"{citation.get('source_file')}-{citation.get('page')}-{citation.get('source')}"
        )
        if key in seen:
            continue
        seen.add(key)
        citations.append(citation)

    lines: List[str] = []
    for idx, citation in enumerate(citations, start=1):
        source = citation.get("source") or "data_room"
        src_file = citation.get("source_file") or "—"
        page = citation.get("page") or "—"
        quote = (citation.get("quote") or "")[:200]
        external_tag = " [externa]" if source == "external" else ""
        lines.append(f"[{idx}] ({source}{external_tag}) {src_file}, pág. {page}: {quote}")

    return CitationBundle(citations=tuple(citations), reference_lines=tuple(lines))
