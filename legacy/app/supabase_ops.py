from pathlib import Path
from app.db import get_supabase


def get_or_create_firma(phone: str) -> str:
    client = get_supabase()
    res = client.table("firmas").select("id").eq("whatsapp", phone).execute()
    if res.data:
        return res.data[0]["id"]
    nova = client.table("firmas").insert({
        "nome": phone,
        "whatsapp": phone,
        "plano": "solo"
    }).execute()
    return nova.data[0]["id"]


def criar_deal(firma_id: str, nome: str) -> str:
    client = get_supabase()
    res = client.table("deals").insert({
        "firma_id": firma_id,
        "nome": nome,
        "status": "em_andamento"
    }).execute()
    return res.data[0]["id"]


def salvar_documento(deal_id: str, firma_id: str, tipo: str, ppt_path: str) -> str:
    client = get_supabase()
    file_bytes = Path(ppt_path).read_bytes()
    storage_path = f"{firma_id}/{deal_id}/{tipo}.pptx"
    client.storage.from_("documentos").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}
    )
    client.table("documentos").insert({
        "deal_id": deal_id,
        "tipo": tipo,
        "storage_path": storage_path
    }).execute()
    return storage_path


def get_signed_url(storage_path: str, expires_in: int = 86400) -> str:
    client = get_supabase()
    res = client.storage.from_("documentos").create_signed_url(storage_path, expires_in)
    return res["signedURL"]
