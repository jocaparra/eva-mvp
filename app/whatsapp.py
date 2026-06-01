import os
import requests
from dotenv import load_dotenv
load_dotenv()

ZAPI_INSTANCE_ID = os.getenv("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_BASE_URL = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}"


def send_message(to: str, message: str):
    """Envia mensagem de texto simples via Z-API"""
    phone = to.replace("whatsapp:", "").replace("+", "").strip()

    url = f"{ZAPI_BASE_URL}/send-text"
    payload = {
        "phone": phone,
        "message": message,
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erro ao enviar mensagem Z-API: {e}")


def send_download_link(to: str, job_id: str, filename: str):
    """Envia link de download quando job terminar"""
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    link = f"{base_url}/jobs/{job_id}/download"
    send_message(
        to,
        f"✅ *{filename}* pronto!\n\n"
        f"📥 Baixe aqui:\n{link}\n\n"
        f"_Link válido por 24 horas._",
    )


def send_error(to: str, company: str):
    """Envia mensagem de erro"""
    send_message(
        to,
        f"❌ Erro ao gerar documento para *{company}*.\n"
        f"Tente novamente ou entre em contato com o suporte.",
    )
