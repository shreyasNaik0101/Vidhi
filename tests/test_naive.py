"""Baseline A — chunking, the generalized error metrics, and a live index smoke test."""
from __future__ import annotations

from datetime import date

import httpx
import pytest

from rbi.config import config
from rbi.eval.golden import GoldenQuestion
from rbi.eval.metrics import Prediction, is_entity_error, is_temporal_error
from rbi.eval.naive import chunk_text


# --- chunking (deterministic) ---
def test_short_text_is_one_chunk():
    assert chunk_text("a b c", size=45) == ["a b c"]


def test_empty_text_no_chunks():
    assert chunk_text("   ") == []


def test_long_text_chunks_overlap_and_cover():
    words = [f"w{i}" for i in range(100)]
    chunks = chunk_text(" ".join(words), size=20, overlap=5)
    assert len(chunks) > 1
    # every word appears in at least one chunk
    seen = set()
    for c in chunks:
        seen.update(c.split())
    assert seen == set(words)
    # consecutive chunks overlap
    first, second = chunks[0].split(), chunks[1].split()
    assert set(first) & set(second)


# --- generalized error detection ---
def _q(entity="RRB", as_of=date(2026, 10, 2), category="lookup"):
    return GoldenQuestion(id="x", category=category, question="?", entity_type=entity,
                          clause="68C", as_of=as_of, expected_status="in_force")


def test_entity_error_when_answer_from_other_entity():
    assert is_entity_error(_q("RRB"), Prediction(status="in_force", text="t", answer_entity="LAB"))
    assert not is_entity_error(_q("RRB"), Prediction(status="in_force", text="t", answer_entity="RRB"))


def test_no_entity_error_when_abstaining():
    assert not is_entity_error(_q("RRB"), Prediction(status="no_provision"))


def test_temporal_error_when_answer_not_yet_in_force():
    p = Prediction(status="in_force", text="t", answer_entity="RRB",
                   answer_valid_from=date(2026, 10, 1))
    assert is_temporal_error(_q("RRB", as_of=date(2026, 9, 30)), p)      # before effective
    assert not is_temporal_error(_q("RRB", as_of=date(2026, 10, 2)), p)  # after effective


def test_no_temporal_error_when_abstaining():
    assert not is_temporal_error(_q(as_of=date(2026, 9, 30)), Prediction(status="not_yet_in_force"))


# --- live: seed a doc, build the index, answer (self-contained; runs on the test DB) ---
def _db_reachable() -> bool:
    try:
        from rbi.db.conn import connect
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False


def _embed_ok() -> bool:
    try:
        from rbi.eval.naive import DEFAULT_EMBED_MODEL
        r = httpx.get(f"{config.ollama_host}/api/tags", timeout=3)
        return DEFAULT_EMBED_MODEL in {m["name"] for m in r.json().get("models", [])}
    except Exception:
        return False


def test_naive_rag_answers_with_provenance():
    # runtime guard (the test DB is provisioned by the session fixture, after collection)
    if not (_db_reachable() and _embed_ok()):
        pytest.skip("needs DB + embed model")

    from rbi.apply.build import build_timeline
    from rbi.classify.rules import DocumentMeta
    from rbi.db.conn import connect
    from rbi.db.sync import DocBundle, persist
    from rbi.eval.naive import NaiveRAG, build_index
    from rbi.group.build import group_ops
    from rbi.parse.schema import NewClause, Operation

    meta = DocumentMeta(rbi_ref="TEST/RRB", title="RRB IRACP", doc_type="amendment",
                        md_family="IRACP", entity_type_code="RRB",
                        issued_date=date(2026, 7, 16), effective_date=date(2026, 10, 1))
    op = Operation(seq=1, operation="insert", target_chapter="V", clause_numbers=["68C"],
                   new_clauses=[NewClause(clause_number="68C",
                       text="Any accrued but unrealised interest on an acquired SNFA "
                            "shall not be recognised as income.")],
                   evidence_span="x", confidence=1.0)
    bundle = DocBundle(meta=meta, operations=[op], source_url="test://", sha256="0" * 64,
                       raw_text="accrued but unrealised interest on an acquired SNFA")
    persist([bundle], build_timeline([(meta, [op])]), group_ops([]))  # into rbi_test

    with connect() as conn:
        n = build_index(conn)
        assert n > 0
        p = NaiveRAG(conn=conn).answer(GoldenQuestion(
            id="g001", category="lookup",
            question="How is accrued interest on an acquired SNFA treated?",
            entity_type="RRB", clause="68C", as_of=date(2026, 10, 2), expected_status="in_force"))
    assert p.status == "in_force" and p.text          # naive RAG always commits
    assert p.answer_entity == "RRB"
