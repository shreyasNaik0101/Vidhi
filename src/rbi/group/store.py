"""Postgres persistence for change groups (CLAUDE.md §5). Lazy psycopg import."""
from __future__ import annotations

from ..config import config
from .models import ChangeGroup


def write_change_groups(
    groups: list[ChangeGroup], *, database_url: str | None = None
) -> int:
    """Insert change_group + change_group_member rows. Returns group count."""
    import psycopg

    url = database_url or config.database_url
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for g in groups:
            cur.execute(
                "INSERT INTO change_group (label, issued_date, effective_date) "
                "VALUES (%s,%s,%s) RETURNING id",
                (g.label, g.issued_date, g.effective_date),
            )
            gid = cur.fetchone()[0]
            for m in g.members:
                # amendment_op_id is resolved elsewhere; store op_ref-derived link
                cur.execute(
                    "INSERT INTO change_group_member "
                    "(change_group_id, amendment_op_id, similarity) "
                    "VALUES (%s, (SELECT id FROM amendment_op WHERE "
                    " amendment_doc_id IN (SELECT id FROM document WHERE rbi_ref = %s) "
                    " LIMIT 1), %s)",
                    (gid, m.op_ref.split("#")[0], m.similarity),
                )
        conn.commit()
    return len(groups)
