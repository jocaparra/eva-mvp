import os

import requests
from dotenv import load_dotenv

from app.log_utils import mask_phone

load_dotenv()

ZAPI_INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.getenv("ZAPI_CLIENT_TOKEN")

ZAPI_BASE_URL = (
    f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}"
    f"/token/{ZAPI_TOKEN}"
)


def send_message(to: str, message: str):
    phone = to.replace("whatsapp:", "").replace("+", "").strip()
    phone = phone.split("@")[0]

    url = f"{ZAPI_BASE_URL}/send-text"
    payload = {
        "phone": phone,
        "message": message,
    }
    headers = {
        "Content-Type": "application/json",
        "Client-Token": ZAPI_CLIENT_TOKEN,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"Z-API response: {response.status_code} phone={mask_phone(phone)}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erro Z-API phone={mask_phone(phone)}: {type(e).__name__}")


def send_download_link(to: str, job_id: str, filename: str):
    """Envia link de download quando job terminar"""
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    phone = to.replace("whatsapp:", "").replace("+", "").strip().split("@")[0]
    link = f"{base_url}/jobs/{job_id}/download?phone={phone}"
    send_message(
        to,
        f"✅ *{filename}* pronto!\n\n"
        f"📥 Baixe aqui:\n{link}\n\n"
        f"🔒 _Dados de entrada descartados após geração._",
    )


def send_error(to: str, company: str):
    """Envia mensagem de erro"""
    send_message(
        to,
        f"❌ Erro ao gerar documento para *{company}*.\n"
        f"Tente novamente ou entre em contato com o suporte.",
    )
