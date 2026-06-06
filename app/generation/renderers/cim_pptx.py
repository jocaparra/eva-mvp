"""Renderer CIM → PPTX."""

from __future__ import annotations

import os
from datetime import date

from app.artifact_types import ARTIFACT_EXTENSION, ARTIFACT_MIME
from app.generation.citations import CitationBundle
from app.generation.models import GenerationResult


class CimPptxRenderer:
    artifact_type = "cim_pptx"

    def render(
        self,
        deal_state: dict,
        sections: dict[str, str],
        citations: CitationBundle,
        output_path: str,
    ) -> GenerationResult:
        from app.generation.content import build_plain_content
        from app.generation.renderers._pptx_common import render_pptx

        company = deal_state.get("company_name", "empresa")
        doc_type = deal_state.get("document_type", "CIM")
        job_id = deal_state.get("job_id", "unknown")

        # Enriquece state para paths legados (template / Presenton)
        enriched = dict(deal_state)
        enriched["_generation_sections"] = sections
        enriched["_generation_plain"] = build_plain_content(deal_state, self.artifact_type)

        result_path, edit_url = render_pptx(enriched, output_path)
        filename = f"{company}_{doc_type}_{date.today()}{ARTIFACT_EXTENSION[self.artifact_type]}"

        gen = GenerationResult(
            artifact_type=self.artifact_type,
            file_path=result_path,
            file_filename=filename,
            mime_type=ARTIFACT_MIME[self.artifact_type],
            format="pptx",
        )
        if edit_url:
            deal_state["edit_url"] = edit_url
        return gen
