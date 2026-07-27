"""Write path: persist the pipeline graph to Postgres in dependency order.

document -> amendment_op -> clause -> change_group -> change_group_member.
A full TRUNCATE-and-reinsert keeps the stage idempotent and resumable (§13).
op_ref ('rbi_ref#seqN') is mapped to amendment_op.id in Python so change-group
members link correctly without brittle SQL subqueries.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..apply.build import assert_no_overlap, build_timeline
from ..apply.models import ClauseVersion
from ..classify.rules import DocumentMeta, classify_text
from ..config import CORPUS_DIR, SAMPLES_DIR, config
from ..extract.normalise import normalise
from ..extract.pdf import extract_pdf, sha256_file
from ..group.build import group_ops
from ..group.models import ChangeGroup, OpRef
from ..parse.runner import parse_document
from ..parse.schema import Operation
from .conn import connect, entity_id_map


@dataclass
class DocBundle:
    meta: DocumentMeta
    operations: list[Operation]
    source_url: str
    sha256: str
    raw_text: str


def persist(
    docs: list[DocBundle],
    versions: list[ClauseVersion],
    groups: list[ChangeGroup],
    *,
    database_url: str | None = None,
) -> dict[str, int]:
    assert_no_overlap(versions)
    with connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE change_group_member, change_group, clause, amendment_op, "
                "document RESTART IDENTITY CASCADE"
            )
            entity_ids = entity_id_map(cur)
            op_id_by_ref: dict[str, int] = {}

            for d in docs:
                m = d.meta
                cur.execute(
                    """INSERT INTO document
                       (rbi_ref, dor_ref, title, doc_type, md_family, entity_type_id,
                        issued_date, effective_date, source_url, sha256, raw_text)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (m.rbi_ref, m.dor_ref, m.title, m.doc_type, m.md_family,
                     entity_ids.get(m.entity_type_code), m.issued_date, m.effective_date,
                     d.source_url, d.sha256, d.raw_text),
                )
                doc_id = cur.fetchone()[0]
                for op in d.operations:
                    body = " ".join(nc.text for nc in op.new_clauses) or None
                    cur.execute(
                        """INSERT INTO amendment_op
                           (amendment_doc_id, seq, operation, target_md_family,
                            target_entity_type, target_chapter, target_anchor,
                            section_heading, new_text, evidence_span, parse_confidence,
                            status)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (doc_id, op.seq, op.operation, m.md_family,
                         entity_ids.get(m.entity_type_code), op.target_chapter,
                         op.target_anchor, op.section_heading, body, op.evidence_span,
                         op.confidence, "parsed"),
                    )
                    op_id_by_ref[f"{m.rbi_ref}#seq{op.seq}"] = cur.fetchone()[0]

            for v in versions:
                cur.execute(
                    """INSERT INTO clause
                       (md_family, entity_type_id, chapter, clause_number, sort_key,
                        text, valid_from, valid_to, created_by_op_id, superseded_by_op_id)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (v.md_family, entity_ids[v.entity_type_code], v.chapter,
                     v.clause_number, v.sort_key, v.text, v.valid_from, v.valid_to,
                     op_id_by_ref.get(v.created_by_ref),
                     op_id_by_ref.get(v.superseded_by_ref)),
                )

            for g in groups:
                cur.execute(
                    "INSERT INTO change_group (label, issued_date, effective_date) "
                    "VALUES (%s,%s,%s) RETURNING id",
                    (g.label, g.issued_date, g.effective_date),
                )
                gid = cur.fetchone()[0]
                for mem in g.members:
                    op_id = op_id_by_ref.get(mem.op_ref)
                    if op_id is None:
                        continue
                    cur.execute(
                        "INSERT INTO change_group_member "
                        "(change_group_id, amendment_op_id, similarity) VALUES (%s,%s,%s)",
                        (gid, op_id, mem.similarity),
                    )
        conn.commit()

    return {
        "documents": len(docs),
        "operations": sum(len(d.operations) for d in docs),
        "clauses": len(versions),
        "change_groups": len(groups),
    }


def sync_samples(*, model: str | None = None, database_url: str | None = None) -> dict[str, int]:
    """Run the full pipeline on the sample corpus and persist it."""
    model = model or config.ollama_model_parse
    docs: list[DocBundle] = []
    entries, ops = [], []

    def take(text: str, source_url: str, sha: str) -> None:
        meta = classify_text(text)
        result = parse_document(text, model=model)
        docs.append(DocBundle(meta=meta, operations=result.operations,
                              source_url=source_url, sha256=sha, raw_text=text))
        entries.append((meta, result.operations))
        for op in result.operations:
            if op.operation == "insert":
                ops.append(OpRef(
                    op_ref=f"{meta.rbi_ref}#seq{op.seq}", entity_type_code=meta.entity_type_code,
                    md_family=meta.md_family, issued_date=meta.issued_date,
                    effective_date=meta.effective_date,
                    text=" ".join(nc.text for nc in op.new_clauses),
                    clause_numbers=op.clause_numbers))

    # the two real PDFs
    for p in sorted(Path(SAMPLES_DIR).glob("*.pdf")):
        take(normalise(extract_pdf(p)), f"file://data/samples/{p.name}", sha256_file(p))
    # synthetic text amendments (substitute, extra entities) — see data/corpus/README
    for p in sorted(Path(CORPUS_DIR).glob("*.txt")):
        raw = p.read_text(encoding="utf-8")
        take(normalise(raw), f"file://data/corpus/{p.name}",
             hashlib.sha256(raw.encode("utf-8")).hexdigest())

    # build_timeline sees ALL documents in effective-date order, so substitute/omit
    # correctly close prior versions (that's how 68C gets two versions).
    versions = build_timeline(entries)
    groups = group_ops(ops)
    return persist(docs, versions, groups, database_url=database_url)
