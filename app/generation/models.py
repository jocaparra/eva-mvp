"""Resultado padronizado de generate(artifact_type, deal_state)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationResult:
    artifact_type: str
    file_path: str
    file_filename: str
    mime_type: str
    format: str  # pptx | docx

    # Compatibilidade com JobState legado
    @property
    def ppt_path(self) -> str:
        return self.file_path if self.format == "pptx" else ""

    @property
    def ppt_filename(self) -> str:
        return self.file_filename if self.format == "pptx" else ""
