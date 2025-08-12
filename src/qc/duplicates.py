from typing import Dict, List

from src.utils.db import Database


def find_duplicates(db: Database) -> List[List[int]]:
    rows = db.all_hashes()
    groups: Dict[str, List[int]] = {}
    for r in rows:
        h = r.get("hash")
        if not h:
            continue
        groups.setdefault(h, []).append(int(r["id"]))
    return [ids for ids in groups.values() if len(ids) >= 2]
