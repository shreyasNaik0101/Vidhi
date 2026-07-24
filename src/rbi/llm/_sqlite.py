"""Shared SQLite connection for the cache + ledger (both live in data/llm_cache.db)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import config


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path is not None else config.llm_cache_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn
