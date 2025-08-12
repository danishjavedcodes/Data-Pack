import hashlib
import time
from pathlib import Path
from typing import Dict, Optional

import requests
from PIL import Image
from io import BytesIO

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def safe_filename_from_url(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"img_{digest}"


def download_image(url: str, dest_dir: Path, timeout: int = 15) -> Optional[Dict]:
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code != 200 or not resp.content:
            return None
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        name = safe_filename_from_url(url)
        out_path = dest_dir / f"{name}.jpg"
        dest_dir.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="JPEG", quality=95)
        return {
            "local_path": str(out_path),
            "width": img.width,
            "height": img.height,
            "format": "JPEG",
        }
    except Exception:
        return None


def rate_limited_sleep(rpm: int) -> None:
    if rpm <= 0:
        return
    delay = 60.0 / float(rpm)
    time.sleep(delay)
