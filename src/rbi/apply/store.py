"""Postgres persistence for the clause timeline (CLAUDE.md §5, §8).

Optional: psycopg is imported lazily so the pure-domain core and its tests do not
require a database. Runs against config.database_url once `make db-up` is available.
The overlap invariant is asserted before any write.
"""
from __future__ import annotations

from ..config import config
from .build import assert_no_overlap
from .models import ClauseVersion


def _entity_id_map(cur) -> dict[str, int]:
    cur.execute("SELECT id, code FROM entity_type")
    return {code: id_ for id_, code in cur.fetchall()}


def write_clause_versions(
    versions: list[ClauseVersion], *, database_url: str | None = None
) -> int:
    """Insert clause versions. Returns the row count written. Idempotent per run."""
    import psycopg  # lazy — only needed when a DB is present

    assert_no_overlap(versions)
    url = database_url or config.database_url

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        entity_ids = _entity_id_map(cur)
        written = 0
        for v in versions:
            entity_id = entity_ids.get(v.entity_type_code)
            if entity_id is None:
                raise KeyError(f"unknown entity_type code {v.entity_type_code!r}")
            cur.execute(
                """
                INSERT INTO clause
                    (md_family, entity_type_id, chapter, clause_number, sort_key,
                     text, valid_from, valid_to)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    v.md_family,
                    entity_id,
                    v.chapter,
                    v.clause_number,
                    v.sort_key,
                    v.text,
                    v.valid_from,
                    v.valid_to,
                ),
            )
            written += 1
        conn.commit()
    return written
