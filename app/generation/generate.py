"""Ponto de entrada: generate(artifact_type, deal_state)."""

from __future__ import annotations

import os

from app.artifact_types import ARTIFACT_EXTENSION, SUPPORTED_ARTIFACT_TYPES
from app.generation.citations import collect_citations
from app.generation.content import build_document_sections
from app.generation.models import GenerationResult
from app.generation.renderers.cim_pptx import CimPptxRenderer
from app.generation.renderers.memo_docx import MemoDocxRenderer

_RENDERERS = {
    "cim_pptx": CimPptxRenderer(),
    "memo_docx": MemoDocxRenderer(),
}


class UnsupportedArtifactTypeError(ValueError):
    pass


def generate(artifact_type: str, deal_state: dict) -> GenerationResult:
    """
    Gera artefato a partir do deal_state.

    Conteúdo narrativo + citações são compartilhados; o renderer escolhe o formato.
    """
    if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        raise UnsupportedArtifactTypeError(
            f"artifact_type '{artifact_type}' não suportado. "
            f"Use: {', '.join(SUPPORTED_ARTIFACT_TYPES)}"
        )

    renderer = _RENDERERS[artifact_type]
    sections = build_document_sections(deal_state, artifact_type)
    citations = collect_citations(deal_state)

    job_id = deal_state.get("job_id", "unknown")
    ext = ARTIFACT_EXTENSION[artifact_type]
    output_path = os.path.join("outputs", f"{job_id}{ext}")

    return renderer.render(deal_state, sections, citations, output_path)
