"""Agent layer: tool behaviour (runs against the DB) + a gated live-agent test.

The tools are the substance — they reuse the resolver, so they carry its
abstention. They run whenever Postgres is up. The Groq round-trip is gated behind
GROQ_API_KEY so the suite stays green (and free) without a key.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("langchain_groq")

from rbi.agent.tools import clause_history, find_clause, list_banks, resolve_clause


def _db_ok() -> bool:
    try:
        from rbi.db.conn import connect
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False


DB = _db_ok()
needs_db = pytest.mark.skipif(not DB, reason="Postgres not available")


@needs_db
def test_resolve_in_force():
    out = resolve_clause.invoke({"bank": "RRB", "clause": "68C", "as_of": "2026-11-01"})
    assert out.startswith("IN FORCE")
    assert "SNFA" in out


@needs_db
def test_resolve_not_yet_in_force():
    out = resolve_clause.invoke({"bank": "RRB", "clause": "68C", "as_of": "2026-08-01"})
    assert "NOT YET IN FORCE" in out


@needs_db
def test_resolve_no_provision_abstains():
    # a bank type with no such clause — the tool must abstain, not invent
    out = resolve_clause.invoke({"bank": "SCB", "clause": "68C", "as_of": "2026-11-01"})
    assert "NO PROVISION" in out


@needs_db
def test_list_banks():
    # the test DB (rbi_test) is seeded per-run, so assert on what's guaranteed present
    out = list_banks.invoke({})
    assert "RRB" in out


@needs_db
def test_find_clause_matches_topic():
    out = find_clause.invoke({"bank": "RRB", "topic": "income recognition on an SNFA"})
    assert "68" in out


@needs_db
def test_clause_history_lists_versions():
    out = clause_history.invoke({"bank": "RRB", "clause": "68C"})
    assert "present" in out or "to " in out


@pytest.mark.skipif(
    not (os.getenv("GROQ_API_KEY") and DB),
    reason="live agent test needs GROQ_API_KEY and Postgres",
)
def test_agent_round_trip():
    from rbi.agent.agent import build_agent

    executor = build_agent()
    out = executor.invoke({
        "input": "What is the SNFA income rule for a Regional Rural Bank in November 2026?",
        "chat_history": [],
    })
    assert out["output"].strip()  # produced a grounded answer via the tools
