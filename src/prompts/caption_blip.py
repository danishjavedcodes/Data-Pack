from typing import Iterable, List
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor

from src.utils.db import Database

_model = None
_processor = None

def _load():
    global _model, _processor
    if _model is None:
        _model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        _processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")


def generate_captions_for_images(db: Database, image_ids: Iterable[int], batch_size: int = 8) -> List[int]:
    _load()
    rows = db.get_images_by_ids(image_ids)
    updated: List[int] = []
    batch_imgs: List[Image.Image] = []
    batch_rows = []

    def flush_batch():
        nonlocal updated, batch_imgs, batch_rows
        if not batch_rows:
            return
        inputs = _processor(images=batch_imgs, return_tensors="pt")
        out = _model.generate(**inputs, max_new_tokens=40)
        captions = _processor.batch_decode(out, skip_special_tokens=True)
        for r, cap in zip(batch_rows, captions):
            db.update_fields(r["id"], {"prompt": cap.strip()})
            updated.append(r["id"])
        batch_imgs = []
        batch_rows = []

    for r in rows:
        try:
            p = r.get("processed_path") or r.get("local_path")
            img = Image.open(p).convert("RGB")
            batch_imgs.append(img)
            batch_rows.append(r)
            if len(batch_imgs) >= batch_size:
                flush_batch()
        except Exception:
            continue
    flush_batch()
    return updated
