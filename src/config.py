from pathlib import Path
from typing import Dict

BASE = Path(__file__).resolve().parent.parent

def get_paths() -> Dict[str, Path]:
    data_dir = BASE / "data"
    return {
        "base": BASE,
        "data": data_dir,
        "raw": data_dir / "raw",
        "processed": data_dir / "processed",
        "final": data_dir / "final",
        "db_file": data_dir / "metadata.db",
    }

def ensure_directories() -> None:
    paths = get_paths()
    for key in ["data", "raw", "processed", "final"]:
        paths[key].mkdir(parents=True, exist_ok=True)
