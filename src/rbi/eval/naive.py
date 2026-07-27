"""Baseline A — naive RAG (PROJECT_SPEC.md §9).

Every document chunked into ONE pgvector index. Retrieval is pure vector
similarity: no entity filter, no date filter. This is what a normal project
builds — and, on the near-identical RRB/LAB texts, it is what returns the wrong
entity's clause and text that is not yet in force. That contrast is the point.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..group.embed import DEFAULT_EMBED_MODEL, embed_text
from .golden import GoldenQuestion
from .metrics import Prediction

CHUNK_WORDS = 45
OVERLAP = 12

# nomic-embed models expect task prefixes.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


def chunk_text(text: str, size: int = CHUNK_WORDS, overlap: int = OVERLAP) -> list[str]:
    words = text.split()
    if len(words) <= size:
        return [" ".join(words)] if words else []
    step = max(1, size - overlap)
    out = []
    for start in range(0, len(words), step):
        piece = words[start : start + size]
        if piece:
            out.append(" ".join(piece))
        if start + size >= len(words):
            break
    return out


def _vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def build_index(conn, *, model: str = DEFAULT_EMBED_MODEL) -> int:
    """(Re)build naive_chunk from every document's raw_text. Returns chunk count."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT d.id, e.code, d.md_family, d.effective_date, d.issued_date, d.raw_text
               FROM document d LEFT JOIN entity_type e ON e.id = d.entity_type_id"""
        )
        docs = cur.fetchall()

    # detect embedding dimension from a probe
    dim = len(embed_text(DOC_PREFIX + "probe", model=model))

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS naive_chunk")
        cur.execute(
            f"""CREATE TABLE naive_chunk (
                    id SERIAL PRIMARY KEY,
                    document_id INT REFERENCES document(id),
                    entity_code TEXT,
                    md_family TEXT,
                    effective_date DATE,
                    issued_date DATE,
                    chunk_text TEXT NOT NULL,
                    embedding vector({dim})
                )"""
        )
        n = 0
        for doc_id, code, family, eff, issued, raw in docs:
            for chunk in chunk_text(raw):
                vec = embed_text(DOC_PREFIX + chunk, model=model)
                cur.execute(
                    """INSERT INTO naive_chunk
                       (document_id, entity_code, md_family, effective_date,
                        issued_date, chunk_text, embedding)
                       VALUES (%s,%s,%s,%s,%s,%s,%s::vector)""",
                    (doc_id, code, family, eff, issued, chunk, _vec_literal(vec)),
                )
                n += 1
    conn.commit()
    return n


@dataclass
class NaiveRAG:
    """Answers by nearest chunk only — ignores entity, family, and as_of entirely."""
    conn: object
    model: str = DEFAULT_EMBED_MODEL

    def answer(self, q: GoldenQuestion) -> Prediction:
        qvec = embed_text(QUERY_PREFIX + q.question, model=self.model)
        with self.conn.cursor() as cur:  # type: ignore[attr-defined]
            cur.execute(
                """SELECT entity_code, effective_date, chunk_text
                   FROM naive_chunk ORDER BY embedding <=> %s::vector LIMIT 1""",
                (_vec_literal(qvec),),
            )
            row = cur.fetchone()
        if row is None:
            return Prediction(status="no_provision", note="empty index")
        entity_code, effective_date, chunk = row
        # Naive RAG cannot abstain: it always returns the nearest text as the answer.
        return Prediction(
            status="in_force",
            text=chunk,
            answer_entity=entity_code,
            answer_valid_from=effective_date,
            answer_valid_to=None,
        )
