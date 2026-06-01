import os

from dotenv import load_dotenv

load_dotenv()


def create_checkout_session(phone: str) -> str:
    """Retorna URL de checkout (Stripe ou página de assinatura)."""
    base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
    checkout_url = os.getenv("STRIPE_CHECKOUT_URL")
    if checkout_url:
        return f"{checkout_url}?phone={phone}"
    return f"{base_url}/subscribe?phone={phone}"
