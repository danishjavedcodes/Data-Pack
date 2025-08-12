from typing import Iterable, List
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from src.utils.db import Database

LABELS = ["photograph", "illustration", "vector"]

_model = None
_processor = None

def _load():
    global _model, _processor
    if _model is None:
        _model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")


def classify_types_for_images(db: Database, image_ids: Iterable[int]) -> List[int]:
    _load()
    updated: List[int] = []
    rows = db.get_images_by_ids(image_ids)
    for r in rows:
        try:
            p = r.get("processed_path") or r.get("local_path")
            img = Image.open(p).convert("RGB")
            inputs = _processor(text=LABELS, images=img, return_tensors="pt", padding=True)
            outputs = _model(**inputs)
            logits_per_image = outputs.logits_per_image  # (1, num_labels)
            probs = logits_per_image.softmax(dim=1)
            idx = int(probs.argmax().item())
            lbl = LABELS[idx]
            db.update_fields(r["id"], {"type": lbl})
            updated.append(r["id"])
        except Exception:
            continue
    return updated
