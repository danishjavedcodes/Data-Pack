from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from PIL import Image, ImageEnhance
import imagehash

from .db import Database
from .watermark import remove_watermark_heuristic


def _enhance_image(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Brightness(img).enhance(1.05)
    img = ImageEnhance.Contrast(img).enhance(1.05)
    return img


def _standardize(img: Image.Image, target_size: Optional[Tuple[int, int]]) -> Image.Image:
    if target_size:
        img = img.resize(target_size, Image.Resampling.LANCZOS)
    return img


def preprocess_images(
    db: Database,
    image_ids: Iterable[int],
    target_size: Optional[Tuple[int, int]],
    target_format: str,
    enhance: bool,
    remove_watermark: bool,
    paths: dict,
) -> List[int]:
    processed_ids: List[int] = []
    for row in db.get_images_by_ids(image_ids):
        try:
            p = Path(row["local_path"]) if row.get("local_path") else None
            if not p or not p.exists():
                continue
            img = Image.open(p).convert("RGB")
            if enhance:
                img = _enhance_image(img)
            if remove_watermark:
                img = remove_watermark_heuristic(img)
            img = _standardize(img, target_size)

            out_ext = ".png" if target_format.upper() == "PNG" else ".jpg"
            out_path = Path(paths["processed"]) / (Path(p).stem + out_ext)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if target_format.upper() == "PNG":
                img.save(out_path, format="PNG")
            else:
                img.save(out_path, format="JPEG", quality=95)

            # compute hash on processed
            ahash = str(imagehash.average_hash(img))
            db.update_fields(row["id"], {
                "processed_path": str(out_path),
                "format": target_format.upper(),
                "width": img.width,
                "height": img.height,
                "hash": ahash,
            })
            processed_ids.append(row["id"])
        except Exception:
            continue
    return processed_ids
