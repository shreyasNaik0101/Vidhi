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


# --- live: build index + answer (skips without DB + embed model) ---
def _db_ok() -> bool:
    try:
        from rbi.db.conn import connect
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM document")
            return cur.fetchone()[0] > 0
    except Exception:
        return False


def _embed_ok() -> bool:
    try:
        from rbi.eval.naive import DEFAULT_EMBED_MODEL
        r = httpx.get(f"{config.ollama_host}/api/tags", timeout=3)
        return DEFAULT_EMBED_MODEL in {m["name"] for m in r.json().get("models", [])}
    except Exception:
        return False


@pytest.mark.skipif(not (_db_ok() and _embed_ok()), reason="needs DB with docs + embed model")
def test_naive_rag_answers_with_provenance():
    from rbi.db.conn import connect
    from rbi.eval.naive import NaiveRAG, build_index

    with connect() as conn:
        n = build_index(conn)
        assert n > 0
        rag = NaiveRAG(conn=conn)
        q = GoldenQuestion(id="g001", category="lookup",
                           question="How is accrued but unrealised interest on an acquired SNFA treated?",
                           entity_type="RRB", clause="68C", as_of=date(2026, 10, 2),
                           expected_status="in_force")
        p = rag.answer(q)
    assert p.status == "in_force" and p.text          # naive RAG always commits
    assert p.answer_entity in {"RRB", "LAB"}           # from whichever chunk was nearest
