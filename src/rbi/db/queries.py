"""Read path: load clause versions from Postgres, resolve as-of in Python.

The coarse entity+family+clause filter runs in SQL (the query that defines the
product, PROJECT_SPEC.md §5); the temporal logic reuses the tested apply.resolve.resolve
so there is one source of truth for in-force / not-yet / no-provision.
"""
from __future__ import annotations

from datetime import date

from ..apply.models import ClauseVersion, Resolution
from ..apply.resolve import resolve as _resolve
from .conn import connect


def load_clause_versions(
    conn, *, md_family: str, entity_code: str, clause_number: str | None = None
) -> list[ClauseVersion]:
    sql = """
        SELECT c.md_family, e.code, c.clause_number, c.sort_key, c.chapter,
               c.text, c.valid_from, c.valid_to
        FROM clause c
        JOIN entity_type e ON e.id = c.entity_type_id
        WHERE c.md_family = %s AND e.code = %s
    """
    params: list = [md_family, entity_code]
    if clause_number is not None:
        sql += " AND c.clause_number = %s"
        params.append(clause_number)
    sql += " ORDER BY c.sort_key, c.valid_from"

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        ClauseVersion(
            md_family=r[0], entity_type_code=r[1], clause_number=r[2], sort_key=r[3],
            chapter=r[4], text=r[5], valid_from=r[6], valid_to=r[7],
        )
        for r in rows
    ]


def resolve_as_of(
    conn, *, md_family: str, entity_code: str, clause_number: str, as_of: date
) -> Resolution:
    versions = load_clause_versions(
        conn, md_family=md_family, entity_code=entity_code, clause_number=clause_number
    )
    return _resolve(
        versions, md_family=md_family, entity_type_code=entity_code,
        clause_number=clause_number, as_of=as_of,
    )
