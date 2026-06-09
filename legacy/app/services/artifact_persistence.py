"""Persistência de artefatos do pipeline no object storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.storage.artifact_storage import (
    artifact_storage_key,
    get_artifact_storage,
    guess_content_type,
)


def persist_pipeline_artifact(
    result: dict[str, Any],
    *,
    deal_id: str,
    job_id: str,
) -> dict[str, Any]:
    """
    Envia o arquivo gerado (outputs/) para o storage e substitui file_path/ppt_path pela chave.
    """
    local_path = result.get("file_path") or result.get("ppt_path")
    if not local_path:
        return result

    path = Path(local_path)
    if not path.is_file():
        return result

    filename = result.get("ppt_filename") or path.name
    key = artifact_storage_key(deal_id=deal_id, job_id=job_id, filename=filename)
    data = path.read_bytes()
    storage = get_artifact_storage()
    storage_key = storage.store(
        key=key,
        data=data,
        content_type=guess_content_type(filename),
    )

    updated = dict(result)
    updated["file_path"] = storage_key
    updated["ppt_path"] = storage_key
    return updated
