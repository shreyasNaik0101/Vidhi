"""Postgres integration — persist a timeline and resolve as-of against real SQL.

Skips when the database is unreachable, so the suite stays green without Docker.
Uses a hand-built timeline (no model) written through the same persist() path.
"""
from __future__ import annotations

from datetime import date

import pytest

from rbi.apply.build import build_timeline
from rbi.classify.rules import DocumentMeta
from rbi.db.conn import connect
from rbi.db.queries import resolve_as_of
from rbi.db.sync import DocBundle, persist
from rbi.group.build import group_ops
from rbi.group.models import OpRef
from rbi.parse.schema import NewClause, Operation

EFF = date(2026, 10, 1)
_68C = "RRB accrued interest text for 68C, SNFA."
_119C = "LAB accrued interest text for 119C, SNFA."


def _db_available() -> bool:
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not reachable")


def _bundle(entity, ref, clauses):
    meta = DocumentMeta(
        rbi_ref=ref, dor_ref=None, title=f"{entity} IRACP", doc_type="amendment",
        md_family="IRACP", entity_type_code=entity,
        issued_date=date(2026, 7, 16), effective_date=EFF,
    )
    op = Operation(
        seq=1, operation="insert", target_chapter="V", section_heading="B.",
        clause_numbers=list(clauses),
        new_clauses=[NewClause(clause_number=n, text=t) for n, t in clauses.items()],
        evidence_span="the following shall be inserted", confidence=1.0,
    )
    return DocBundle(meta=meta, operations=[op],
                     source_url=f"file://test/{ref}", sha256="0" * 64, raw_text="raw")


@pytest.fixture(scope="module")
def seeded_db():
    docs = [
        _bundle("RRB", "TEST/RRB", {"68C": _68C}),
        _bundle("LAB", "TEST/LAB", {"119C": _119C}),
    ]
    entries = [(d.meta, d.operations) for d in docs]
    versions = build_timeline(entries)
    ops = [OpRef(op_ref=f"{d.meta.rbi_ref}#seq1", entity_type_code=d.meta.entity_type_code,
                 md_family="IRACP", issued_date=date(2026, 7, 16), effective_date=EFF,
                 text=list(d.operations[0].new_clauses)[0].text,
                 clause_numbers=d.operations[0].clause_numbers) for d in docs]
    counts = persist(docs, versions, group_ops(ops))
    return counts


def test_persist_counts(seeded_db):
    assert seeded_db["documents"] == 2
    assert seeded_db["clauses"] == 2


def test_date_flip_against_real_postgres(seeded_db):
    with connect() as conn:
        before = resolve_as_of(conn, md_family="IRACP", entity_code="RRB",
                               clause_number="68C", as_of=date(2026, 9, 30))
        after = resolve_as_of(conn, md_family="IRACP", entity_code="RRB",
                              clause_number="68C", as_of=date(2026, 10, 2))
    assert before.status == "not_yet_in_force"
    assert after.status == "in_force"
    assert after.text == _68C


def test_entity_filter_in_sql(seeded_db):
    # RRB asked with LAB's clause number -> no rows -> no_provision
    with connect() as conn:
        r = resolve_as_of(conn, md_family="IRACP", entity_code="RRB",
                          clause_number="119C", as_of=date(2026, 10, 2))
    assert r.status == "no_provision"
