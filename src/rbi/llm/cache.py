"""Response cache (CLAUDE.md §7). Key = sha256(model + prompt + params).

Check before every call, no exceptions. A warm cache makes a pipeline re-run ~free.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ._sqlite import connect

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_cache (
    key        TEXT PRIMARY KEY,
    model      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    response   TEXT NOT NULL
);
"""


def cache_key(model: str, prompt: str, params: dict | None = None) -> str:
    payload = json.dumps(
        {"model": model, "prompt": prompt, "params": params or {}},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, path: Path | None = None):
        self._path = path
        with connect(self._path) as c:
            c.execute(_SCHEMA)

    def get(self, model: str, prompt: str, params: dict | None = None) -> str | None:
        key = cache_key(model, prompt, params)
        with connect(self._path) as c:
            row = c.execute(
                "SELECT response FROM llm_cache WHERE key = ?", (key,)
            ).fetchone()
        return row["response"] if row else None

    def put(
        self, model: str, prompt: str, response: str, params: dict | None = None
    ) -> None:
        key = cache_key(model, prompt, params)
        with connect(self._path) as c:
            c.execute(
                "INSERT OR REPLACE INTO llm_cache (key, model, created_at, response) "
                "VALUES (?,?,?,?)",
                (key, model, datetime.now(timezone.utc).isoformat(), response),
            )
