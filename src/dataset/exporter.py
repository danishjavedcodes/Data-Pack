from pathlib import Path
from typing import Dict, List
import json
import pandas as pd

from src.utils.db import Database

COLUMNS = [
    "image_path", "prompt", "type"
]


def _collect_rows(db: Database) -> List[dict]:
    rows = db.list_images(limit=1000000)
    out = []
    for r in rows:
        image_path = r.get("processed_path") or r.get("local_path")
        out.append({
            "image_path": image_path,
            "prompt": r.get("prompt") or "",
            "type": r.get("type") or "unknown",
        })
    return out


def export_dataset(db: Database, paths: Dict[str, Path], formats: List[str]) -> Dict[str, Path]:
    data = _collect_rows(db)
    df = pd.DataFrame(data, columns=COLUMNS)
    out_paths: Dict[str, Path] = {}

    final = paths["final"]
    final.mkdir(parents=True, exist_ok=True)

    if "csv" in formats:
        p = final / "dataset.csv"
        df.to_csv(p, index=False)
        out_paths["csv"] = p
    if "json" in formats:
        p = final / "dataset.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        out_paths["json"] = p
    if "parquet" in formats:
        p = final / "dataset.parquet"
        df.to_parquet(p, index=False)
        out_paths["parquet"] = p
    if "hdf5" in formats:
        p = final / "dataset.h5"
        df.to_hdf(p, key="images", mode="w")
        out_paths["hdf5"] = p

    return out_paths
