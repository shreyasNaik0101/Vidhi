"""Postgres connection helper. Lazy psycopg import so non-DB code stays importable."""
from __future__ import annotations

from contextlib import contextmanager

from ..config import config


@contextmanager
def connect(database_url: str | None = None):
    import psycopg

    conn = psycopg.connect(database_url or config.database_url)
    try:
        yield conn
    finally:
        conn.close()


def entity_id_map(cur) -> dict[str, int]:
    cur.execute("SELECT code, id FROM entity_type")
    return {code: id_ for code, id_ in cur.fetchall()}
