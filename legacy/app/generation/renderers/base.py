"""Renderers por formato — consomem deal_state + conteúdo + citações compartilhados."""

from __future__ import annotations

from typing import Protocol

from app.generation.citations import CitationBundle
from app.generation.models import GenerationResult


class ArtifactRenderer(Protocol):
    artifact_type: str

    def render(
        self,
        deal_state: dict,
        sections: dict[str, str],
        citations: CitationBundle,
        output_path: str,
    ) -> GenerationResult:
        ...
