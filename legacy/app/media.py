from pathlib import Path
from typing import Optional

import requests

USER_AGENT = "EVA/1.0"


def download_bytes(url: str, timeout: int = 60) -> Optional[bytes]:
    """Baixa arquivo binário (documentos, etc.)."""
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        if response.status_code != 200 or len(response.content) < 100:
            return None
        return response.content
    except Exception:
        return None


def download_file(url: str, path: Path, timeout: int = 5) -> bool:
    """Download a file safely. Returns True on success, False on any failure."""
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        )
        if response.status_code != 200 or len(response.content) < 200:
            return False

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(response.content)

        try:
            from PIL import Image
            from io import BytesIO

            with Image.open(BytesIO(response.content)) as img:
                img.verify()
        except Exception:
            return False

        return True
    except Exception:
        return False
