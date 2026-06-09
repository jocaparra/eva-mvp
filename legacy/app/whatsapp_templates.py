"""Recepção de templates .pptx via webhook Z-API."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from app.media import download_bytes
from app.utils.template import client_has_own_template, save_client_template
from app.whatsapp import send_message


def _is_template_file(filename: str, mime_type: str) -> bool:
    name = (filename or "").lower()
    mime = (mime_type or "").lower()
    if name.endswith(".pptx"):
        return True
    if "presentationml" in mime:
        return True
    if mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        return True
    return False


def extract_document_info(data: dict[str, Any]) -> Tuple[Optional[str], str, str]:
    """
    Extrai (url, filename, mime_type) de payloads Z-API.
    Suporta document, media, e campos planos.
    """
    doc = data.get("document") or {}
    if isinstance(doc, dict):
        url = (
            doc.get("documentUrl")
            or doc.get("url")
            or doc.get("mediaUrl")
            or doc.get("downloadUrl")
        )
        filename = doc.get("fileName") or doc.get("filename") or doc.get("title") or ""
        mime = doc.get("mimeType") or doc.get("mimetype") or ""
        if url:
            return url, str(filename), str(mime)

    media = data.get("media") or {}
    if isinstance(media, dict):
        url = media.get("url") or media.get("mediaUrl") or media.get("documentUrl")
        filename = media.get("fileName") or media.get("filename") or ""
        mime = media.get("mimeType") or media.get("mimetype") or ""
        if url:
            return url, str(filename), str(mime)

    url = data.get("mediaUrl") or data.get("documentUrl") or data.get("url")
    filename = data.get("fileName") or data.get("filename") or ""
    mime = data.get("mimeType") or data.get("mimetype") or ""
    if url:
        return str(url), str(filename), str(mime)

    return None, str(filename), str(mime)


def handle_whatsapp_template_upload(data: dict[str, Any], phone: str) -> Optional[dict]:
    """
    Se a mensagem contém .pptx/.docx, baixa e salva como template do cliente.
    Retorna dict de status ou None se não for template.
    """
    url, filename, mime = extract_document_info(data)
    if not url or not _is_template_file(filename, mime):
        return None

    had_template = client_has_own_template(phone)
    file_bytes = download_bytes(url)
    if not file_bytes:
        send_message(
            phone,
            "❌ Não consegui baixar o arquivo. Tente enviar o .pptx novamente.",
        )
        return {"status": "template_download_failed"}

    save_client_template(phone, file_bytes, filename or "template.pptx")

    if had_template:
        send_message(phone, "✅ Template atualizado!")
    else:
        send_message(
            phone,
            "✅ Template recebido! Todos os seus documentos usarão este layout.",
        )

    return {"status": "template_updated" if had_template else "template_saved", "phone": phone}
