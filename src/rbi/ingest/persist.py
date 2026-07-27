"""Incremental persistence for one ingested amendment.

Unlike db.sync (which rebuilds the whole graph), this inserts a single document and
its clauses without disturbing the rest — and is idempotent: re-ingesting the same
rbi_ref replaces the prior copy.
"""
from __future__ import annotations

from ..apply.models import ClauseVersion
from ..db.conn import connect, entity_id_map
from ..db.sync import DocBundle


def persist_one(doc: DocBundle, versions: list[ClauseVersion], *, database_url=None) -> dict:
    m = doc.meta
    ref = m.rbi_ref
    with connect(database_url) as conn:
        with conn.cursor() as cur:
            entity_ids = entity_id_map(cur)

            # idempotent re-ingest: drop any prior copy of this ref, children first.
            cur.execute("SELECT id FROM document WHERE rbi_ref = %s", (ref,))
            prior = cur.fetchone()
            if prior:
                pid = prior[0]
                ops_sub = "SELECT id FROM amendment_op WHERE amendment_doc_id = %s"
                # release clause references to this doc's ops, then remove clauses it created
                cur.execute(f"UPDATE clause SET superseded_by_op_id = NULL WHERE superseded_by_op_id IN ({ops_sub})", (pid,))
                cur.execute(f"DELETE FROM clause WHERE created_by_op_id IN ({ops_sub})", (pid,))
                cur.execute(f"DELETE FROM change_group_member WHERE amendment_op_id IN ({ops_sub})", (pid,))
                cur.execute("DELETE FROM amendment_op WHERE amendment_doc_id = %s", (pid,))
                cur.execute("DELETE FROM naive_chunk WHERE document_id = %s", (pid,))
                cur.execute("DELETE FROM document WHERE id = %s", (pid,))

            cur.execute(
                """INSERT INTO document
                   (rbi_ref, dor_ref, title, doc_type, md_family, entity_type_id,
                    issued_date, effective_date, source_url, sha256, raw_text)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (ref, m.dor_ref, m.title, m.doc_type, m.md_family,
                 entity_ids.get(m.entity_type_code), m.issued_date, m.effective_date,
                 doc.source_url, doc.sha256, doc.raw_text),
            )
            doc_id = cur.fetchone()[0]

            op_id_by_ref: dict[str, int] = {}
            for op in doc.operations:
                body = " ".join(nc.text for nc in op.new_clauses) or None
                cur.execute(
                    """INSERT INTO amendment_op
                       (amendment_doc_id, seq, operation, target_md_family,
                        target_entity_type, target_chapter, target_anchor,
                        section_heading, new_text, evidence_span, parse_confidence, status)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (doc_id, op.seq, op.operation, m.md_family,
                     entity_ids.get(m.entity_type_code), op.target_chapter, op.target_anchor,
                     op.section_heading, body, op.evidence_span, op.confidence, "parsed"),
                )
                op_id_by_ref[f"{ref}#seq{op.seq}"] = cur.fetchone()[0]

            clauses = 0
            for v in versions:
                eid = entity_ids.get(v.entity_type_code)
                if eid is None:
                    continue
                cur.execute(
                    """INSERT INTO clause
                       (md_family, entity_type_id, chapter, clause_number, sort_key,
                        text, valid_from, valid_to, created_by_op_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (v.md_family, eid, v.chapter, v.clause_number, v.sort_key, v.text,
                     v.valid_from, v.valid_to, op_id_by_ref.get(v.created_by_ref)),
                )
                clauses += 1

            # A substitute/omit revises a clause created by an EARLIER document, so it
            # lives in the DB and build_timeline (which sees only this doc) couldn't close
            # it. Close the previously-in-force version here: valid_to = this effective
            # date. For substitute the new version was just inserted (valid_from = eff),
            # and `valid_from < eff` excludes it, so only the prior version is closed.
            eff = m.effective_date or m.issued_date
            eid = entity_ids.get(m.entity_type_code)
            for op in doc.operations:
                if op.operation not in ("substitute", "omit"):
                    continue
                numbers = ([nc.clause_number for nc in op.new_clauses]
                           or op.clause_numbers
                           or ([op.target_anchor] if op.target_anchor else []))
                op_id = op_id_by_ref.get(f"{ref}#seq{op.seq}")
                for number in numbers:
                    cur.execute(
                        """UPDATE clause SET valid_to = %s, superseded_by_op_id = %s
                           WHERE md_family = %s AND entity_type_id = %s
                             AND clause_number = %s AND valid_to IS NULL AND valid_from < %s""",
                        (eff, op_id, m.md_family, eid, number, eff),
                    )
        conn.commit()

    return {"rbi_ref": ref, "operations": len(doc.operations), "clauses": clauses}
