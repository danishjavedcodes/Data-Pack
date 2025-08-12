import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT,
  query TEXT,
  url TEXT UNIQUE,
  local_path TEXT,
  processed_path TEXT,
  width INTEGER,
  height INTEGER,
  format TEXT,
  hash TEXT,
  type TEXT,
  prompt TEXT,
  flags TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_images_type ON images(type);
CREATE INDEX IF NOT EXISTS idx_images_hash ON images(hash);
CREATE INDEX IF NOT EXISTS idx_images_processed ON images(processed_path);
"""

class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._init()

    def _init(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.commit()
            conn.close()

    def upsert_image(self, values: Dict[str, Any]) -> Optional[int]:
        keys = [
            "source", "query", "url", "local_path", "processed_path",
            "width", "height", "format", "hash", "type", "prompt", "flags"
        ]
        placeholders = ", ".join([":" + k for k in keys])
        update_clause = ", ".join([f"{k}=excluded.{k}" for k in keys if k not in ("url",)])
        sql = f"""
        INSERT INTO images ({', '.join(keys)})
        VALUES ({placeholders})
        ON CONFLICT(url) DO UPDATE SET {update_clause}
        """
        with self._conn() as conn:
            conn.execute(sql, {k: values.get(k) for k in keys})
            cur = conn.execute("SELECT id FROM images WHERE url=?", (values.get("url"),))
            row = cur.fetchone()
            return int(row[0]) if row else None

    def update_fields(self, image_id: int, fields: Dict[str, Any]) -> None:
        if not fields:
            return
        set_clause = ", ".join([f"{k}=?" for k in fields.keys()])
        sql = f"UPDATE images SET {set_clause} WHERE id=?"
        with self._conn() as conn:
            conn.execute(sql, [*fields.values(), image_id])

    def list_images(self, filter_text: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        where = ""
        params: List[Any] = []
        if filter_text:
            where = "WHERE (source LIKE ? OR query LIKE ?)"
            params.extend([f"%{filter_text}%", f"%{filter_text}%"])
        sql = f"SELECT * FROM images {where} ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def list_image_ids_missing_prompts(self) -> List[int]:
        with self._conn() as conn:
            cur = conn.execute("SELECT id FROM images WHERE processed_path IS NOT NULL AND (prompt IS NULL OR prompt='') ORDER BY id DESC")
            return [int(r[0]) for r in cur.fetchall()]

    def count_by_type(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute("SELECT COALESCE(type, 'unknown') as type, COUNT(*) as n FROM images GROUP BY COALESCE(type, 'unknown') ORDER BY n DESC")
            return [dict(r) for r in cur.fetchall()]

    def get_images_by_ids(self, image_ids: Iterable[int]) -> List[Dict[str, Any]]:
        ids = list(image_ids)
        if not ids:
            return []
        placeholders = ",".join(["?"] * len(ids))
        with self._conn() as conn:
            cur = conn.execute(f"SELECT * FROM images WHERE id IN ({placeholders})", ids)
            return [dict(r) for r in cur.fetchall()]

    def all_hashes(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute("SELECT id, hash FROM images WHERE hash IS NOT NULL")
            return [dict(r) for r in cur.fetchall()]
